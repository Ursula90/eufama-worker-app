"""
EUFAMA WORKER — Android App (Kivy)
EUFAMA Holding — Worker Safety Application

Hidden admin setup: tap the logo 5 times to configure server IP + worker token.
This screen is NEVER shown to the worker during normal use — only Valy
accesses it once, during device provisioning, before handing the phone over.
"""

import json
import os
import time
import threading
import hashlib
import hmac
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.core.window import Window
from kivy.utils import platform

import urllib.request
import urllib.error

# ── ANDROID PERMISSIONS ───────────────────────────────────
if platform == "android":
    from android.permissions import request_permissions, Permission
    from jnius import autoclass

    def request_android_permissions():
        request_permissions([
            Permission.ACCESS_FINE_LOCATION,
            Permission.ACCESS_COARSE_LOCATION,
            Permission.ACCESS_BACKGROUND_LOCATION,
            Permission.CAMERA,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.INTERNET,
        ])

    def get_gps_location():
        """Get real GPS via Android LocationManager."""
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            activity = PythonActivity.mActivity
            location_manager = activity.getSystemService(Context.LOCATION_SERVICE)
            LocationManager = autoclass("android.location.LocationManager")
            location = location_manager.getLastKnownLocation(
                LocationManager.GPS_PROVIDER
            )
            if location is None:
                location = location_manager.getLastKnownLocation(
                    LocationManager.NETWORK_PROVIDER
                )
            if location:
                return location.getLatitude(), location.getLongitude()
        except Exception:
            pass
        return 38.5244, -8.8882  # fallback default

    def keep_screen_on():
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            WindowManager = autoclass("android.view.WindowManager$LayoutParams")
            activity.getWindow().addFlags(WindowManager.FLAG_KEEP_SCREEN_ON)
        except Exception:
            pass
else:
    def request_android_permissions():
        pass

    def get_gps_location():
        import random
        return (38.5244 + random.uniform(-0.01, 0.01),
                -8.8882 + random.uniform(-0.01, 0.01))

    def keep_screen_on():
        pass

# ── STORAGE PATHS ──────────────────────────────────────────
if platform == "android":
    from android.storage import app_storage_path
    APP_DIR = app_storage_path()
else:
    APP_DIR = os.path.expanduser("~/.eufama_worker")
    os.makedirs(APP_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
QUEUE_FILE  = os.path.join(APP_DIR, "offline_queue.json")

GPS_INTERVAL = 30  # seconds

# ── CONFIG ──────────────────────────────────────────────────
def load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

# ── OFFLINE QUEUE ───────────────────────────────────────────
def queue_load() -> list:
    try:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def queue_save(entries: list):
    try:
        entries = entries[-500:]
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f)
    except Exception:
        pass

def queue_push(payload: dict):
    q = queue_load()
    payload["queued_at"] = datetime.now().isoformat()
    q.append(payload)
    queue_save(q)

# ── HTTP HELPERS ────────────────────────────────────────────
def post(server_ip: str, server_port: int, endpoint: str, payload: dict) -> bool:
    try:
        url = f"http://{server_ip}:{server_port}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False

def queue_flush(server_ip: str, server_port: int) -> int:
    q = queue_load()
    if not q:
        return 0
    sent = 0
    remaining = []
    for entry in q:
        if post(server_ip, server_port, "/ping", entry):
            sent += 1
        else:
            remaining.append(entry)
        time.sleep(0.2)
    queue_save(remaining)
    return sent

# ── KV LAYOUT (UI definition) ──────────────────────────────
KV = """
#:import dp kivy.metrics.dp

<RoundButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: self.bg_color if hasattr(self, 'bg_color') else (0.05, 0.4, 0.8, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12,]

<LoginScreen>:
    name: 'login'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.02, 0.03, 0.07, 1
            Rectangle:
                pos: self.pos
                size: self.size
        padding: dp(30)
        spacing: dp(16)

        Widget:
            size_hint_y: 0.15

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
            text: 'Safety System'
            font_size: '14sp'
            color: 0.5, 0.6, 0.8, 1
            size_hint_y: 0.08

        Widget:
            size_hint_y: 0.1

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

<MainScreen>:
    name: 'main'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.02, 0.03, 0.07, 1
            Rectangle:
                pos: self.pos
                size: self.size
        padding: dp(20)
        spacing: dp(14)

        BoxLayout:
            size_hint_y: 0.1
            Label:
                text: 'EUFAMA SAFETY'
                font_size: '18sp'
                bold: True
                color: 0, 0.7, 1, 1
            Label:
                text: root.worker_id
                font_size: '12sp'
                color: 0.5, 0.6, 0.8, 1

        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.15
            canvas.before:
                Color:
                    rgba: 0.06, 0.08, 0.13, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [10,]
            Label:
                id: status_label
                text: root.status_text
                font_size: '16sp'
                bold: True
                color: root.status_color
            Label:
                id: conn_label
                text: root.conn_text
                font_size: '11sp'
                color: 0.5, 0.6, 0.8, 1

        RoundButton:
            id: shift_btn
            text: root.shift_button_text
            font_size: '17sp'
            bold: True
            size_hint_y: 0.13
            bg_color: (0.05,0.4,0.8,1) if not root.on_shift else (0.5,0.05,0.1,1)
            on_release: root.toggle_shift()

        Widget:
            size_hint_y: 0.03

        RoundButton:
            id: panic_btn
            text: 'PANIC' if not root.sos_active else 'SOS ACTIVE'
            font_size: '26sp'
            bold: True
            bg_color: (0.5,0,0,1) if not root.sos_active else (0.8,0,0,1)
            size_hint_y: 0.28
            on_release: root.trigger_panic()

        RoundButton:
            text: 'I AM OK — Cancel Alert'
            font_size: '13sp'
            opacity: 1 if root.sos_active else 0
            disabled: not root.sos_active
            bg_color: 0,0.5,0.3,1
            size_hint_y: 0.08 if root.sos_active else 0
            on_release: root.cancel_panic()

        RoundButton:
            text: 'Report Incident (Photo)'
            font_size: '13sp'
            bg_color: 0.15, 0.15, 0.2, 1
            size_hint_y: 0.1
            on_release: root.report_incident()

        Widget:
            size_hint_y: 0.05

        Button:
            text: 'Logout'
            font_size: '11sp'
            color: 0.5, 0.6, 0.8, 1
            background_color: 0,0,0,0
            background_normal: ''
            size_hint_y: 0.06
            on_release: root.logout()

<AdminScreen>:
    name: 'admin'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.02, 0.03, 0.07, 1
            Rectangle:
                pos: self.pos
                size: self.size
        padding: dp(24)
        spacing: dp(12)

        Label:
            text: 'ADMIN SETUP'
            font_size: '20sp'
            bold: True
            color: 1, 0.2, 0.2, 1
            size_hint_y: 0.1

        Label:
            text: 'Server IP Address'
            font_size: '12sp'
            color: 0.6, 0.7, 0.85, 1
            size_hint_y: 0.05
            halign: 'left'
            text_size: self.size

        TextInput:
            id: server_ip_input
            multiline: False
            font_size: '15sp'
            size_hint_y: 0.08
            background_color: 0.06, 0.08, 0.13, 1
            foreground_color: 0.9, 0.93, 0.96, 1

        Label:
            text: 'Server Port'
            font_size: '12sp'
            color: 0.6, 0.7, 0.85, 1
            size_hint_y: 0.05
            halign: 'left'
            text_size: self.size

        TextInput:
            id: server_port_input
            multiline: False
            font_size: '15sp'
            text: '8765'
            size_hint_y: 0.08
            background_color: 0.06, 0.08, 0.13, 1
            foreground_color: 0.9, 0.93, 0.96, 1

        Label:
            text: 'Pre-fill Worker ID (optional)'
            font_size: '12sp'
            color: 0.6, 0.7, 0.85, 1
            size_hint_y: 0.05
            halign: 'left'
            text_size: self.size

        TextInput:
            id: prefill_worker_input
            multiline: False
            font_size: '15sp'
            size_hint_y: 0.08
            background_color: 0.06, 0.08, 0.13, 1
            foreground_color: 0.9, 0.93, 0.96, 1

        RoundButton:
            text: 'SAVE & EXIT TO LOGIN'
            font_size: '15sp'
            bold: True
            size_hint_y: 0.1
            on_release: root.save_admin_config()

        Label:
            id: admin_status
            text: ''
            font_size: '11sp'
            color: 0, 0.8, 0.4, 1
            size_hint_y: 0.08

        Widget:
            size_hint_y: 0.2
"""

# ── SCREENS ─────────────────────────────────────────────────
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tap_count = 0
        self._last_tap = 0

    def on_logo_tap(self):
        """Tap logo 5 times within 3 seconds to open hidden admin screen."""
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
        if not wid or not token:
            self.ids.error_label.text = "// Enter Worker ID and Token"
            return

        cfg = load_config()
        if not cfg.get("server_ip"):
            self.ids.error_label.text = "// Server not configured. Contact IT."
            return

        cfg["worker_id"] = wid
        cfg["token"] = token
        save_config(cfg)

        main_screen = self.manager.get_screen("main")
        main_screen.worker_id = wid
        main_screen.token = token
        main_screen.server_ip = cfg.get("server_ip")
        main_screen.server_port = int(cfg.get("server_port", 8765))
        self.manager.current = "main"


class MainScreen(Screen):
    worker_id     = StringProperty("")
    token         = StringProperty("")
    server_ip     = StringProperty("")
    server_port   = NumericProperty(8765)
    on_shift      = BooleanProperty(False)
    sos_active    = BooleanProperty(False)
    status_text   = StringProperty("◉ STANDBY")
    status_color  = (0.4, 0.5, 0.6, 1)
    conn_text     = StringProperty("")
    shift_button_text = StringProperty("▶  START SHIFT")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gps_event = None

    def toggle_shift(self):
        if not self.on_shift:
            self.start_shift()
        else:
            self.end_shift()

    def start_shift(self):
        self.on_shift = True
        self.shift_button_text = "◼  END SHIFT"
        self.status_text = "◉ ON SHIFT"
        self.status_color = (0, 0.9, 0.4, 1)

        lat, lon = get_gps_location()
        threading.Thread(
            target=lambda: post(self.server_ip, self.server_port,
                "/shift/start",
                {"worker_id": self.worker_id, "token": self.token,
                 "lat": lat, "lon": lon}),
            daemon=True).start()

        self._gps_event = Clock.schedule_interval(
            self._gps_tick, GPS_INTERVAL)

    def end_shift(self):
        self.on_shift = False
        self.shift_button_text = "▶  START SHIFT"
        self.status_text = "◉ STANDBY"
        self.status_color = (0.4, 0.5, 0.6, 1)
        self.conn_text = ""

        if self._gps_event:
            self._gps_event.cancel()
            self._gps_event = None

        threading.Thread(
            target=lambda: post(self.server_ip, self.server_port,
                "/shift/end",
                {"worker_id": self.worker_id, "token": self.token}),
            daemon=True).start()

    def _gps_tick(self, dt):
        threading.Thread(target=self._gps_send, daemon=True).start()

    def _gps_send(self):
        lat, lon = get_gps_location()
        payload = {
            "worker_id": self.worker_id, "token": self.token,
            "lat": lat, "lon": lon, "battery": 100,
            "status": "SOS" if self.sos_active else "OK"
        }

        # Flush queue first
        q_size = len(queue_load())
        flushed = 0
        if q_size > 0:
            flushed = queue_flush(self.server_ip, self.server_port)

        ok = post(self.server_ip, self.server_port, "/ping", payload)
        ts = datetime.now().strftime("%H:%M:%S")

        if ok:
            txt = f"● Online  {ts}"
            if flushed:
                txt += f"  (+{flushed} synced)"
        else:
            queue_push(payload)
            q_total = len(queue_load())
            txt = f"● Offline [{q_total} queued]  {ts}"

        Clock.schedule_once(lambda dt: setattr(self, "conn_text", txt))

    def trigger_panic(self):
        self.sos_active = True
        lat, lon = get_gps_location()
        threading.Thread(
            target=lambda: post(self.server_ip, self.server_port,
                "/sos",
                {"worker_id": self.worker_id, "token": self.token,
                 "lat": lat, "lon": lon}),
            daemon=True).start()

    def cancel_panic(self):
        self.sos_active = False
        threading.Thread(
            target=lambda: post(self.server_ip, self.server_port,
                "/resolve",
                {"worker_id": self.worker_id, "token": self.token}),
            daemon=True).start()

    def report_incident(self):
        """Opens camera for incident photo report — location auto-tagged."""
        if platform == "android":
            try:
                from plyer import camera
                photo_path = os.path.join(APP_DIR, f"incident_{int(time.time())}.jpg")
                camera.take_picture(filename=photo_path,
                                    on_complete=self._on_photo_taken)
            except Exception:
                pass
        else:
            print("Camera not available on this platform (desktop test mode)")

    def _on_photo_taken(self, photo_path):
        lat, lon = get_gps_location()
        threading.Thread(
            target=lambda: post(self.server_ip, self.server_port,
                "/incident",
                {"worker_id": self.worker_id, "token": self.token,
                 "lat": lat, "lon": lon,
                 "photo_path": photo_path,
                 "description": "Photo incident report"}),
            daemon=True).start()

    def logout(self):
        if self.on_shift:
            self.end_shift()
        self.manager.current = "login"


class AdminScreen(Screen):
    def on_pre_enter(self):
        cfg = load_config()
        self.ids.server_ip_input.text = cfg.get("server_ip", "")
        self.ids.server_port_input.text = str(cfg.get("server_port", 8765))
        self.ids.prefill_worker_input.text = cfg.get("prefill_worker_id", "")

    def save_admin_config(self):
        ip   = self.ids.server_ip_input.text.strip()
        port = self.ids.server_port_input.text.strip()
        prefill = self.ids.prefill_worker_input.text.strip()

        if not ip:
            self.ids.admin_status.text = "// Server IP required"
            self.ids.admin_status.color = (1, 0.3, 0.3, 1)
            return

        cfg = load_config()
        cfg["server_ip"] = ip
        cfg["server_port"] = int(port) if port.isdigit() else 8765
        cfg["prefill_worker_id"] = prefill
        save_config(cfg)

        self.ids.admin_status.text = "Saved. Returning to login..."
        self.ids.admin_status.color = (0, 0.8, 0.4, 1)
        Clock.schedule_once(lambda dt: setattr(
            self.manager, "current", "login"), 1.5)


class EufamaWorkerApp(App):
    def build(self):
        Window.clearcolor = (0.02, 0.03, 0.07, 1)
        request_android_permissions()
        keep_screen_on()

        Builder.load_string(KV)
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(AdminScreen(name="admin"))
        return sm


if __name__ == "__main__":
    EufamaWorkerApp().run()
