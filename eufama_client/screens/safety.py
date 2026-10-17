"""The original EUFAMA Worker safety features: shift tracking with GPS
pings, the panic button and photo incident reports — unchanged in spirit
from the app this project started from, just re-plugged into the new
backend and config module."""

import os
import threading
import time

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.screenmanager import Screen
from kivy.utils import platform

from ..config import GPS_INTERVAL, load_config
from ..media_helpers import new_media_path
from ..netclient import post
from ..offline_queue import queue_flush, queue_load, queue_push, try_post

if platform == "android":
    from jnius import autoclass

    def get_gps_location():
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            activity = PythonActivity.mActivity
            location_manager = activity.getSystemService(Context.LOCATION_SERVICE)
            LocationManager = autoclass("android.location.LocationManager")
            location = location_manager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            if location is None:
                location = location_manager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            if location:
                return location.getLatitude(), location.getLongitude()
        except Exception:
            pass
        return 38.5244, -8.8882
else:
    def get_gps_location():
        import random
        return (38.5244 + random.uniform(-0.01, 0.01), -8.8882 + random.uniform(-0.01, 0.01))


KV = """
<SafetyScreen>:
    name: 'safety'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(14)

        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.16
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
            size_hint_y: 0.14
            bg_color: (0.05,0.4,0.8,1) if not root.on_shift else (0.5,0.05,0.1,1)
            on_release: root.toggle_shift()

        Widget:
            size_hint_y: 0.02

        RoundButton:
            id: panic_btn
            text: 'PANIC' if not root.sos_active else 'SOS ACTIVE'
            font_size: '26sp'
            bold: True
            bg_color: (0.5,0,0,1) if not root.sos_active else (0.8,0,0,1)
            size_hint_y: 0.3
            on_release: root.trigger_panic()

        RoundButton:
            text: 'I AM OK — Cancel Alert'
            font_size: '13sp'
            opacity: 1 if root.sos_active else 0
            disabled: not root.sos_active
            bg_color: 0,0.5,0.3,1
            size_hint_y: 0.1 if root.sos_active else 0
            on_release: root.cancel_panic()

        RoundButton:
            text: 'Report Incident (Photo)'
            font_size: '13sp'
            bg_color: 0.15, 0.15, 0.2, 1
            size_hint_y: 0.12
            on_release: root.report_incident()
"""
Builder.load_string(KV)


class SafetyScreen(Screen):
    on_shift = BooleanProperty(False)
    sos_active = BooleanProperty(False)
    status_text = StringProperty("◉ STANDBY")
    status_color = (0.4, 0.5, 0.6, 1)
    conn_text = StringProperty("")
    shift_button_text = StringProperty("▶  START SHIFT")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gps_event = None

    def toggle_shift(self):
        self.end_shift() if self.on_shift else self.start_shift()

    def start_shift(self):
        self.on_shift = True
        self.shift_button_text = "◼  END SHIFT"
        self.status_text = "◉ ON SHIFT"
        self.status_color = (0, 0.9, 0.4, 1)

        cfg = load_config()
        lat, lon = get_gps_location()
        threading.Thread(
            target=lambda: try_post("/shift/start", {
                "worker_id": cfg.get("worker_id"), "token": cfg.get("token"),
                "lat": lat, "lon": lon,
            }), daemon=True).start()

        self._gps_event = Clock.schedule_interval(self._gps_tick, GPS_INTERVAL)

    def end_shift(self):
        self.on_shift = False
        self.shift_button_text = "▶  START SHIFT"
        self.status_text = "◉ STANDBY"
        self.status_color = (0.4, 0.5, 0.6, 1)
        self.conn_text = ""

        if self._gps_event:
            self._gps_event.cancel()
            self._gps_event = None

        cfg = load_config()
        threading.Thread(
            target=lambda: try_post("/shift/end", {
                "worker_id": cfg.get("worker_id"), "token": cfg.get("token"),
            }), daemon=True).start()

    def _gps_tick(self, dt):
        threading.Thread(target=self._gps_send, daemon=True).start()

    def _gps_send(self):
        cfg = load_config()
        lat, lon = get_gps_location()
        payload = {
            "worker_id": cfg.get("worker_id"), "token": cfg.get("token"),
            "lat": lat, "lon": lon, "battery": 100,
            "status": "SOS" if self.sos_active else "OK",
        }

        q_size = len(queue_load())
        flushed = queue_flush() if q_size > 0 else 0
        ok = try_post("/ping", payload)
        ts = time.strftime("%H:%M:%S")

        if ok:
            txt = f"● Online  {ts}"
            if flushed:
                txt += f"  (+{flushed} synced)"
        else:
            queue_push(payload)
            txt = f"● Offline [{len(queue_load())} queued]  {ts}"

        Clock.schedule_once(lambda dt: setattr(self, "conn_text", txt))

    def trigger_panic(self):
        self.sos_active = True
        cfg = load_config()
        lat, lon = get_gps_location()
        threading.Thread(
            target=lambda: try_post("/sos", {
                "worker_id": cfg.get("worker_id"), "token": cfg.get("token"),
                "lat": lat, "lon": lon,
            }), daemon=True).start()

    def cancel_panic(self):
        self.sos_active = False
        cfg = load_config()
        threading.Thread(
            target=lambda: try_post("/resolve", {
                "worker_id": cfg.get("worker_id"), "token": cfg.get("token"),
            }), daemon=True).start()

    def report_incident(self):
        if platform == "android":
            try:
                from plyer import camera
                path = new_media_path("jpg")
                camera.take_picture(filename=path, on_complete=self._on_photo_taken)
                return
            except Exception:
                pass
        print("Camera not available on this platform (desktop test mode)")

    def _on_photo_taken(self, photo_path):
        cfg = load_config()
        lat, lon = get_gps_location()
        threading.Thread(
            target=lambda: try_post("/incident", {
                "worker_id": cfg.get("worker_id"), "token": cfg.get("token"),
                "lat": lat, "lon": lon, "photo_path": photo_path,
                "description": "Photo incident report",
            }), daemon=True).start()
