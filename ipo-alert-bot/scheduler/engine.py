import logging
import re
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from scraper.investorgain import InvestorGainScraper
from bot.telegram_client import TelegramClient
from database import is_ipo_muted, log_alert, update_settings
from config import config

logger = logging.getLogger("ipo_bot.scheduler")

class AlertScheduler:
    def __init__(self):
        self.tz = self._resolve_timezone()
        self.scheduler = BackgroundScheduler(timezone=self.tz)
        self.scraper = InvestorGainScraper()

    def _resolve_timezone(self):
        tz_str = config.timezone or "Asia/Kolkata"
        try:
            return pytz.timezone(tz_str)
        except Exception:
            return pytz.timezone("Asia/Kolkata")

    def _get_now_str(self) -> str:
        return datetime.now(self.tz).strftime("%Y-%m-%d %H:%M:%S")

    def _parse_time_str(self, time_str: str):
        """
        Parses time strings supporting both 24-hour (e.g. 10:00, 15:30)
        and 12-hour AM/PM formats (e.g. 10:00 AM, 2:30 PM, 3 PM).
        Returns (hour, minute).
        """
        raw = time_str.strip()
        if not raw:
            raise ValueError("Empty time string")

        # Check for AM/PM
        match_12h = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", raw, re.IGNORECASE)
        if match_12h:
            hour = int(match_12h.group(1))
            minute = int(match_12h.group(2)) if match_12h.group(2) else 0
            meridiem = match_12h.group(3).lower()
            if hour < 1 or hour > 12 or minute < 0 or minute > 59:
                raise ValueError(f"Invalid 12-hour time: {raw}")
            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            return hour, minute

        # Standard 24-hour (e.g. 10:00 or 15:30)
        parts = raw.split(":")
        if len(parts) >= 2:
            hour = int(parts[0].strip())
            minute = int(parts[1].strip())
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute

        raise ValueError(f"Unsupported time format: '{raw}'. Expected 'HH:MM' or 'HH:MM AM/PM'")

    def start(self):
        self._reschedule()
        self.scheduler.start()
        print(f"[AlertScheduler] Background scheduler started in timezone {self.tz}.")
        logger.info(f"Background scheduler started with timezone: {self.tz}")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print("[AlertScheduler] Stopped scheduler.")
            logger.info("Stopped scheduler.")

    def reload_schedule(self):
        """Reloads jobs based on updated schedule_times in config"""
        self._reschedule()

    def _reschedule(self):
        self.scheduler.remove_all_jobs()
        self.tz = self._resolve_timezone()
        self.scheduler.timezone = self.tz

        times = config.schedule_times
        scheduled_count = 0

        for t in times:
            try:
                hour, minute = self._parse_time_str(t)
                trigger = CronTrigger(hour=hour, minute=minute, timezone=self.tz)
                self.scheduler.add_job(
                    self.execute_check_job,
                    trigger=trigger,
                    id=f"ipo_check_{hour:02d}_{minute:02d}",
                    replace_existing=True,
                    misfire_grace_time=3600,  # 1 hour grace window to prevent silent drops on VM lag
                    coalesce=True
                )
                scheduled_count += 1
                print(f"[AlertScheduler] Scheduled check for {hour:02d}:{minute:02d} ({self.tz})")
                logger.info(f"Scheduled check for {hour:02d}:{minute:02d} ({self.tz})")
            except Exception as e:
                print(f"[AlertScheduler] Invalid schedule time format '{t}': {e}")
                logger.warning(f"Invalid schedule time format '{t}': {e}")

        print(f"[AlertScheduler] Active scheduled jobs: {scheduled_count}")

    def execute_check_job(self):
        now_disp = self._get_now_str()
        print(f"[AlertScheduler] Scheduled check triggered at {now_disp} ({self.tz}).")
        logger.info(f"Scheduled check triggered at {now_disp}")
        self.run_check(is_manual=False)

    def get_schedule_info(self) -> dict:
        """Returns details on running scheduler, jobs, and upcoming execution times"""
        self.tz = self._resolve_timezone()
        jobs_list = []
        next_fire = None

        if self.scheduler.running:
            for job in sorted(self.scheduler.get_jobs(), key=lambda j: j.next_run_time or datetime.max.replace(tzinfo=self.tz)):
                nrt = job.next_run_time
                nrt_str = nrt.astimezone(self.tz).strftime("%Y-%m-%d %H:%M:%S %Z") if nrt else "None"
                if nrt and (next_fire is None or nrt < next_fire):
                    next_fire = nrt
                jobs_list.append({
                    "id": job.id,
                    "next_run_time": nrt_str,
                    "trigger": str(job.trigger)
                })

        next_fire_str = next_fire.astimezone(self.tz).strftime("%Y-%m-%d %H:%M:%S") if next_fire else None
        
        return {
            "is_running": self.scheduler.running,
            "jobs_count": len(jobs_list),
            "jobs": jobs_list,
            "next_fire_time": next_fire_str,
            "timezone": str(self.tz)
        }

    def run_check(self, target_chat_override: str = None, is_manual: bool = False) -> int:
        self.tz = self._resolve_timezone()
        now_str = self._get_now_str()
        
        if not is_manual and not config.is_enabled:
            status_msg = "Skipped (Bot Paused in Settings)"
            update_settings({"last_check_at": now_str, "last_check_status": status_msg})
            print(f"[AlertScheduler] Bot is disabled/paused in settings. Skipping check at {now_str}.")
            logger.info(f"Check skipped: {status_msg}")
            return 0

        token = config.bot_token
        chat_id = target_chat_override or config.chat_id
        min_gmp = config.gmp_threshold

        try:
            update_settings({"last_check_at": now_str, "last_check_status": "Checking live market..."})
            open_ipos = self.scraper.get_open_ipos_above_gmp(min_gmp)
            total_open = len(open_ipos)
            print(f"[AlertScheduler] Scraped market: Found {total_open} open IPO(s) with GMP >= {min_gmp}%.")
            logger.info(f"Found {total_open} open IPO(s) with GMP >= {min_gmp}%.")
            
            alerts_dispatched = 0
            muted_count = 0
            sme_skipped_count = 0
            client = TelegramClient(token) if token else None

            for ipo in open_ipos:
                name = ipo["name"]
                
                # Check if muted
                if is_ipo_muted(name):
                    muted_count += 1
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
                        details="Ignored/Applied by user",
                        sent_at=now_str
                    )
                    continue

                # Check SME rule
                category = ipo.get("category", "").upper()
                if category == "SME" and not config.enable_sme_alerts:
                    sme_skipped_count += 1
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
                        details="SME IPO alerts disabled by user rule",
                        sent_at=now_str
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
                        details=msg,
                        sent_at=now_str
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
                        details="Alert generated (Token/ChatID not configured)",
                        sent_at=now_str
                    )
                    alerts_dispatched += 1

            if alerts_dispatched > 0:
                status_summary = f"Success ({alerts_dispatched} alert(s) sent)"
            elif total_open == 0:
                status_summary = f"Success (0 open IPOs with GMP >= {min_gmp}%)"
            else:
                reasons = []
                if muted_count > 0:
                    reasons.append(f"{muted_count} muted")
                if sme_skipped_count > 0:
                    reasons.append(f"{sme_skipped_count} SME skipped")
                reason_str = f" ({', '.join(reasons)})" if reasons else ""
                status_summary = f"Success (No alerts dispatched{reason_str})"

            update_settings({"last_check_at": now_str, "last_check_status": status_summary})
            logger.info(f"Check finished: {status_summary}")
            return alerts_dispatched

        except Exception as e:
            err_msg = f"Error: {str(e)}"
            print(f"[AlertScheduler] Check failed: {e}")
            logger.exception(f"Alert check failed: {e}")
            update_settings({"last_check_at": now_str, "last_check_status": err_msg})
            return 0

