import requests
import json
import re
import urllib.parse
from datetime import datetime
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

    def edit_message_text(self, chat_id: str, message_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        try:
            payload = {
                "chat_id": str(chat_id).strip(),
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if reply_markup is not None:
                payload["reply_markup"] = json.dumps(reply_markup)
            resp = requests.post(f"{self.base_url}/editMessageText", data=payload, timeout=8)
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception:
            return False

    def delete_webhook(self, drop_pending_updates: bool = False) -> bool:
        if not self.token:
            return False
        try:
            params = {"drop_pending_updates": drop_pending_updates}
            resp = requests.get(f"{self.base_url}/deleteWebhook", params=params, timeout=8)
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception:
            return False

    @staticmethod
    def format_ipo_alert(ipo: Dict[str, Any], include_buttons: bool = True, hide_bid_button: bool = False) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Formats the IPO card and returns (html_text, inline_keyboard_markup).
        Clean, icon-free layout with separate sHNI/bHNI, Investment section, and Add to Calendar."""
        name = ipo.get("name", "Unknown IPO").strip()
        
        # Category normalization (prevents "IPO IPO")
        cat_raw = ipo.get("category", "Mainboard")
        if str(cat_raw).strip().upper() in ["IPO", "MAINBOARD", "MAIN"]:
            cat_disp = "Mainboard"
        elif str(cat_raw).strip().upper() in ["SME"]:
            cat_disp = "SME"
        else:
            cat_disp = re.sub(r"(?i)\s*ipo$", "", str(cat_raw)).strip() or "Mainboard"

        gmp_val = ipo.get("gmp_val", "₹0")
        gmp_pct = ipo.get("gmp_percent", 0.0)
        start_d = ipo.get("start_date", "TBA")
        end_d = ipo.get("end_date", "TBA")
        price = ipo.get("price", "TBA")
        
        qib = ipo.get("qib_sub", "-")
        shni = ipo.get("shni_sub") or ipo.get("hni_sub", "-")
        bhni = ipo.get("bhni_sub", "-")
        retail = ipo.get("retail_sub", "-")
        total = ipo.get("total_sub", "-")
        
        retail_order = ipo.get("retail_min_order", "1 Lot")
        shni_order = ipo.get("shni_min_order") or ipo.get("hni_min_order", "2 Lots")

        # Strip commas and wrap shares in <code> for native 1-tap copy to clipboard in Telegram (ready for broker apps)
        def make_copyable_shares(order_str: str) -> str:
            return re.sub(r"\((\d[\d,]*)\)", lambda m: f"(<code>{m.group(1).replace(',', '')}</code>)", str(order_str))

        retail_order_html = make_copyable_shares(retail_order)
        shni_order_html = make_copyable_shares(shni_order)

        is_closing = bool(ipo.get("is_closing_today") or str(ipo.get("status", "")).upper() == "CLOSING_TODAY")
        if not is_closing:
            try:
                import pytz
                today_ist = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d")
            except Exception:
                today_ist = datetime.now().strftime("%Y-%m-%d")
            if str(ipo.get("end_date_sort") or "").strip() == today_ist:
                is_closing = True

        title_ending = " - Ending Today" if is_closing else ""
        header_title = f"<b>High GMP: {name} ({gmp_pct}%){title_ending}</b>"

        html_msg = (
            f"{header_title}\n\n"
            f"<b>Category: {cat_disp}</b>\n"
            f"• GMP: {gmp_val} (+{gmp_pct}%)\n"
            f"• Issue Dates: {start_d} - {end_d}\n"
            f"• Price: {price}\n\n"
            f"<b>Subscription</b>\n"
            f"• QIB: {qib}\n"
            f"• sHNI: {shni}\n"
            f"• bHNI: {bhni}\n"
            f"• Retail: {retail}\n"
            f"• Total: {total}\n\n"
            f"<b>Investment</b>\n"
            f"• Retail: {retail_order_html}\n"
            f"• sHNI: {shni_order_html}"
        )

        if not include_buttons:
            return html_msg, None

        # Calendar reminder link (Google Calendar template opens native app / web)
        end_date_sort = str(ipo.get("end_date_sort") or "").strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", end_date_sort):
            parts = end_date_sort.split("-")
            yr, mo, dy = parts[0], parts[1], parts[2]
            start_utc_str = f"{yr}{mo}{dy}T043000Z" # 10:00 AM IST
            end_utc_str = f"{yr}{mo}{dy}T113000Z"   # 5:00 PM IST
        else:
            now_dt = datetime.utcnow()
            ds = now_dt.strftime("%Y%m%d")
            start_utc_str = f"{ds}T043000Z"
            end_utc_str = f"{ds}T113000Z"

        cal_details = (
            f"IPO: {name}\n"
            f"Category: {cat_disp}\n"
            f"GMP: {gmp_val} (+{gmp_pct}%)\n"
            f"Price: {price}\n"
            f"Retail: {retail_order}\n"
            f"sHNI: {shni_order}\n\n"
            f"Important: Complete your bid and authorize UPI mandate before 5:00 PM IST."
        )
        cal_params = {
            "action": "TEMPLATE",
            "text": f"Last Day: {name} IPO (Closes 5 PM)",
            "dates": f"{start_utc_str}/{end_utc_str}",
            "details": cal_details,
            "location": "Stock Broker App / BSE / NSE"
        }
        cal_url = "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(cal_params)

        # Extract raw quantities for bridge page 1-tap copy
        retail_qty_match = re.search(r"\((\d[\d,]*)\)", retail_order)
        shni_qty_match = re.search(r"\((\d[\d,]*)\)", shni_order)
        retail_num = retail_qty_match.group(1).replace(",", "") if retail_qty_match else ""
        shni_num = shni_qty_match.group(1).replace(",", "") if shni_qty_match else ""

        # Telegram callback_data limit is 64 bytes
        cb_name = name[:30].replace(":", "")
        try:
            from config import config
            bridge_base = config.bid_bridge_url
        except Exception:
            bridge_base = ""

        if bridge_base:
            bid_params = urllib.parse.urlencode({
                "name": name,
                "category": cat_disp,
                "price": price,
                "retail_qty": retail_num,
                "shni_qty": shni_num
            })
            bid_url = f"{bridge_base}?{bid_params}"
        else:
            bid_url = "https://kite.zerodha.com/bids/ipo"

        button_rows = []
        if not hide_bid_button:
            button_rows.append([
                {
                    "text": "Place Bid",
                    "url": bid_url
                }
            ])
        button_rows.append([
            {
                "text": "Mute",
                "callback_data": f"mute:user:{cb_name}"
            },
            {
                "text": "Add to Calendar",
                "url": cal_url
            }
        ])

        reply_markup = {"inline_keyboard": button_rows}
        return html_msg, reply_markup
