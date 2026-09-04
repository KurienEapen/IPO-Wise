import requests
import json
from typing import Dict, Any, Optional, Tuple

class TelegramClient:
    def __init__(self, token: str):
        self.token = token.strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def get_me(self) -> Tuple[bool, Dict[str, Any]]:
        if not self.token:
            return False, {"error": "Bot token is empty"}
        try:
            resp = requests.get(f"{self.base_url}/getMe", timeout=8)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return True, data.get("result", {})
            return False, {"error": data.get("description", "Failed to connect to Telegram")}
        except Exception as e:
            return False, {"error": str(e)}

    def send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        if not self.token:
            return False, "Bot token not configured"
        if not chat_id:
            return False, "Chat ID not configured"

        payload = {
            "chat_id": chat_id.strip(),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        try:
            resp = requests.post(f"{self.base_url}/sendMessage", data=payload, timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return True, "Message sent successfully"
            return False, data.get("description", f"Telegram API error {resp.status_code}")
        except Exception as e:
            return False, str(e)

    def answer_callback_query(self, callback_query_id: str, text: str, show_alert: bool = True) -> bool:
        try:
            payload = {
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert
            }
            resp = requests.post(f"{self.base_url}/answerCallbackQuery", data=payload, timeout=8)
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception:
            return False

    def edit_message_reply_markup(self, chat_id: str, message_id: int, reply_markup: Optional[Dict[str, Any]] = None):
        try:
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": json.dumps(reply_markup) if reply_markup else json.dumps({"inline_keyboard": []})
            }
            requests.post(f"{self.base_url}/editMessageReplyMarkup", data=payload, timeout=8)
        except Exception:
            pass

    @staticmethod
    def format_ipo_alert(ipo: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Formats the IPO card and returns (html_text, inline_keyboard_markup)"""
        name = ipo.get("name", "Unknown IPO")
        cat = ipo.get("category", "Mainboard")
        gmp_val = ipo.get("gmp_val", "₹0")
        gmp_pct = ipo.get("gmp_percent", 0.0)
        start_d = ipo.get("start_date", "TBA")
        end_d = ipo.get("end_date", "TBA")
        price = ipo.get("price", "TBA")
        
        qib = ipo.get("qib_sub", "-")
        hni = ipo.get("hni_sub", "-")
        retail = ipo.get("retail_sub", "-")
        total = ipo.get("total_sub", "-")
        
        retail_order = ipo.get("retail_min_order", "1 Lot")
        hni_order = ipo.get("hni_min_order", "2 Lots")

        # Visual indicator
        fire = "🔥" if gmp_pct >= 25 else "⚡"
        
        html_msg = (
            f"🚀 <b>HIGH GMP ALERT: {name}</b> {fire}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Key Highlights:</b>\n"
            f"• <b>Category:</b> {cat} IPO\n"
            f"• <b>GMP:</b> {gmp_val} (<b>+{gmp_pct}%</b>)\n"
            f"• <b>Issue Dates:</b> {start_d} ➔ {end_d}\n"
            f"• <b>Price Band:</b> {price}\n\n"
            f"📈 <b>Subscription Demand:</b>\n"
            f"• <b>QIB:</b> {qib}\n"
            f"• <b>HNI / NII:</b> {hni}\n"
            f"• <b>Retail:</b> {retail}\n"
            f"• <b>Overall:</b> {total}\n\n"
            f"📦 <b>Minimum Investment:</b>\n"
            f"• <b>Retail (Min):</b> {retail_order}\n"
            f"• <b>HNI (Min):</b> {hni_order}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Tap below if you have applied or wish to mute this IPO:</i>"
        )

        # Telegram callback_data limit is 64 bytes. Clean name for callback data:
        cb_name = name[:28].replace(":", "")
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Applied (Mute)",
                        "callback_data": f"mute:applied:{cb_name}"
                    },
                    {
                        "text": "🔕 Ignore IPO",
                        "callback_data": f"mute:ignored:{cb_name}"
                    }
                ]
            ]
        }
        return html_msg, reply_markup
