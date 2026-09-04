import time
import threading
import requests
from typing import Optional, Callable
from bot.telegram_client import TelegramClient
from database import mute_ipo, unmute_ipo, get_muted_ipos, is_ipo_muted, get_settings
from config import config

class BotUpdatePoller:
    def __init__(self, manual_check_trigger: Optional[Callable] = None):
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_update_id = 0
        self.manual_check_trigger = manual_check_trigger

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        print("[TelegramPoller] Started background polling.")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        print("[TelegramPoller] Stopped polling.")

    def _poll_loop(self):
        while self.running:
            token = config.bot_token
            if not token:
                time.sleep(5)
                continue

            client = TelegramClient(token)
            try:
                params = {
                    "offset": self.last_update_id + 1,
                    "timeout": 15,
                    "allowed_updates": ["message", "callback_query"]
                }
                resp = requests.get(f"{client.base_url}/getUpdates", params=params, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            self.last_update_id = update["update_id"]
                            self._handle_update(client, update)
                elif resp.status_code == 401 or resp.status_code == 404:
                    # Invalid token, sleep longer
                    time.sleep(15)
                else:
                    time.sleep(3)
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                # transient network error
                time.sleep(4)

    def _handle_update(self, client: TelegramClient, update: dict):
        if "callback_query" in update:
            self._handle_callback(client, update["callback_query"])
        elif "message" in update:
            self._handle_message(client, update["message"])

    def _handle_callback(self, client: TelegramClient, cb: dict):
        cb_id = cb.get("id")
        cb_data = cb.get("data", "")
        message = cb.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        message_id = message.get("message_id")

        if cb_data.startswith("mute:"):
            parts = cb_data.split(":", 2)
            if len(parts) == 3:
                action_type = parts[1].upper() # APPLIED or IGNORED
                ipo_name = parts[2]
                
                # Mute in database
                mute_ipo(ipo_name, action=action_type)
                action_desc = "Applied" if action_type == "APPLIED" else "Ignored"
                
                alert_text = f"✅ Noted! Alerts for '{ipo_name}' are now muted ({action_desc})."
                client.answer_callback_query(cb_id, alert_text, show_alert=True)

                # Update button in message to show muted state
                new_keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": f"🔒 Muted ({action_desc})",
                                "callback_data": f"noop:{ipo_name}"
                            }
                        ]
                    ]
                }
                if chat_id and message_id:
                    client.edit_message_reply_markup(chat_id, message_id, new_keyboard)
                return

        elif cb_data.startswith("noop:"):
            client.answer_callback_query(cb_id, "This IPO alert is already muted.", show_alert=False)

    def _handle_message(self, client: TelegramClient, msg: dict):
        text = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not text:
            return

        cmd = text.split()[0].lower()
        args = text[len(cmd):].strip()

        if cmd in ["/start", "/help"]:
            reply = (
                "👋 <b>Welcome to IPO Wise Alert Bot!</b>\n\n"
                "I monitor open Indian IPOs and alert you when an IPO meets your GMP criteria.\n\n"
                "<b>Available Commands:</b>\n"
                "• <code>/check</code> - Run an instant check for high GMP IPOs\n"
                "• <code>/applied &lt;IPO Name&gt;</code> - Mark an IPO as applied to mute further alerts\n"
                "• <code>/ignore &lt;IPO Name&gt;</code> - Ignore an IPO to mute further alerts\n"
                "• <code>/unmute &lt;IPO Name&gt;</code> - Unmute an IPO to resume alerts\n"
                "• <code>/muted</code> - List all currently muted IPOs\n"
                "• <code>/status</code> - View bot configuration and schedule\n"
            )
            client.send_message(chat_id, reply)

        elif cmd == "/status":
            settings = get_settings()
            enabled = "✅ Enabled" if config.is_enabled else "⏸️ Disabled"
            sme_status = "✅ Enabled" if config.enable_sme_alerts else "🚫 Disabled"
            threshold = config.gmp_threshold
            times = config.schedule_times
            target_chat = config.chat_id or "Not configured"
            
            reply = (
                f"⚙️ <b>IPO Wise Bot Status</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Status:</b> {enabled}\n"
                f"• <b>SME Alerts:</b> {sme_status}\n"
                f"• <b>GMP Threshold:</b> &gt; {threshold}%\n"
                f"• <b>Scheduled Check Times:</b> {', '.join(times)}\n"
                f"• <b>Target Alert Channel/Chat:</b> <code>{target_chat}</code>\n"
                f"• <b>Last Check:</b> {settings.get('last_check_at', 'None')} ({settings.get('last_check_status', 'Idle')})\n"
            )
            client.send_message(chat_id, reply)

        elif cmd == "/muted":
            muted_list = get_muted_ipos()
            if not muted_list:
                client.send_message(chat_id, "ℹ️ No IPOs are currently muted.")
            else:
                lines = [f"• <b>{m['ipo_name']}</b> ({m['action']}) - {m['created_at'][:10]}" for m in muted_list]
                reply = "🔕 <b>Currently Muted IPOs:</b>\n\n" + "\n".join(lines) + "\n\n<i>Use /unmute &lt;Name&gt; to restore alerts.</i>"
                client.send_message(chat_id, reply)

        elif cmd in ["/applied", "/ignore"]:
            action = "APPLIED" if cmd == "/applied" else "IGNORED"
            if not args:
                client.send_message(chat_id, f"⚠️ Please provide the IPO name. Example: <code>{cmd} Qualiance International</code>")
                return
            mute_ipo(args, action=action)
            client.send_message(chat_id, f"✅ Muted alerts for <b>{args}</b> ({action.capitalize()}).")

        elif cmd == "/unmute":
            if not args:
                client.send_message(chat_id, "⚠️ Please provide the IPO name. Example: <code>/unmute Qualiance International</code>")
                return
            success = unmute_ipo(args)
            if success:
                client.send_message(chat_id, f"✅ Unmuted <b>{args}</b>. Alerts will resume if it meets criteria.")
            else:
                client.send_message(chat_id, f"ℹ️ Could not find '<b>{args}</b>' in the muted list.")

        elif cmd == "/check":
            client.send_message(chat_id, "🔍 <i>Checking for open IPOs matching criteria...</i>")
            if self.manual_check_trigger:
                count = self.manual_check_trigger(target_chat_override=chat_id)
                if count == 0:
                    client.send_message(chat_id, "ℹ️ No unmuted open IPOs currently meet the GMP threshold.")
            else:
                client.send_message(chat_id, "⚠️ Check runner is not connected.")
