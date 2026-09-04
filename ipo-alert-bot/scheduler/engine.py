from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from scraper.investorgain import InvestorGainScraper
from bot.telegram_client import TelegramClient
from database import is_ipo_muted, log_alert, update_settings
from config import config

class AlertScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scraper = InvestorGainScraper()

    def start(self):
        self._reschedule()
        self.scheduler.start()
        print("[AlertScheduler] Background scheduler started.")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print("[AlertScheduler] Stopped scheduler.")

    def reload_schedule(self):
        """Reloads jobs based on updated schedule_times in config"""
        self._reschedule()

    def _reschedule(self):
        self.scheduler.remove_all_jobs()
        tz_str = config.timezone or "Asia/Kolkata"
        try:
            tz = pytz.timezone(tz_str)
        except Exception:
            tz = pytz.timezone("Asia/Kolkata")

        times = config.schedule_times
        for t in times:
            try:
                parts = t.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
                self.scheduler.add_job(
                    self.execute_check_job,
                    trigger=trigger,
                    id=f"ipo_check_{hour}_{minute}",
                    replace_existing=True
                )
                print(f"[AlertScheduler] Scheduled check for {hour:02d}:{minute:02d} ({tz_str})")
            except Exception as e:
                print(f"[AlertScheduler] Invalid schedule time format '{t}': {e}")

    def execute_check_job(self):
        print("[AlertScheduler] Scheduled check triggered.")
        self.run_check(is_manual=False)

    def run_check(self, target_chat_override: str = None, is_manual: bool = False) -> int:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not is_manual and not config.is_enabled:
            update_settings({"last_check_at": now_str, "last_check_status": "Skipped (Bot Disabled)"})
            print("[AlertScheduler] Bot is disabled. Skipping check.")
            return 0

        token = config.bot_token
        chat_id = target_chat_override or config.chat_id
        min_gmp = config.gmp_threshold

        try:
            update_settings({"last_check_at": now_str, "last_check_status": "Checking..."})
            open_ipos = self.scraper.get_open_ipos_above_gmp(min_gmp)
            print(f"[AlertScheduler] Found {len(open_ipos)} open IPOs with GMP >= {min_gmp}%.")
            
            alerts_dispatched = 0
            client = TelegramClient(token) if token else None

            for ipo in open_ipos:
                name = ipo["name"]
                
                # Check if muted
                if is_ipo_muted(name):
                    print(f"[AlertScheduler] Skipping '{name}': Marked as Muted/Applied.")
                    log_alert(
                        ipo_name=name,
                        gmp_val=ipo.get("gmp_val", ""),
                        gmp_percent=ipo.get("gmp_percent", 0.0),
                        total_sub=ipo.get("total_sub", ""),
                        retail_sub=ipo.get("retail_sub", ""),
                        hni_sub=ipo.get("hni_sub", ""),
                        qib_sub=ipo.get("qib_sub", ""),
                        chat_id=chat_id or "NONE",
                        status="MUTED_SKIPPED",
                        details="Ignored/Applied by user"
                    )
                    continue

                # Check SME rule
                category = ipo.get("category", "").upper()
                if category == "SME" and not config.enable_sme_alerts:
                    print(f"[AlertScheduler] Skipping '{name}': SME IPO alerts are disabled by rule.")
                    log_alert(
                        ipo_name=name,
                        gmp_val=ipo.get("gmp_val", ""),
                        gmp_percent=ipo.get("gmp_percent", 0.0),
                        total_sub=ipo.get("total_sub", ""),
                        retail_sub=ipo.get("retail_sub", ""),
                        hni_sub=ipo.get("hni_sub", ""),
                        qib_sub=ipo.get("qib_sub", ""),
                        chat_id=chat_id or "NONE",
                        status="SME_SKIPPED",
                        details="SME IPO alerts disabled by user rule"
                    )
                    continue

                card_html, markup = TelegramClient.format_ipo_alert(ipo)
                
                if client and chat_id:
                    success, msg = client.send_message(chat_id=chat_id, text=card_html, reply_markup=markup)
                    status_log = "SENT" if success else "FAILED"
                    log_alert(
                        ipo_name=name,
                        gmp_val=ipo.get("gmp_val", ""),
                        gmp_percent=ipo.get("gmp_percent", 0.0),
                        total_sub=ipo.get("total_sub", ""),
                        retail_sub=ipo.get("retail_sub", ""),
                        hni_sub=ipo.get("hni_sub", ""),
                        qib_sub=ipo.get("qib_sub", ""),
                        chat_id=chat_id,
                        status=status_log,
                        details=msg
                    )
                    if success:
                        alerts_dispatched += 1
                else:
                    # Dry run / Token not set
                    print(f"[AlertScheduler] Dry-run alert for '{name}' (Token/ChatID not set):")
                    log_alert(
                        ipo_name=name,
                        gmp_val=ipo.get("gmp_val", ""),
                        gmp_percent=ipo.get("gmp_percent", 0.0),
                        total_sub=ipo.get("total_sub", ""),
                        retail_sub=ipo.get("retail_sub", ""),
                        hni_sub=ipo.get("hni_sub", ""),
                        qib_sub=ipo.get("qib_sub", ""),
                        chat_id=chat_id or "NONE",
                        status="DRY_RUN",
                        details="Alert generated (Token/ChatID not configured)"
                    )
                    alerts_dispatched += 1

            status_summary = f"Success ({alerts_dispatched} alert(s) sent)" if alerts_dispatched > 0 else "Success (No new alerts)"
            update_settings({"last_check_at": now_str, "last_check_status": status_summary})
            return alerts_dispatched

        except Exception as e:
            err_msg = f"Error: {str(e)}"
            print(f"[AlertScheduler] Check failed: {e}")
            update_settings({"last_check_at": now_str, "last_check_status": err_msg})
            return 0
