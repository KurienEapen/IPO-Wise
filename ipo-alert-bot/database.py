import sqlite3
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

DB_PATH = os.environ.get("IPO_BOT_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipo_bot.db"))

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table for key-value configuration settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    # Table for muted/ignored IPOs
    cursor.execute("PRAGMA table_info(muted_ipos)")
    cols = [r["name"] for r in cursor.fetchall()]
    if cols and "chat_id" not in cols:
        cursor.execute("""
        CREATE TABLE muted_ipos_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL DEFAULT 'GLOBAL',
            ipo_name TEXT NOT NULL,
            clean_name TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(chat_id, clean_name)
        )
        """)
        cursor.execute("""
        INSERT OR IGNORE INTO muted_ipos_new (id, chat_id, ipo_name, clean_name, action, created_at)
        SELECT id, 'GLOBAL', ipo_name, clean_name, action, created_at FROM muted_ipos
        """)
        cursor.execute("DROP TABLE muted_ipos")
        cursor.execute("ALTER TABLE muted_ipos_new RENAME TO muted_ipos")
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS muted_ipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL DEFAULT 'GLOBAL',
            ipo_name TEXT NOT NULL,
            clean_name TEXT NOT NULL,
            action TEXT NOT NULL, -- 'APPLIED' or 'IGNORED'
            created_at TEXT NOT NULL,
            UNIQUE(chat_id, clean_name)
        )
        """)

    # Table for subscribers (Telegram users)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscribers (
        chat_id TEXT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'unsubscribed'
        gmp_threshold REAL DEFAULT NULL,
        enable_sme INTEGER DEFAULT 0,
        only_closing_day INTEGER DEFAULT 0,
        disable_bid_button INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    cursor.execute("PRAGMA table_info(subscribers)")
    sub_cols = [r["name"] for r in cursor.fetchall()]
    if sub_cols and "gmp_threshold" not in sub_cols:
        cursor.execute("ALTER TABLE subscribers ADD COLUMN gmp_threshold REAL DEFAULT NULL")
    if sub_cols and "enable_sme" not in sub_cols:
        cursor.execute("ALTER TABLE subscribers ADD COLUMN enable_sme INTEGER DEFAULT 0")
    if sub_cols and "only_closing_day" not in sub_cols:
        cursor.execute("ALTER TABLE subscribers ADD COLUMN only_closing_day INTEGER DEFAULT 0")
    if sub_cols and "disable_bid_button" not in sub_cols:
        cursor.execute("ALTER TABLE subscribers ADD COLUMN disable_bid_button INTEGER DEFAULT 0")
    
    # Table for dispatch alert logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ipo_name TEXT NOT NULL,
        gmp_val TEXT,
        gmp_percent REAL,
        total_sub TEXT,
        retail_sub TEXT,
        hni_sub TEXT,
        qib_sub TEXT,
        chat_id TEXT,
        status TEXT, -- 'SENT', 'FAILED', 'DRY_RUN'
        details TEXT,
        sent_at TEXT NOT NULL
    )
    """)
    
    # Table for active user sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """)
    
    # Default settings
    default_settings = {
        "bot_token": "",
        "chat_id": "",
        "gmp_threshold": "15.0",
        "is_enabled": "1",
        "enable_sme_alerts": "1",
        "schedule_times": "10:00,12:30,15:30",
        "timezone": "Asia/Kolkata",
        "public_url": "",
        "last_check_at": "",
        "last_check_status": "Idle",
        "admin_username": "admin"
    }
    
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    conn.commit()
    conn.close()

def get_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def update_settings(new_settings: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    for k, v in new_settings.items():
        cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (k, str(v)))
    conn.commit()
    conn.close()

def clean_ipo_key(name: str) -> str:
    """Normalize IPO name for robust matching (lowercase, alphanumeric only)"""
    return "".join(c for c in name.lower() if c.isalnum())

def mute_ipo(ipo_name: str, chat_id: str = "GLOBAL", action: str = "IGNORED") -> bool:
    """Mute an IPO from alerts for a user or globally (action: APPLIED or IGNORED)"""
    clean_k = clean_ipo_key(ipo_name)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cid = str(chat_id or "GLOBAL").strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO muted_ipos (chat_id, ipo_name, clean_name, action, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, clean_name) DO UPDATE SET
            action=excluded.action,
            created_at=excluded.created_at,
            ipo_name=excluded.ipo_name
        """, (cid, ipo_name.strip(), clean_k, action.upper(), now_str))
        conn.commit()
        return True
    finally:
        conn.close()

def unmute_ipo(ipo_name: str, chat_id: str = "GLOBAL") -> bool:
    """Unmute an IPO so alerts can resume if eligible"""
    clean_k = clean_ipo_key(ipo_name)
    cid = str(chat_id or "GLOBAL").strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if cid == "GLOBAL":
            cursor.execute("DELETE FROM muted_ipos WHERE clean_name = ? OR ipo_name = ?", (clean_k, ipo_name.strip()))
        else:
            cursor.execute("DELETE FROM muted_ipos WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND (clean_name = ? OR ipo_name = ?)", (cid, clean_k, ipo_name.strip()))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def is_ipo_muted(ipo_name: str, chat_id: Optional[str] = None) -> bool:
    clean_k = clean_ipo_key(ipo_name)
    conn = get_db_connection()
    cursor = conn.cursor()
    if chat_id:
        cid = str(chat_id).strip()
        cursor.execute("""
        SELECT id FROM muted_ipos
        WHERE (clean_name = ? OR ipo_name = ?) AND (chat_id = 'GLOBAL' OR chat_id = ?)
        """, (clean_k, ipo_name.strip(), cid))
    else:
        cursor.execute("""
        SELECT id FROM muted_ipos
        WHERE (clean_name = ? OR ipo_name = ?) AND chat_id = 'GLOBAL'
        """, (clean_k, ipo_name.strip()))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def get_muted_ipos(chat_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if chat_id:
        cursor.execute("SELECT id, chat_id, ipo_name, action, created_at FROM muted_ipos WHERE chat_id = ? OR chat_id = 'GLOBAL' ORDER BY id DESC", (str(chat_id).strip(),))
    else:
        cursor.execute("SELECT id, chat_id, ipo_name, action, created_at FROM muted_ipos ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def cleanup_closed_muted_ipos(active_open_names: List[str]) -> int:
    """Removes muted IPO entries for IPOs that are no longer active/open to prevent table bloat."""
    if not active_open_names:
        return 0
    active_clean_keys = set(clean_ipo_key(n) for n in active_open_names if n)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, clean_name FROM muted_ipos")
        rows = cursor.fetchall()
        to_delete = [row["id"] for row in rows if row["clean_name"] not in active_clean_keys]
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            cursor.execute(f"DELETE FROM muted_ipos WHERE id IN ({placeholders})", to_delete)
            conn.commit()
            return len(to_delete)
        return 0
    finally:
        conn.close()

# Subscriber Management Functions
def register_or_update_subscriber(chat_id: str, username: str = "", first_name: str = "", last_name: str = "") -> Dict[str, Any]:
    cid = str(chat_id).strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM subscribers WHERE chat_id = ?", (cid,))
        existing = cursor.fetchone()
        if existing:
            current = dict(existing)
            # If user was unsubscribed or rejected and requested again, set back to pending
            new_status = "pending" if current["status"] in ["unsubscribed", "rejected"] else current["status"]
            cursor.execute("""
            UPDATE subscribers 
            SET username = ?, first_name = ?, last_name = ?, status = ?, updated_at = ?
            WHERE chat_id = ?
            """, (username or current.get("username", ""), first_name or current.get("first_name", ""), last_name or current.get("last_name", ""), new_status, now_str, cid))
            conn.commit()
            current["status"] = new_status
            return current
        else:
            cursor.execute("""
            INSERT INTO subscribers (chat_id, username, first_name, last_name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """, (cid, username, first_name, last_name, now_str, now_str))
            conn.commit()
            return {
                "chat_id": cid,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "status": "pending",
                "created_at": now_str,
                "updated_at": now_str
            }
    finally:
        conn.close()

def get_subscriber(chat_id: str) -> Optional[Dict[str, Any]]:
    cid = str(chat_id).strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscribers WHERE chat_id = ?", (cid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_subscribers(status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM subscribers WHERE status = ? ORDER BY created_at DESC", (status.strip(),))
    else:
        cursor.execute("SELECT * FROM subscribers ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_approved_subscribers() -> List[Dict[str, Any]]:
    return get_subscribers(status="approved")

def set_subscriber_status(chat_id: str, status: str) -> bool:
    cid = str(chat_id).strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE subscribers SET status = ?, updated_at = ? WHERE chat_id = ?", (status.strip(), now_str, cid))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def set_subscriber_threshold(chat_id: str, threshold: Optional[float]) -> bool:
    cid = str(chat_id).strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE subscribers SET gmp_threshold = ?, updated_at = ? WHERE chat_id = ?", (threshold, now_str, cid))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def set_subscriber_sme(chat_id: str, enable_sme: bool) -> bool:
    cid = str(chat_id).strip()
    val = 1 if enable_sme else 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE subscribers SET enable_sme = ?, updated_at = ? WHERE chat_id = ?", (val, now_str, cid))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def set_subscriber_closing_day(chat_id: str, only_closing_day: bool) -> bool:
    cid = str(chat_id).strip()
    val = 1 if only_closing_day else 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE subscribers SET only_closing_day = ?, updated_at = ? WHERE chat_id = ?", (val, now_str, cid))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def set_subscriber_bid_button(chat_id: str, disable_bid: bool) -> bool:
    cid = str(chat_id).strip()
    val = 1 if disable_bid else 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE subscribers SET disable_bid_button = ?, updated_at = ? WHERE chat_id = ?", (val, now_str, cid))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def delete_subscriber(chat_id: str) -> bool:
    cid = str(chat_id).strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM subscribers WHERE chat_id = ?", (cid,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def log_alert(ipo_name: str, gmp_val: str, gmp_percent: float, total_sub: str,
              retail_sub: str, hni_sub: str, qib_sub: str, chat_id: str,
              status: str, details: str = "", sent_at: Optional[str] = None):
    now_str = sent_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO alert_logs (ipo_name, gmp_val, gmp_percent, total_sub, retail_sub, hni_sub, qib_sub, chat_id, status, details, sent_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ipo_name, gmp_val, gmp_percent, total_sub, retail_sub, hni_sub, qib_sub, chat_id, status, details, now_str))
    conn.commit()
    conn.close()

def get_recent_alert_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Authentication Helpers
import hashlib
import secrets
from datetime import timedelta

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
    return f"{salt}:{dk.hex()}"

def verify_password(stored_hash: str, password: str) -> bool:
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, dk_hex = stored_hash.split(":", 1)
    new_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
    return secrets.compare_digest(dk_hex, new_dk.hex())

def set_admin_password(password: str):
    hashed = hash_password(password)
    update_settings({"admin_password_hash": hashed})

def get_admin_password_hash() -> str:
    settings = get_settings()
    stored = settings.get("admin_password_hash", "")
    if not stored:
        # Default password from ENV or fallback
        initial_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
        stored = hash_password(initial_pw)
        update_settings({"admin_password_hash": stored})
    return stored

def verify_admin_login(password: str) -> bool:
    # Also check if ADMIN_PASSWORD environment variable matches directly
    env_pw = os.environ.get("ADMIN_PASSWORD")
    if env_pw and secrets.compare_digest(password, env_pw):
        return True
    stored_hash = get_admin_password_hash()
    return verify_password(stored_hash, password)

def create_session(duration_hours: int = 72) -> str:
    token = secrets.token_hex(32)
    now = datetime.now()
    expires = now + timedelta(hours=duration_hours)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_str = expires.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (token, created_at, expires_at) VALUES (?, ?, ?)", (token, now_str, expires_str))
    conn.commit()
    conn.close()
    return token

def validate_session(token: str) -> bool:
    if not token:
        return False
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT token FROM sessions WHERE token = ? AND expires_at > ?", (token.strip(), now_str))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def delete_session(token: str):
    if not token:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token.strip(),))
    conn.commit()
    conn.close()

