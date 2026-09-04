import os
from typing import Dict, Any
from database import get_settings, update_settings, init_db

init_db()

class AppConfig:
    @staticmethod
    def get_all() -> Dict[str, Any]:
        return get_settings()

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        settings = get_settings()
        return settings.get(key, default)

    @staticmethod
    def set(key: str, value: Any):
        update_settings({key: value})

    @property
    def bot_token(self) -> str:
        return os.environ.get("TELEGRAM_BOT_TOKEN") or self.get("bot_token", "")

    @property
    def chat_id(self) -> str:
        return os.environ.get("TELEGRAM_CHAT_ID") or self.get("chat_id", "")

    @property
    def gmp_threshold(self) -> float:
        try:
            return float(self.get("gmp_threshold", 15.0))
        except (ValueError, TypeError):
            return 15.0

    @property
    def is_enabled(self) -> bool:
        return str(self.get("is_enabled", "1")).lower() in ["1", "true", "yes"]

    @property
    def enable_sme_alerts(self) -> bool:
        return str(self.get("enable_sme_alerts", "1")).lower() in ["1", "true", "yes"]

    @property
    def schedule_times(self) -> list:
        val = self.get("schedule_times", "10:00,12:30,15:30")
        return [t.strip() for t in val.split(",") if t.strip()]

    @property
    def timezone(self) -> str:
        return self.get("timezone", "Asia/Kolkata")

config = AppConfig()
