import threading
import time

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen

from ..config import load_config, update_config
from ..netclient import ApiError, post
from ..ws_client import ws_client

KV = """
<LoginScreen>:
    name: 'login'
    DarkScreen:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(30)
            spacing: dp(16)

            Widget:
                size_hint_y: 0.12

            Button:
                id: logo_btn
                text: 'EUFAMA'
                font_size: '32sp'
                bold: True
                color: 0, 0.7, 1, 1
                background_color: 0,0,0,0
                background_normal: ''
                size_hint_y: 0.12
                on_release: root.on_logo_tap()

            Label:
                text: 'Connect — Worker App'
                font_size: '14sp'
                color: 0.5, 0.6, 0.8, 1
                size_hint_y: 0.08

            Widget:
                size_hint_y: 0.06

            Label:
                text: 'Worker ID'
                font_size: '13sp'
                color: 0.6, 0.7, 0.85, 1
                size_hint_y: 0.05
                halign: 'left'
                text_size: self.size

            TextInput:
                id: worker_id_input
                multiline: False
                font_size: '16sp'
                size_hint_y: 0.08
                background_color: 0.06, 0.08, 0.13, 1
                foreground_color: 0.9, 0.93, 0.96, 1
                cursor_color: 0, 0.7, 1, 1
                padding: [dp(12), dp(12)]

            Label:
                text: 'Access Token'
                font_size: '13sp'
                color: 0.6, 0.7, 0.85, 1
                size_hint_y: 0.05
                halign: 'left'
                text_size: self.size

            TextInput:
                id: token_input
                multiline: False
                password: True
                font_size: '16sp'
                size_hint_y: 0.08
                background_color: 0.06, 0.08, 0.13, 1
                foreground_color: 0.9, 0.93, 0.96, 1
                cursor_color: 0, 0.7, 1, 1
                padding: [dp(12), dp(12)]

            RoundButton:
                id: login_btn
                text: 'LOGIN'
                font_size: '16sp'
                bold: True
                color: 1,1,1,1
                size_hint_y: 0.1
                on_release: root.do_login()

            Label:
                id: error_label
                text: ''
                font_size: '12sp'
                color: 1, 0.3, 0.3, 1
                size_hint_y: 0.08

            Widget:
                size_hint_y: 0.2
"""
Builder.load_string(KV)


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tap_count = 0
        self._last_tap = 0

    def on_logo_tap(self):
        now = time.time()
        if now - self._last_tap > 3:
            self._tap_count = 0
        self._tap_count += 1
        self._last_tap = now
        if self._tap_count >= 5:
            self._tap_count = 0
            self.manager.current = "admin"

    def on_pre_enter(self):
        cfg = load_config()
        prefill = cfg.get("prefill_worker_id", "")
        if prefill and not self.ids.worker_id_input.text:
            self.ids.worker_id_input.text = prefill

    def do_login(self):
        wid = self.ids.worker_id_input.text.strip()
        token = self.ids.token_input.text.strip()
        self.ids.error_label.text = ""

        if not wid or not token:
            self.ids.error_label.text = "// Enter Worker ID and Token"
            return

        cfg = load_config()
        if not cfg.get("server_ip"):
            self.ids.error_label.text = "// Server not configured. Contact IT."
            return

        self.ids.login_btn.disabled = True
        self.ids.login_btn.text = "..."
        threading.Thread(target=self._login_thread, args=(wid, token), daemon=True).start()

    def _login_thread(self, wid, token):
        try:
            resp = post("/auth/login", {"worker_id": wid, "token": token}, auth=False)
            user = resp["user"]
            update_config(
                worker_id=wid, token=token,
                user_id=user["id"], display_name=user["display_name"], role=user["role"],
            )
            Clock.schedule_once(lambda dt: self._login_ok())
        except ApiError as e:
            msg = "Worker ID sau token incorect." if e.status == 401 else f"Eroare server: {e.message}"
            Clock.schedule_once(lambda dt: self._login_failed(msg))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._login_failed(f"Eroare de conexiune: {e}"))

    def _login_ok(self):
        self.ids.login_btn.disabled = False
        self.ids.login_btn.text = "LOGIN"
        ws_client.start()
        self.manager.current = "home"

    def _login_failed(self, message):
        self.ids.login_btn.disabled = False
        self.ids.login_btn.text = "LOGIN"
        self.ids.error_label.text = f"// {message}"
