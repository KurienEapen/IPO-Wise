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

    @property
    def public_url(self) -> str:
        val = os.environ.get("PUBLIC_URL") or self.get("public_url", "")
        if val:
            return val.rstrip("/")
        # Auto-detect local IP if running locally
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            port = os.environ.get("PORT", "5050")
            base = os.environ.get("BASE_PATH", "").rstrip("/")
            return f"http://{ip}:{port}{base}"
        except Exception:
            return ""

    @property
    def bid_bridge_url(self) -> str:
        # Only route Telegram alerts through the bridge if an explicit public_url is configured.
        # Otherwise, fallback to direct broker URL so alerts never break with unroutable private IPs.
        val = os.environ.get("PUBLIC_URL") or self.get("public_url", "")
        if not val:
            return ""
        val = val.rstrip("/")
        base_subpath = os.environ.get("BASE_PATH", "").strip("/")
        if base_subpath and not val.endswith(f"/{base_subpath}"):
            val = f"{val}/{base_subpath}"
        return f"{val}/place-bid"

    @property
    def kite_bridge_url(self) -> str:
        bridge = self.bid_bridge_url
        if bridge:
            return bridge
        return "https://kite.zerodha.com/bids/ipo"

config = AppConfig()
