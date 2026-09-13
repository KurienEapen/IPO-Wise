import time
import threading
import requests
from typing import Optional, Callable, Tuple
from bot.telegram_client import TelegramClient
from database import (
    mute_ipo, unmute_ipo, get_muted_ipos, is_ipo_muted, get_settings,
    register_or_update_subscriber, get_subscriber, set_subscriber_status,
    set_subscriber_threshold, set_subscriber_sme, set_subscriber_closing_day,
    set_subscriber_bid_button
)
from config import config

def build_onboarding_view(sub: dict) -> Tuple[str, dict]:
    """Generates a high-density, institutional-grade alert configuration card
    and symmetrical inline keyboard per Impeccable standards."""
    name_disp = sub.get("first_name") or sub.get("username") or "Investor"
    status = sub.get("status", "pending")
    thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold
    is_sme = bool(sub.get("enable_sme", 0))
    is_closing = bool(sub.get("only_closing_day", 0))
    is_bid_disabled = bool(sub.get("disable_bid_button", 0))

    if status == "approved":
        status_line = "Active (Approved)"
        status_note = ""
    elif status == "pending":
        status_line = "Pending Approval"
        status_note = "<i>Account review pending. Configured parameters will activate automatically upon approval.</i>\n\n"
    elif status == "rejected":
        status_line = "Inactive (Under Review)"
        status_note = "<i>Account not currently routed for alerts. Web console approval required.</i>\n\n"
    else: # unsubscribed
        status_line = "Unsubscribed"
        status_note = "<i>Direct alerts paused. Send /subscribe to re-activate.</i>\n\n"

    sme_disp = "Enabled (Mainboard + SME)" if is_sme else "Disabled (Mainboard only)"
    timing_disp = "Closing Day Only" if is_closing else "All Open Days"
    bid_disp = "Hidden" if is_bid_disabled else "Enabled"

    card_text = (
        f"<b>IPO-WISE | Alert Preferences</b>\n\n"
        f"<b>Subscriber:</b> {name_disp}\n"
        f"<b>Status:</b> {status_line}\n"
        f"{status_note}"
        f"<b>Parameters</b>\n"
        f"• Threshold: <b>GMP ≥ {thresh}%</b>\n"
        f"• SME Coverage: <b>{sme_disp}</b>\n"
        f"• Timing: <b>{timing_disp}</b>\n"
        f"• Broker Link: <b>{bid_disp}</b>"
    )

    sme_btn = "SME: Enabled" if is_sme else "SME: Disabled"
    closing_btn = "Timing: Closing Day" if is_closing else "Timing: All Days"
    bid_btn = "Bid Link: Hidden" if is_bid_disabled else "Bid Link: Shown"

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": sme_btn, "callback_data": "cfg:sme"},
                {"text": closing_btn, "callback_data": "cfg:closing"}
            ],
            [
                {"text": bid_btn, "callback_data": "cfg:bid"},
                {"text": f"Threshold: ≥ {thresh}%", "callback_data": "cfg:threshold"}
            ],
            [
                {"text": "Check Open IPOs", "callback_data": "cfg:check"},
                {"text": "Commands", "callback_data": "cfg:help"}
            ]
        ]
    }
    return card_text, reply_markup

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

        elif cb_data.startswith("cfg:"):
            action = cb_data.split(":", 1)[1]
            sub = get_subscriber(user_id) or get_subscriber(chat_id)
            if not sub:
                sub = register_or_update_subscriber(chat_id=user_id or chat_id)
            sub_chat = sub.get("chat_id") or user_id or chat_id

            if action == "sme":
                new_val = not bool(sub.get("enable_sme", 0))
                set_subscriber_sme(sub_chat, new_val)
                toast = f"SME Alerts: {'Enabled (Mainboard + SME)' if new_val else 'Disabled (Mainboard only)'}"
                client.answer_callback_query(cb_id, toast, show_alert=False)
                sub["enable_sme"] = 1 if new_val else 0
                new_text, new_markup = build_onboarding_view(sub)
                if chat_id and message_id:
                    client.edit_message_text(chat_id, message_id, new_text, new_markup)

            elif action == "closing":
                new_val = not bool(sub.get("only_closing_day", 0))
                set_subscriber_closing_day(sub_chat, new_val)
                toast = f"Alert Timing: {'Closing Day Only' if new_val else 'All Open Days'}"
                client.answer_callback_query(cb_id, toast, show_alert=False)
                sub["only_closing_day"] = 1 if new_val else 0
                new_text, new_markup = build_onboarding_view(sub)
                if chat_id and message_id:
                    client.edit_message_text(chat_id, message_id, new_text, new_markup)

            elif action == "bid":
                new_val = not bool(sub.get("disable_bid_button", 0))
                set_subscriber_bid_button(sub_chat, new_val)
                toast = f"Broker Link: {'Hidden' if new_val else 'Enabled'}"
                client.answer_callback_query(cb_id, toast, show_alert=False)
                sub["disable_bid_button"] = 1 if new_val else 0
                new_text, new_markup = build_onboarding_view(sub)
                if chat_id and message_id:
                    client.edit_message_text(chat_id, message_id, new_text, new_markup)

            elif action == "threshold":
                curr_thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold
                info = (
                    f"Alert Threshold: GMP ≥ {curr_thresh}%\n\n"
                    "To update your threshold, send a command in this chat:\n"
                    "• /threshold <val> (e.g. /threshold 20)\n"
                    "• /threshold default (reset to system default)"
                )
                client.answer_callback_query(cb_id, info, show_alert=True)

            elif action == "refresh":
                fresh_sub = get_subscriber(sub_chat) or sub
                new_text, new_markup = build_onboarding_view(fresh_sub)
                client.answer_callback_query(cb_id, "Preferences refreshed.", show_alert=False)
                if chat_id and message_id:
                    client.edit_message_text(chat_id, message_id, new_text, new_markup)

            elif action == "check":
                client.answer_callback_query(cb_id, "Checking open IPOs...", show_alert=False)
                client.send_message(chat_id, "<i>Checking open IPOs matching criteria...</i>")
                if self.manual_check_trigger:
                    count = self.manual_check_trigger(target_chat_override=chat_id)
                    if count == 0:
                        client.send_message(chat_id, "No unmuted open IPOs currently meet your alert criteria.")
                else:
                    client.send_message(chat_id, "Check runner is currently offline.")

            elif action == "help":
                client.answer_callback_query(cb_id, "Commands list sent below.", show_alert=False)
                self._send_help(client, chat_id)

    def _send_help(self, client: TelegramClient, chat_id: str):
        reply = (
            "<b>IPO-WISE | Available Commands</b>\n\n"
            "• <code>/start</code> - Open interactive alert preferences\n"
            "• <code>/status</code> - View and adjust notification parameters\n"
            "• <code>/threshold &lt;val&gt;</code> - View or update GMP threshold\n"
            "• <code>/sme on|off</code> - Enable or disable SME IPO alerts\n"
            "• <code>/closingday on|off</code> - Limit alerts to final closing day\n"
            "• <code>/bidbutton on|off</code> - Show or hide Place Bid broker link\n"
            "• <code>/check</code> - Run instant check for active IPOs\n"
            "• <code>/unmute &lt;IPO Name&gt;</code> - Unmute an IPO to resume alerts\n"
            "• <code>/muted</code> - List currently muted IPOs\n"
            "• <code>/unsubscribe</code> - Pause direct alerts\n"
        )
        client.send_message(chat_id, reply)

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
                sub = register_or_update_subscriber(chat_id=chat_id, username=username, first_name=first_name, last_name=last_name)
                card_text, card_markup = build_onboarding_view(sub)
                client.send_message(chat_id, card_text, reply_markup=card_markup)
            else:
                reply = (
                    "<b>IPO-WISE | Automated Intelligence</b>\n\n"
                    f"Monitoring active Indian IPOs with GMP ≥ {config.gmp_threshold}%.\n\n"
                    "• For private 1-on-1 alerts, message this bot in a direct chat.\n"
                    "• <code>/check</code> - Run instant market check\n"
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
                    f"<b>Alert Threshold:</b> <b>{current_thresh}%</b>{custom_tag}\n\n"
                    f"Alerts will trigger when an IPO's Grey Market Premium meets or exceeds this cutoff.\n\n"
                    f"<b>Update threshold:</b>\n"
                    f"• <code>/threshold &lt;val&gt;</code> (e.g. <code>/threshold 20</code>)\n"
                    f"• <code>/threshold default</code> (reset to system default {config.gmp_threshold}%)"
                )
            else:
                if args.lower() in ["default", "reset"]:
                    set_subscriber_threshold(chat_id, None)
                    client.send_message(
                        chat_id,
                        f"<b>Alert Threshold Reset</b>\n\n"
                        f"Alert threshold reset to system default of <b>{config.gmp_threshold}%</b>."
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
                            f"<b>Alert Threshold Updated</b>\n\n"
                            f"Personal alert threshold set to <b>{val}%</b>.\n"
                            f"Alerts will route for open IPOs with GMP ≥ <b>{val}%</b>."
                        )
                    except ValueError:
                        client.send_message(
                            chat_id,
                            "<b>Invalid Threshold Parameter</b>\n\n"
                            "Please provide a valid percentage number. Examples:\n"
                            "• <code>/threshold 20</code>\n"
                            "• <code>/threshold 12.5</code>\n"
                            "• <code>/threshold default</code>"
                        )

        elif cmd == "/sme" and is_private:
            sub = get_subscriber(chat_id)
            if not sub or sub.get("status") != "approved":
                client.send_message(chat_id, "Account review pending. Send <code>/subscribe</code> to register.")
                return

            sub_sme = bool(sub.get("enable_sme", 0))
            sub_thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold

            arg_lower = args.lower().strip()
            if arg_lower in ["on", "enable", "yes", "true", "1"]:
                set_subscriber_sme(chat_id, True)
                client.send_message(
                    chat_id,
                    f"<b>SME Coverage Enabled</b>\n\n"
                    f"Alerts will route for both <b>Mainboard and SME IPOs</b> (GMP ≥ {sub_thresh}%).\n\n"
                    f"<i>(To disable SME coverage, send <code>/sme off</code>).</i>"
                )
            elif arg_lower in ["off", "disable", "no", "false", "0"]:
                set_subscriber_sme(chat_id, False)
                client.send_message(
                    chat_id,
                    f"<b>SME Coverage Disabled</b>\n\n"
                    f"Alerts will route for <b>Mainboard IPOs only</b> (GMP ≥ {sub_thresh}%).\n\n"
                    f"<i>(To re-enable SME coverage, send <code>/sme on</code>).</i>"
                )
            else:
                curr_status = "Enabled (Mainboard + SME)" if sub_sme else "Disabled (Mainboard only)"
                action_hint = "Send <code>/sme off</code> to disable." if sub_sme else "Send <code>/sme on</code> to enable."
                client.send_message(
                    chat_id,
                    f"<b>IPO Category Coverage</b>\n\n"
                    f"• Status: <b>{curr_status}</b>\n\n"
                    f"{action_hint}"
                )

        elif cmd in ["/closingday", "/closing", "/lastday"] and is_private:
            sub = get_subscriber(chat_id)
            if not sub or sub.get("status") != "approved":
                client.send_message(chat_id, "Account review pending. Send <code>/subscribe</code> to register.")
                return

            sub_closing = bool(sub.get("only_closing_day", 0))
            sub_sme = bool(sub.get("enable_sme", 0))
            sub_thresh = sub.get("gmp_threshold") if sub.get("gmp_threshold") is not None else config.gmp_threshold
            cat_desc = "Mainboard and SME IPOs" if sub_sme else "Mainboard IPOs"

            arg_lower = args.lower().strip()
            if arg_lower in ["on", "enable", "yes", "true", "1"]:
                set_subscriber_closing_day(chat_id, True)
                client.send_message(
                    chat_id,
                    f"<b>Closing Day Timing Enabled</b>\n\n"
                    f"Alerts will only trigger on the <b>final closing day</b> for eligible {cat_desc} (GMP ≥ {sub_thresh}%).\n\n"
                    f"<i>(To receive alerts on all open days, send <code>/closingday off</code>).</i>"
                )
            elif arg_lower in ["off", "disable", "no", "false", "0"]:
                set_subscriber_closing_day(chat_id, False)
                client.send_message(
                    chat_id,
                    f"<b>Daily Timing Enabled</b>\n\n"
                    f"Alerts will route on <b>all open days</b> for eligible {cat_desc} (GMP ≥ {sub_thresh}%).\n\n"
                    f"<i>(To limit to closing day only, send <code>/closingday on</code>).</i>"
                )
            else:
                curr_status = "Closing Day Only" if sub_closing else "All Open Days"
                action_hint = "Send <code>/closingday off</code> for all open days." if sub_closing else "Send <code>/closingday on</code> for closing day only."
                client.send_message(
                    chat_id,
                    f"<b>Alert Timing Parameter</b>\n\n"
                    f"• Timing: <b>{curr_status}</b>\n"
                    f"• Active Scope: {cat_desc}\n\n"
                    f"{action_hint}"
                )

        elif cmd in ["/bidbutton", "/placebid", "/disablebid"] and is_private:
            sub = get_subscriber(chat_id)
            if not sub:
                sub = register_or_update_subscriber(chat_id=chat_id, username=username, first_name=first_name, last_name=last_name)

            sub_bid_disabled = bool(sub.get("disable_bid_button", 0))
            arg_lower = args.lower().strip()
            if arg_lower in ["off", "disable", "hide", "no", "false", "0"]:
                set_subscriber_bid_button(chat_id, True)
                client.send_message(
                    chat_id,
                    "<b>Broker Link Disabled</b>\n\n"
                    "Alert cards will no longer include the 'Place Bid' broker link.\n\n"
                    "<i>(To re-enable, send <code>/bidbutton on</code> or adjust via <code>/status</code>).</i>"
                )
            elif arg_lower in ["on", "enable", "show", "yes", "true", "1"]:
                set_subscriber_bid_button(chat_id, False)
                client.send_message(
                    chat_id,
                    "<b>Broker Link Enabled</b>\n\n"
                    "Alert cards will now include the 1-tap 'Place Bid' broker link.\n\n"
                    "<i>(To disable, send <code>/bidbutton off</code> or adjust via <code>/status</code>).</i>"
                )
            else:
                curr_status = "Hidden" if sub_bid_disabled else "Enabled (Shown on cards)"
                action_hint = "Send <code>/bidbutton on</code> to enable." if sub_bid_disabled else "Send <code>/bidbutton off</code> to disable."
                client.send_message(
                    chat_id,
                    f"<b>Broker Link Configuration</b>\n\n"
                    f"• Status: <b>{curr_status}</b>\n\n"
                    f"Provides a direct 1-tap broker bidding bridge link on alert cards.\n\n"
                    f"{action_hint}"
                )

        elif cmd == "/unsubscribe" and is_private:
            set_subscriber_status(chat_id, "unsubscribed")
            client.send_message(chat_id, "<b>Subscription Paused</b>\n\nDirect IPO alerts are paused. Send <code>/subscribe</code> anytime to resume.")

        elif cmd == "/help":
            self._send_help(client, chat_id)

        elif cmd == "/status":
            if is_private:
                sub = get_subscriber(chat_id)
                if not sub:
                    sub = register_or_update_subscriber(chat_id=chat_id, username=username, first_name=first_name, last_name=last_name)
                card_text, card_markup = build_onboarding_view(sub)
                client.send_message(chat_id, card_text, reply_markup=card_markup)
            else:
                times = config.schedule_times
                times_str = ", ".join(times) + " IST"
                reply = (
                    f"<b>IPO-WISE | Terminal Status</b>\n\n"
                    f"• Status: Active\n"
                    f"• Schedule: Daily checks at {times_str}"
                )
                client.send_message(chat_id, reply)

        elif cmd == "/muted":
            muted_list = get_muted_ipos(chat_id=chat_id)
            if not muted_list:
                client.send_message(chat_id, "No IPO alerts are currently muted.")
            else:
                lines = [f"• <b>{m['ipo_name']}</b> ({m['action']}) - {m['created_at'][:10]}" for m in muted_list]
                reply = "<b>Muted IPOs</b>\n\n" + "\n".join(lines) + "\n\n<i>Use /unmute &lt;Name&gt; to restore alerts.</i>"
                client.send_message(chat_id, reply)

        elif cmd in ["/applied", "/ignore"]:
            action = "APPLIED" if cmd == "/applied" else "IGNORED"
            if not args:
                client.send_message(chat_id, f"Please provide the IPO name. Example: <code>{cmd} Qualiance International</code>")
                return
            mute_ipo(args, chat_id=chat_id, action=action)
            client.send_message(chat_id, f"Muted alerts for <b>{args}</b> ({action.capitalize()}).")

        elif cmd == "/unmute":
            if not args:
                client.send_message(chat_id, "Please provide the IPO name. Example: <code>/unmute Qualiance International</code>")
                return
            success = unmute_ipo(args, chat_id=chat_id)
            if success:
                client.send_message(chat_id, f"Unmuted <b>{args}</b>. Alerts will resume when criteria are met.")
            else:
                client.send_message(chat_id, f"Could not find '<b>{args}</b>' in your muted list.")

        elif cmd == "/check":
            client.send_message(chat_id, "<i>Checking open IPOs matching criteria...</i>")
            if self.manual_check_trigger:
                count = self.manual_check_trigger(target_chat_override=chat_id)
                if count == 0:
                    client.send_message(chat_id, "No unmuted open IPOs currently meet your alert criteria.")
            else:
                client.send_message(chat_id, "Check runner is currently offline.")
