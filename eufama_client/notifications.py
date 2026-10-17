"""Local notifications for events that arrive while EUFAMA Connect is
backgrounded (another app in front, or the screen off but the process
still alive). Uses plyer's cross-platform notification facade.

Honest limitation (see README): this only fires while our process is
still running. It does not wake the app from a fully killed/doze-
suspended state the way Firebase Cloud Messaging push does — that would
need a Firebase project, which only the account holder can create."""

_MEDIA_LABEL = {"image": "📷 Fotografie", "file": "📎 Fișier", "voice": "🎙 Mesaj vocal"}


def notify(title: str, message: str):
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="EUFAMA Connect", timeout=10)
    except Exception:
        pass


def notify_message(sender_name: str, msg: dict):
    if msg.get("encrypted"):
        body = "🔒 Mesaj criptat"
    elif msg.get("type") == "text":
        body = msg.get("body") or ""
    else:
        body = _MEDIA_LABEL.get(msg.get("type"), msg.get("type", ""))
    notify(f"Mesaj de la {sender_name}", body[:120])


def notify_buzz(sender_name: str):
    notify("Buzz!", f"{sender_name} te-a buzz-uit")


def notify_incoming_call(sender_name: str, call_type: str):
    kind = "video" if call_type == "video" else "audio"
    notify("Apel primit", f"Apel {kind} de la {sender_name}")


def notify_sos(display_name: str, worker_id: str):
    notify("🚨 ALERTĂ SOS", f"{display_name} ({worker_id}) a declanșat panica")
