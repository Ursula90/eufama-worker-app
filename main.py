"""
EUFAMA CONNECT — Android App (Kivy)
EUFAMA Holding — worker messaging + safety application.

Chat, groups, photos/files, voice notes, "Buzz" nudges, VIP broadcast and
audio/video calling (via the browser's WebRTC engine), plus the original
shift/GPS/panic/incident safety features.

Hidden admin setup: tap the logo 5 times on the login screen to configure
server IP + port. Never shown to the worker during normal use — only used
once, during device provisioning, before handing the phone over.
"""

import threading

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.utils import platform

from eufama_client import contacts_cache, crypto, kv_common  # noqa: F401 — kv_common registers shared KV templates
from eufama_client.config import is_logged_in, load_config, save_config
from eufama_client.effects import trigger_buzz
from eufama_client.media_helpers import open_url_external
from eufama_client.netclient import post
from eufama_client.notifications import notify_buzz, notify_incoming_call, notify_message, notify_sos
from eufama_client.screens.admin import AdminScreen
from eufama_client.screens.chat_detail import ChatDetailScreen
from eufama_client.screens.group_create import GroupCreateScreen
from eufama_client.screens.home import HomeScreen
from eufama_client.screens.login import LoginScreen
from eufama_client.ws_client import ws_client

if platform == "android":
    from android.permissions import request_permissions, Permission

    def request_android_permissions():
        request_permissions([
            Permission.ACCESS_FINE_LOCATION,
            Permission.ACCESS_COARSE_LOCATION,
            Permission.ACCESS_BACKGROUND_LOCATION,
            Permission.CAMERA,
            Permission.RECORD_AUDIO,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.INTERNET,
            Permission.VIBRATE,
        ] + (
            [Permission.POST_NOTIFICATIONS] if hasattr(Permission, "POST_NOTIFICATIONS") else []
        ))

    def keep_screen_on():
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            WindowManager = autoclass("android.view.WindowManager$LayoutParams")
            activity.getWindow().addFlags(WindowManager.FLAG_KEEP_SCREEN_ON)
        except Exception:
            pass
else:
    def request_android_permissions():
        pass

    def keep_screen_on():
        pass


class EufamaConnectApp(App):
    in_foreground = True

    def build(self):
        Window.clearcolor = (0.02, 0.03, 0.07, 1)
        request_android_permissions()
        keep_screen_on()

        sm = ScreenManager(transition=FadeTransition(duration=0.15))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(AdminScreen(name="admin"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(ChatDetailScreen(name="chat_detail"))
        sm.add_widget(GroupCreateScreen(name="group_create"))

        self._register_global_ws_handlers()

        if is_logged_in():
            ws_client.start()
            sm.current = "home"
            threading.Thread(target=self._ensure_pubkey_uploaded, daemon=True).start()
        else:
            sm.current = "login"

        return sm

    # ── cross-screen navigation ──────────────────────────────
    def open_chat(self, conversation_id: int, title: str):
        chat_screen = self.root.get_screen("chat_detail")
        chat_screen.conversation_id = conversation_id
        chat_screen.title_text = title
        self.root.current = "chat_detail"

    def open_group_create(self):
        self.root.current = "group_create"

    def back_to_home(self):
        self.root.current = "home"

    def _ensure_pubkey_uploaded(self):
        """On every cold start where we skip straight to 'home' (already
        logged in), make sure the server has our current public key —
        covers the case of a fresh install/keypair on a device that was
        already provisioned before E2E encryption existed."""
        try:
            cfg = load_config()
            pubkey = crypto.ensure_keypair()
            post("/auth/login", {
                "worker_id": cfg.get("worker_id"), "token": cfg.get("token"), "public_key": pubkey,
            }, auth=False)
        except Exception:
            pass

    # ── background/foreground lifecycle (drives notifications) ──
    def on_pause(self):
        self.in_foreground = False
        return True  # keep running in the background instead of being stopped

    def on_resume(self):
        self.in_foreground = True

    def logout(self):
        ws_client.stop()
        cfg = load_config()
        # Keep server_ip/port so the next login doesn't need re-provisioning.
        save_config({
            "server_ip": cfg.get("server_ip"),
            "server_port": cfg.get("server_port"),
            "prefill_worker_id": cfg.get("prefill_worker_id"),
        })
        self.root.current = "login"

    # ── global realtime events (fire regardless of active screen) ─
    def _register_global_ws_handlers(self):
        ws_client.on("message", self._on_message)
        ws_client.on("buzz", self._on_buzz)
        ws_client.on("incoming_call", self._on_incoming_call)
        ws_client.on("sos_alert", self._on_sos_alert)
        ws_client.on("incident_report", self._on_incident_report)

    def _on_message(self, data):
        if self.in_foreground:
            return  # the open chat screen (if any) already renders it live
        msg = data.get("message", {})
        sender = contacts_cache.name_for(msg.get("sender_id"))
        notify_message(sender, msg)

    def _on_buzz(self, data):
        trigger_buzz(shake_target=self.root)
        if not self.in_foreground:
            notify_buzz(contacts_cache.name_for(data.get("from")))

    def _on_incoming_call(self, data):
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup

        kind = "video" if data.get("call_type") == "video" else "audio"
        box = BoxLayout(orientation="vertical", spacing=10, padding=10)
        box.add_widget(Label(text=f"Apel {kind} de la {data.get('from_name', '?')}"))
        btn_row = BoxLayout(spacing=10, size_hint_y=None, height=48)
        popup = Popup(title="Apel primit — EUFAMA Connect", content=box,
                       size_hint=(0.85, 0.35), auto_dismiss=False)

        def accept(*_):
            popup.dismiss()
            open_url_external(data["join_url"])

        def decline(*_):
            popup.dismiss()

        accept_btn = Button(text="Răspunde", background_color=(0, 0.6, 0.3, 1))
        accept_btn.bind(on_release=accept)
        decline_btn = Button(text="Refuză", background_color=(0.6, 0.1, 0.1, 1))
        decline_btn.bind(on_release=decline)
        btn_row.add_widget(accept_btn)
        btn_row.add_widget(decline_btn)
        box.add_widget(btn_row)

        trigger_buzz(shake_target=self.root)
        if not self.in_foreground:
            notify_incoming_call(data.get("from_name", "?"), data.get("call_type", "audio"))
        popup.open()

    def _on_sos_alert(self, data):
        from kivy.uix.button import Button
        from kivy.uix.popup import Popup

        trigger_buzz(shake_target=self.root)
        if not self.in_foreground:
            notify_sos(data.get("display_name", "?"), data.get("worker_id", "?"))
        msg = f"🚨 SOS — {data.get('display_name')} ({data.get('worker_id')})\nLat/Lon: {data.get('lat')}, {data.get('lon')}"
        btn = Button(text=msg, background_color=(0.6, 0, 0, 1))
        popup = Popup(title="ALERTĂ SOS", content=btn, size_hint=(0.9, 0.35))
        btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def _on_incident_report(self, data):
        from kivy.uix.button import Button
        from kivy.uix.popup import Popup

        msg = f"📸 Raport incident — {data.get('display_name')}\n{data.get('description', '')}"
        btn = Button(text=msg)
        popup = Popup(title="Raport incident", content=btn, size_hint=(0.9, 0.3))
        btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()


if __name__ == "__main__":
    EufamaConnectApp().run()
