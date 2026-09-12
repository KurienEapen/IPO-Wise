import time
import threading
import requests
from typing import Optional, Callable
from bot.telegram_client import TelegramClient
from database import (
    mute_ipo, unmute_ipo, get_muted_ipos, is_ipo_muted, get_settings,
    register_or_update_subscriber, get_subscriber, set_subscriber_status,
    set_subscriber_threshold, set_subscriber_sme
)
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
        token = config.bot_token
        if not token:
            print("[TelegramPoller] No bot token configured, polling idle.")
            return

        client = TelegramClient(token)
        # Drop pending webhook if any to prevent conflicts with getUpdates
        try:
            client.delete_webhook()
        except Exception:
            pass

        while self.running:
            try:
                # Reload token dynamically if changed in settings
                current_token = config.bot_token
                if current_token and current_token != client.token:
                    client = TelegramClient(current_token)

                if not client.token:
                    time.sleep(5)
                    continue

                url = f"{client.base_url}/getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 15}
                resp = requests.get(url, params=params, timeout=20)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        for update in updates:
                            self.last_update_id = update["update_id"]
                            self._handle_update(client, update)
                elif resp.status_code in [401, 404]:
                    time.sleep(10)
                else:
                    time.sleep(2)
            except Exception as e:
                time.sleep(3)

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
        from_user = cb.get("from", {})
        user_id = str(from_user.get("id", "")) or chat_id
        message_id = message.get("message_id")

        if cb_data.startswith("mute:"):
            parts = cb_data.split(":", 2)
            if len(parts) == 3:
                action_type = parts[1].upper() # APPLIED, IGNORED, or USER
                ipo_name = parts[2]
                
                # Mute in database specifically for this user
                db_action = "MUTED" if action_type == "USER" else action_type
                mute_ipo(ipo_name, chat_id=user_id, action=db_action)
                
                alert_text = f"Noted! Alerts for '{ipo_name}' are now muted for your account."
                client.answer_callback_query(cb_id, alert_text, show_alert=True)

                # Update Mute button to Muted while preserving Add to Calendar button
                orig_keyboard = message.get("reply_markup", {}).get("inline_keyboard", [])
                new_keyboard_rows = []
                for row in orig_keyboard:
                    new_row = []
                    for btn in row:
                        if btn.get("callback_data", "").startswith("mute:"):
                            new_row.append({
                                "text": "Muted",
                                "callback_data": f"noop:{ipo_name}"
                            })
                        else:
                            new_row.append(btn)
                    new_keyboard_rows.append(new_row)

                if not new_keyboard_rows:
                    new_keyboard_rows = [[{"text": "Muted", "callback_data": f"noop:{ipo_name}"}]]

                new_keyboard = {"inline_keyboard": new_keyboard_rows}
                if chat_id and message_id:
                    client.edit_message_reply_markup(chat_id, message_id, new_keyboard)
                return

        elif cb_data.startswith("noop:"):
            client.answer_callback_query(cb_id, "This IPO alert is already muted for you.", show_alert=False)

    def _handle_message(self, client: TelegramClient, msg: dict):
        text = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))
        chat_type = msg.get("chat", {}).get("type", "private")
        from_user = msg.get("from", {})
        username = from_user.get("username", "")
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")
        is_private = (chat_type == "private")

        if not text:
            return

        cmd = text.split()[0].lower()
        args = text[len(cmd):].strip()

        if cmd in ["/start", "/subscribe"]:
            if is_private:
                # Register or check subscriber
                sub = register_or_update_subscriber(chat_id=chat_id, username=username, first_name=first_name, last_name=last_name)
                status = sub.get("status", "pending")
                name_disp = first_name or "there"
                thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold

                if status == "approved":
                    reply = (
                        f"👋 <b>Welcome back, {name_disp}!</b>\n\n"
                        "✅ <b>You are an active, approved subscriber to IPO Wise!</b>\n"
                        f"📊 <b>Your Alert Threshold:</b> GMP ≥ <b>{thresh}%</b>\n"
                        "<i>(You will only receive alerts for open IPOs that meet or exceed this threshold)</i>\n\n"
                        "<b>Commands:</b>\n"
                        "• <code>/threshold &lt;number&gt;</code> - Change your alert threshold (e.g. <code>/threshold 20</code>)\n"
                        "• <code>/sme on|off</code> - Enable or disable SME IPO alerts (Default: Mainboard only)\n"
                        "• <code>/check</code> - Run an instant check for high GMP IPOs\n"
                        "• <code>/unmute &lt;IPO Name&gt;</code> - Unmute an IPO to resume alerts\n"
                        "• <code>/muted</code> - List your currently muted IPOs\n"
                        "• <code>/status</code> - View your subscription settings & schedule\n"
                        "• <code>/unsubscribe</code> - Stop receiving direct alerts\n"
                    )
                elif status == "pending":
                    reply = (
                        f"👋 <b>Hello {name_disp}!</b>\n\n"
                        "⏳ <b>Subscription Request Received!</b>\n"
                        "Your request to receive direct IPO notifications has been recorded and is currently awaiting administrator approval.\n\n"
                        f"📊 <b>Alert Criteria:</b> Default is GMP ≥ <b>{config.gmp_threshold}%</b>. Only IPOs meeting this threshold will trigger alerts.\n"
                        "<i>(You can customize your personal threshold using <code>/threshold &lt;number&gt;</code> once approved).</i>\n\n"
                        "You will automatically receive a message here as soon as an admin approves your access."
                    )
                elif status == "rejected":
                    reply = (
                        f"ℹ️ <b>Subscription Request Pending Review</b>\n\n"
                        "Your subscription status is currently not active. An admin can review and approve your account on the web console.\n"
                        "To re-submit a request, send <code>/subscribe</code>."
                    )
                else: # unsubscribed
                    reply = (
                        "ℹ️ <b>You are currently unsubscribed from alerts.</b>\n\n"
                        "To request subscription again, send <code>/subscribe</code>."
                    )
            else:
                reply = (
                    "👋 <b>Welcome to IPO Wise Alert Bot!</b>\n\n"
                    f"I monitor open Indian IPOs and post alerts here whenever an IPO meets GMP ≥ {config.gmp_threshold}%.\n\n"
                    "• For private 1-on-1 alerts, message me directly in a private chat!\n"
                    "• <code>/check</code> - Run an instant check\n"
                    "• <code>/status</code> - View bot configuration\n"
                )
            client.send_message(chat_id, reply)

        elif cmd in ["/threshold", "/gmp"] and is_private:
            sub = get_subscriber(chat_id)
            current_thresh = sub.get("gmp_threshold") if (sub and sub.get("gmp_threshold") is not None) else config.gmp_threshold
            if not args:
                custom_tag = " (Customized)" if (sub and sub.get("gmp_threshold") is not None) else " (System Default)"
                client.send_message(
                    chat_id,
                    f"📊 <b>Your Alert Threshold:</b> <b>{current_thresh}%</b>{custom_tag}\n\n"
                    f"You will only receive alerts when an IPO's Grey Market Premium (GMP) is at or above this percentage.\n\n"
                    f"<b>To change your threshold:</b>\n"
                    f"• Type <code>/threshold &lt;number&gt;</code> (e.g. <code>/threshold 20</code> or <code>/threshold 12.5</code>)\n"
                    f"• Type <code>/threshold default</code> to reset back to system default ({config.gmp_threshold}%)"
                )
            else:
                if args.lower() in ["default", "reset"]:
                    set_subscriber_threshold(chat_id, None)
                    client.send_message(
                        chat_id,
                        f"✅ <b>Threshold Reset!</b>\n\n"
                        f"Your alert threshold has been reset to the system default of <b>{config.gmp_threshold}%</b>."
                    )
                else:
                    try:
                        clean_val = args.replace("%", "").strip()
                        val = round(float(clean_val), 1)
                        if val < 0 or val > 500:
                            raise ValueError()
                        set_subscriber_threshold(chat_id, val)
                        client.send_message(
                            chat_id,
                            f"✅ <b>Threshold Updated!</b>\n\n"
                            f"Your personal alert threshold is now set to <b>{val}%</b>.\n"
                            f"You will only receive alerts for open IPOs with a GMP of <b>{val}% or higher</b>."
                        )
                    except ValueError:
                        client.send_message(
                            chat_id,
                            "⚠️ <b>Invalid Threshold</b>\n\n"
                            "Please enter a valid percentage number. Examples:\n"
                            "• <code>/threshold 20</code>\n"
                            "• <code>/threshold 12.5</code>\n"
                            "• <code>/threshold default</code>"
                        )

        elif cmd == "/sme" and is_private:
            sub = get_subscriber(chat_id)
            if not sub or sub.get("status") != "approved":
                client.send_message(chat_id, "ℹ️ You must have an approved subscription to configure alert categories. Send <code>/subscribe</code> to request access.")
                return

            sub_sme = bool(sub.get("enable_sme", 0))
            sub_thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold

            arg_lower = args.lower().strip()
            if arg_lower in ["on", "enable", "yes", "true", "1"]:
                set_subscriber_sme(chat_id, True)
                client.send_message(
                    chat_id,
                    f"✅ <b>SME Alerts Enabled!</b>\n\n"
                    f"You will now receive alerts for both <b>Mainboard and SME IPOs</b> that meet your threshold (GMP ≥ {sub_thresh}%).\n\n"
                    f"<i>(To turn off SME alerts anytime, send <code>/sme off</code>).</i>"
                )
            elif arg_lower in ["off", "disable", "no", "false", "0"]:
                set_subscriber_sme(chat_id, False)
                client.send_message(
                    chat_id,
                    f"🚫 <b>SME Alerts Disabled.</b>\n\n"
                    f"You will only receive alerts for <b>Mainboard IPOs</b> (GMP ≥ {sub_thresh}%).\n\n"
                    f"<i>(To re-enable SME alerts, send <code>/sme on</code>).</i>"
                )
            else:
                curr_status = "Subscribed (Active)" if sub_sme else "Disabled"
                action_hint = "Send <code>/sme off</code> to disable SME alerts." if sub_sme else "Send <code>/sme on</code> to subscribe to SME IPOs."
                client.send_message(
                    chat_id,
                    f"🏢 <b>Category Subscriptions</b>\n\n"
                    f"• <b>Mainboard IPOs:</b> Subscribed (Default)\n"
                    f"• <b>SME IPOs:</b> <b>{curr_status}</b>\n\n"
                    f"{action_hint}"
                )

        elif cmd == "/unsubscribe" and is_private:
            set_subscriber_status(chat_id, "unsubscribed")
            client.send_message(chat_id, "🔕 <b>You have unsubscribed.</b> You will no longer receive direct IPO alerts. You can resubscribe anytime by sending <code>/subscribe</code>.")

        elif cmd == "/help":
            reply = (
                "👋 <b>IPO Wise Alert Bot Commands</b>\n\n"
                "• <code>/threshold &lt;val&gt;</code> - View or change your personal GMP alert threshold\n"
                "• <code>/sme on|off</code> - Enable or disable SME IPO alerts\n"
                "• <code>/check</code> - Run an instant check for high GMP IPOs\n"
                "• <code>/status</code> - View your subscription settings & schedule\n"
                "• <code>/subscribe</code> - Request personal direct alerts\n"
                "• <code>/unmute &lt;IPO Name&gt;</code> - Unmute an IPO to resume alerts\n"
                "• <code>/muted</code> - List your currently muted IPOs\n"
                "• <code>/unsubscribe</code> - Stop receiving direct alerts\n"
            )
            client.send_message(chat_id, reply)

        elif cmd == "/status":
            times = config.schedule_times
            times_str = ", ".join(times) + " IST"
            
            if is_private:
                sub = get_subscriber(chat_id)
                if sub and sub.get("status") == "approved":
                    user_thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold
                    sme_status = "Subscribed" if bool(sub.get("enable_sme", 0)) else "Disabled (/sme on to enable)"
                    reply = (
                        f"<b>Subscription Status</b>\n\n"
                        f"• Status: Active (Approved)\n"
                        f"• Alert Threshold: GMP ≥ {user_thresh}%\n"
                        f"• Mainboard IPOs: Subscribed\n"
                        f"• SME IPOs: {sme_status}\n"
                        f"• Schedule: Daily checks at {times_str}\n\n"
                        f"<i>Tip: Use <code>/threshold &lt;number&gt;</code> or <code>/sme on|off</code> to customize your alerts.</i>"
                    )
                elif sub and sub.get("status") == "pending":
                    reply = (
                        f"<b>Subscription Status</b>\n\n"
                        f"• Status: Pending Approval\n"
                        f"• Mainboard IPOs: Subscribed by default once approved\n"
                        f"• SME IPOs: Optional (/sme on)\n"
                        f"• Schedule: Daily checks at {times_str}\n\n"
                        f"<i>Your request is awaiting admin approval.</i>"
                    )
                else:
                    reply = (
                        f"<b>IPO Wise Status</b>\n\n"
                        f"• Status: Not Subscribed\n"
                        f"• Schedule: Daily checks at {times_str}\n\n"
                        f"<i>Send <code>/subscribe</code> to request direct IPO alerts.</i>"
                    )
            else:
                reply = (
                    f"<b>IPO Wise Alert Bot</b>\n\n"
                    f"• Status: Active\n"
                    f"• Schedule: Daily checks at {times_str}"
                )
            client.send_message(chat_id, reply)

        elif cmd == "/muted":
            muted_list = get_muted_ipos(chat_id=chat_id)
            if not muted_list:
                client.send_message(chat_id, "ℹ️ You have no currently muted IPOs.")
            else:
                lines = [f"• <b>{m['ipo_name']}</b> ({m['action']}) - {m['created_at'][:10]}" for m in muted_list]
                reply = "🔕 <b>Your Muted IPOs:</b>\n\n" + "\n".join(lines) + "\n\n<i>Use /unmute &lt;Name&gt; to restore alerts.</i>"
                client.send_message(chat_id, reply)

        elif cmd in ["/applied", "/ignore"]:
            action = "APPLIED" if cmd == "/applied" else "IGNORED"
            if not args:
                client.send_message(chat_id, f"⚠️ Please provide the IPO name. Example: <code>{cmd} Qualiance International</code>")
                return
            mute_ipo(args, chat_id=chat_id, action=action)
            client.send_message(chat_id, f"✅ Muted alerts for <b>{args}</b> ({action.capitalize()}).")

        elif cmd == "/unmute":
            if not args:
                client.send_message(chat_id, "⚠️ Please provide the IPO name. Example: <code>/unmute Qualiance International</code>")
                return
            success = unmute_ipo(args, chat_id=chat_id)
            if success:
                client.send_message(chat_id, f"✅ Unmuted <b>{args}</b>. Alerts will resume if it meets criteria.")
            else:
                client.send_message(chat_id, f"ℹ️ Could not find '<b>{args}</b>' in your muted list.")

        elif cmd == "/check":
            client.send_message(chat_id, "🔍 <i>Checking for open IPOs matching criteria...</i>")
            if self.manual_check_trigger:
                count = self.manual_check_trigger(target_chat_override=chat_id)
                if count == 0:
                    client.send_message(chat_id, "ℹ️ No unmuted open IPOs currently meet the GMP threshold.")
            else:
                client.send_message(chat_id, "⚠️ Check runner is not connected.")
