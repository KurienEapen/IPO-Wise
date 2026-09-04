import os
import sys
import uvicorn
import signal

# Ensure current directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import init_db
from scheduler.engine import AlertScheduler
from bot.handlers import BotUpdatePoller
from web.app import server_app, set_scheduler
from config import config

def start_services():
    print("=========================================")
    print("      IPO WISE TELEGRAM ALERT BOT        ")
    print("=========================================")

    # 1. Initialize SQLite Database
    init_db()

    # 2. Start Alert Scheduler (cron checks at 10:00, 12:30, 15:30)
    scheduler = AlertScheduler()
    set_scheduler(scheduler)
    scheduler.start()

    # 3. Start Telegram Bot Poller for inline button callbacks & commands
    def manual_trigger(target_chat_override=None):
        return scheduler.run_check(target_chat_override=target_chat_override, is_manual=True)

    poller = BotUpdatePoller(manual_check_trigger=manual_trigger)
    poller.start()

    def shutdown_handler(signum, frame):
        print("\nShutting down IPO Wise services...")
        poller.stop()
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    return scheduler, poller

if __name__ == "__main__":
    scheduler, poller = start_services()

    # 4. Start Web Management Console
    port = int(os.environ.get("PORT", 5050))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[WebConsole] Serving Web Management Console at http://{host}:{port}")

    try:
        uvicorn.run(server_app, host=host, port=port, log_level="info")
    finally:
        poller.stop()
        scheduler.stop()
