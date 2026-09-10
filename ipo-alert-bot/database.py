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
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS muted_ipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ipo_name TEXT UNIQUE NOT NULL,
        clean_name TEXT NOT NULL,
        action TEXT NOT NULL, -- 'APPLIED' or 'IGNORED'
        created_at TEXT NOT NULL
    )
    """)
    
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

def mute_ipo(ipo_name: str, action: str = "IGNORED") -> bool:
    """Mute an IPO from further alerts (action: APPLIED or IGNORED)"""
    clean_k = clean_ipo_key(ipo_name)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO muted_ipos (ipo_name, clean_name, action, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ipo_name) DO UPDATE SET action=excluded.action, created_at=excluded.created_at
        """, (ipo_name.strip(), clean_k, action.upper(), now_str))
        conn.commit()
        return True
    finally:
        conn.close()

def unmute_ipo(ipo_name: str) -> bool:
    """Unmute an IPO so alerts can resume if eligible"""
    clean_k = clean_ipo_key(ipo_name)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM muted_ipos WHERE clean_name = ? OR ipo_name = ?", (clean_k, ipo_name.strip()))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def is_ipo_muted(ipo_name: str) -> bool:
    clean_k = clean_ipo_key(ipo_name)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM muted_ipos WHERE clean_name = ? OR ipo_name = ?", (clean_k, ipo_name.strip()))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def get_muted_ipos() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ipo_name, action, created_at FROM muted_ipos ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

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

