import os
import time
import base64
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Body, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import config
from database import (
    get_settings, update_settings, mute_ipo, unmute_ipo,
    get_muted_ipos, is_ipo_muted, get_recent_alert_logs,
    verify_admin_login, create_session, validate_session,
    delete_session, set_admin_password
)
from bot.telegram_client import TelegramClient
from scraper.investorgain import InvestorGainScraper

app = FastAPI(title="IPO Wise Console")

# Subpath / Base Path support (e.g. BASE_PATH=/ipo for Nginx subpath routing)
BASE_PATH = os.environ.get("BASE_PATH", "").rstrip("/")
if BASE_PATH and not BASE_PATH.startswith("/"):
    BASE_PATH = "/" + BASE_PATH

# Setup directories
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(CURRENT_DIR, "static")
TEMPLATES_DIR = os.path.join(CURRENT_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Scraper instance & simple in-memory cache
scraper = InvestorGainScraper()
_ipos_cache: Dict[str, Any] = {"timestamp": 0, "data": []}

# Global scheduler reference (attached by main.py)
scheduler_instance = None

def set_scheduler(scheduler):
    global scheduler_instance
    scheduler_instance = scheduler

# Authentication Dependency
def check_is_authenticated(request: Request) -> bool:
    # 1. Check Cookie
    session_token = request.cookies.get("ipo_session")
    if session_token and validate_session(session_token):
        return True

    # 2. Check Authorization Header (Bearer token or Basic Auth)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if validate_session(token):
            return True
    elif auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            parts = decoded.split(":", 1)
            password = parts[1] if len(parts) > 1 else parts[0]
            if verify_admin_login(password):
                return True
        except Exception:
            pass

    return False

def require_auth(request: Request):
    if not check_is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")

# Public Routes
@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    target_home = f"{BASE_PATH}/" if BASE_PATH else "/"
    target_login = f"{BASE_PATH}/login" if BASE_PATH else "/login"
    if check_is_authenticated(request):
        return RedirectResponse(url=target_home, status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"base_path": BASE_PATH})

@app.post("/api/login")
async def handle_login(data: Dict[str, str] = Body(...)):
    password = data.get("password", "")
    if not password or not verify_admin_login(password):
        raise HTTPException(status_code=401, detail="Incorrect admin password")

    token = create_session(duration_hours=72)
    response = JSONResponse(content={"status": "success", "message": "Authenticated successfully", "token": token})
    # Set secure HttpOnly cookie
    response.set_cookie(
        key="ipo_session",
        value=token,
        max_age=72 * 3600,
        httponly=True,
        samesite="lax"
    )
    return response

@app.get("/logout")
@app.post("/api/logout")
async def handle_logout(request: Request):
    session_token = request.cookies.get("ipo_session")
    if session_token:
        delete_session(session_token)
    target_login = f"{BASE_PATH}/login" if BASE_PATH else "/login"
    response = RedirectResponse(url=target_login, status_code=303)
    response.delete_cookie(key="ipo_session")
    return response

# Protected UI Dashboard & Settings
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    target_login = f"{BASE_PATH}/login" if BASE_PATH else "/login"
    if not check_is_authenticated(request):
        return RedirectResponse(url=target_login, status_code=303)
    return templates.TemplateResponse(request=request, name="index.html", context={"base_path": BASE_PATH})

@app.get("/settings", response_class=HTMLResponse)
async def get_settings_page(request: Request):
    target_login = f"{BASE_PATH}/login" if BASE_PATH else "/login"
    if not check_is_authenticated(request):
        return RedirectResponse(url=target_login, status_code=303)
    return templates.TemplateResponse(request=request, name="settings.html", context={"base_path": BASE_PATH})

# Protected API Routes
@app.get("/api/settings", dependencies=[Depends(require_auth)])
async def get_all_settings():
    settings = get_settings()
    # Mask password hash for security
    sanitized = {k: v for k, v in settings.items() if k != "admin_password_hash"}
    return sanitized

@app.post("/api/settings", dependencies=[Depends(require_auth)])
async def save_settings(data: Dict[str, Any] = Body(...)):
    allowed_keys = [
        "bot_token", "chat_id", "gmp_threshold", "is_enabled",
        "enable_sme_alerts", "schedule_times", "timezone"
    ]
    filtered = {k: str(v) for k, v in data.items() if k in allowed_keys}
    update_settings(filtered)
    
    if scheduler_instance:
        try:
            scheduler_instance.reload_schedule()
        except Exception as e:
            print(f"Error reloading scheduler: {e}")
            
    sanitized = {k: v for k, v in get_settings().items() if k != "admin_password_hash"}
    return {"status": "success", "message": "Settings updated successfully", "settings": sanitized}

@app.post("/api/change-password", dependencies=[Depends(require_auth)])
async def change_password(data: Dict[str, str] = Body(...)):
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not current_pw or not verify_admin_login(current_pw):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    if not new_pw or len(new_pw) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters long")

    set_admin_password(new_pw)
    return {"status": "success", "message": "Password updated successfully"}

@app.post("/api/test-telegram", dependencies=[Depends(require_auth)])
async def test_telegram(data: Dict[str, str] = Body(...)):
    token = data.get("bot_token") or config.bot_token
    chat_id = data.get("chat_id") or config.chat_id
    
    if not token:
        raise HTTPException(status_code=400, detail="Bot token is required")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Chat / Channel ID is required")
        
    client = TelegramClient(token)
    ok, me = client.get_me()
    if not ok:
        raise HTTPException(status_code=400, detail=f"Invalid Bot Token: {me.get('error', 'Could not reach Telegram')}")
        
    bot_username = me.get("username", "UnknownBot")
    test_msg = (
        f"🤖 <b>IPO Wise Test Alert</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Connection successful from <b>@{bot_username}</b>!\n"
        f"Your Telegram notifications are properly configured."
    )
    success, err = client.send_message(chat_id, test_msg)
    if not success:
        raise HTTPException(status_code=400, detail=f"Bot valid, but failed to send to chat '{chat_id}': {err}")
        
    return {"status": "success", "message": f"Verified! Test message sent to {chat_id} via @{bot_username}"}

@app.post("/api/trigger-check", dependencies=[Depends(require_auth)])
async def trigger_check():
    global scheduler_instance
    if not scheduler_instance:
        raise HTTPException(status_code=500, detail="Scheduler service not initialized")
        
    count = scheduler_instance.run_check(is_manual=True)
    return {
        "status": "success",
        "message": f"Check executed. Dispatched {count} alert(s).",
        "alerts_count": count
    }

@app.get("/api/ipos", dependencies=[Depends(require_auth)])
async def get_live_ipos(force: bool = False):
    global _ipos_cache
    now = time.time()
    if not force and _ipos_cache["data"] and (now - _ipos_cache["timestamp"] < 90):
        ipos = _ipos_cache["data"]
    else:
        ipos = scraper.parse_all_ipos()
        _ipos_cache = {"timestamp": now, "data": ipos}

    for ipo in ipos:
        ipo["is_muted"] = is_ipo_muted(ipo["name"])

    return {
        "count": len(ipos),
        "ipos": ipos,
        "cached": not force and (now - _ipos_cache["timestamp"] < 90)
    }

@app.get("/api/muted", dependencies=[Depends(require_auth)])
async def list_muted():
    return get_muted_ipos()

@app.post("/api/mute", dependencies=[Depends(require_auth)])
async def mute_item(data: Dict[str, str] = Body(...)):
    name = data.get("name", "").strip()
    action = data.get("action", "IGNORED").strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="IPO name is required")
        
    mute_ipo(name, action=action)
    return {"status": "success", "message": f"Muted '{name}' ({action})"}

@app.post("/api/unmute", dependencies=[Depends(require_auth)])
async def unmute_item(data: Dict[str, str] = Body(...)):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="IPO name is required")
        
    success = unmute_ipo(name)
    return {"status": "success", "message": f"Unmuted '{name}'", "found": success}

@app.get("/api/logs", dependencies=[Depends(require_auth)])
async def get_logs(limit: int = 50):
    return get_recent_alert_logs(limit)

# Create mountable server app if BASE_PATH is provided
if BASE_PATH:
    server_app = FastAPI(title="IPO Wise Root")
    server_app.mount(BASE_PATH, app)
else:
    server_app = app
