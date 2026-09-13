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
    delete_session, set_admin_password,
    get_subscribers, get_subscriber, set_subscriber_status, delete_subscriber,
    set_subscriber_sme, set_subscriber_closing_day
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

# Public App Bridge for Market Investing Platforms
@app.get("/place-bid", response_class=HTMLResponse)
async def place_bid_bridge(request: Request, name: str = "", category: str = "", price: str = "", retail_qty: str = "", shni_qty: str = ""):
    return templates.TemplateResponse(request=request, name="place_bid.html", context={
        "base_path": BASE_PATH,
        "name": name,
        "category": category,
        "price": price,
        "retail_qty": retail_qty,
        "shni_qty": shni_qty
    })

# Legacy alias for Kite
@app.get("/open-kite")
async def open_kite_bridge(request: Request):
    target = f"{BASE_PATH}/place-bid" if BASE_PATH else "/place-bid"
    qs = request.url.query
    if qs:
        target = f"{target}?{qs}"
    return RedirectResponse(url=target, status_code=307)

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

@app.get("/subscribers", response_class=HTMLResponse)
async def get_subscribers_page(request: Request):
    target_login = f"{BASE_PATH}/login" if BASE_PATH else "/login"
    if not check_is_authenticated(request):
        return RedirectResponse(url=target_login, status_code=303)
    return templates.TemplateResponse(request=request, name="subscribers.html", context={"base_path": BASE_PATH})

# Protected API Routes
@app.get("/api/settings", dependencies=[Depends(require_auth)])
async def get_all_settings():
    settings = get_settings()
    # Mask password hash for security
    sanitized = {k: v for k, v in settings.items() if k != "admin_password_hash"}
    if scheduler_instance:
        try:
            sanitized["schedule_info"] = scheduler_instance.get_schedule_info()
        except Exception as e:
            sanitized["schedule_info"] = {"error": str(e)}
    return sanitized

@app.get("/api/schedule-status", dependencies=[Depends(require_auth)])
async def get_schedule_status():
    global scheduler_instance
    if not scheduler_instance:
        return {"is_running": False, "jobs_count": 0, "jobs": [], "next_fire_time": None}
    return scheduler_instance.get_schedule_info()

@app.post("/api/settings", dependencies=[Depends(require_auth)])
async def save_settings(data: Dict[str, Any] = Body(...)):
    allowed_keys = [
        "bot_token", "chat_id", "gmp_threshold", "is_enabled",
        "enable_sme_alerts", "schedule_times", "timezone", "public_url"
    ]
    filtered = {k: str(v) for k, v in data.items() if k in allowed_keys}
    update_settings(filtered)
    
    if scheduler_instance:
        try:
            scheduler_instance.reload_schedule()
        except Exception as e:
            print(f"Error reloading scheduler: {e}")
            
    sanitized = {k: v for k, v in get_settings().items() if k != "admin_password_hash"}
    if scheduler_instance:
        try:
            sanitized["schedule_info"] = scheduler_instance.get_schedule_info()
        except Exception:
            pass
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

# Subscriber Management API
@app.get("/api/subscribers", dependencies=[Depends(require_auth)])
async def list_subscribers():
    subs = get_subscribers()
    pending = sum(1 for s in subs if s.get("status") == "pending")
    approved = sum(1 for s in subs if s.get("status") == "approved")
    rejected = sum(1 for s in subs if s.get("status") in ["rejected", "unsubscribed"])
    return {
        "subscribers": subs,
        "counts": {
            "total": len(subs),
            "pending": pending,
            "approved": approved,
            "rejected": rejected
        }
    }

@app.post("/api/subscribers/{chat_id}/approve", dependencies=[Depends(require_auth)])
async def approve_subscriber(chat_id: str):
    sub = get_subscriber(chat_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    set_subscriber_status(chat_id, "approved")
    
    # Notify user via Telegram bot if token is configured
    token = config.bot_token
    notified = False
    if token:
        try:
            client = TelegramClient(token)
            msg = (
                "🎉 <b>Subscription Approved!</b>\n\n"
                "Your request has been approved by the administrator. You will now receive high-GMP IPO alerts directly in this chat!\n\n"
                "• Send <code>/check</code> anytime to see open IPOs.\n"
                "• Send <code>/help</code> to view available commands."
            )
            success, _ = client.send_message(chat_id=chat_id, text=msg)
            notified = success
        except Exception:
            pass
            
    return {"status": "success", "message": f"Subscriber {chat_id} approved", "notified": notified}

@app.post("/api/subscribers/{chat_id}/reject", dependencies=[Depends(require_auth)])
async def reject_subscriber(chat_id: str):
    sub = get_subscriber(chat_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    set_subscriber_status(chat_id, "rejected")
    return {"status": "success", "message": f"Subscriber {chat_id} rejected"}

@app.delete("/api/subscribers/{chat_id}", dependencies=[Depends(require_auth)])
async def remove_subscriber(chat_id: str):
    success = delete_subscriber(chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"status": "success", "message": f"Subscriber {chat_id} deleted"}

@app.post("/api/subscribers/{chat_id}/toggle-sme", dependencies=[Depends(require_auth)])
async def toggle_subscriber_sme(chat_id: str):
    sub = get_subscriber(chat_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    current_sme = bool(sub.get("enable_sme", 0))
    new_sme = not current_sme
    set_subscriber_sme(chat_id, new_sme)
    return {"status": "success", "enable_sme": new_sme, "message": f"SME alerts {'enabled' if new_sme else 'disabled'} for subscriber"}

@app.post("/api/subscribers/{chat_id}/toggle-closing-day", dependencies=[Depends(require_auth)])
async def toggle_subscriber_closing_day(chat_id: str):
    sub = get_subscriber(chat_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    current_val = bool(sub.get("only_closing_day", 0))
    new_val = not current_val
    set_subscriber_closing_day(chat_id, new_val)
    return {
        "status": "success",
        "only_closing_day": new_val,
        "message": f"Closing-day-only alerts {'enabled' if new_val else 'disabled'} for subscriber"
    }

@app.post("/api/subscribers/{chat_id}/test", dependencies=[Depends(require_auth)])
async def test_subscriber(chat_id: str):
    sub = get_subscriber(chat_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    token = config.bot_token
    if not token:
        raise HTTPException(status_code=400, detail="Bot token is not configured in Settings")
    
    client = TelegramClient(token)
    name = sub.get("first_name") or "there"
    thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold
    thresh_tag = " (Customized)" if sub.get("gmp_threshold") is not None else " (System Default)"
    cat_pref = "Mainboard + SME" if bool(sub.get("enable_sme", 0)) else "Mainboard Only"
    timing_pref = "Closing Day Only" if bool(sub.get("only_closing_day", 0)) else "All Open Days"
    test_msg = (
        f"⚡ <b>IPO Wise Test Alert</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Hello <b>{name}</b>!\n\n"
        f"This is a test notification confirming that your Telegram connection to <b>IPO Wise</b> is active and working.\n\n"
        f"📊 <b>Your Alert Threshold:</b> GMP ≥ <b>{thresh}%</b>{thresh_tag}\n"
        f"🏢 <b>Categories:</b> {cat_pref}\n"
        f"📅 <b>Alert Timing:</b> {timing_pref}\n\n"
        f"<i>(You can customize these preferences anytime with <code>/threshold</code>, <code>/sme</code>, or <code>/closingday</code>).</i>"
    )
    success, msg = client.send_message(chat_id=chat_id, text=test_msg)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to send test message to {chat_id}: {msg}")
    
    return {"status": "success", "message": f"Test alert delivered successfully to {chat_id}"}

# Create mountable server app if BASE_PATH is provided
if BASE_PATH:
    server_app = FastAPI(title="IPO Wise Root")
    server_app.mount(BASE_PATH, app)
else:
    server_app = app
