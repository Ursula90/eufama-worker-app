"""Background WebSocket connection to /ws/app.

Runs in its own thread (websocket-client's run_forever), auto-reconnects
with backoff, and re-dispatches every incoming event onto the Kivy main
thread via Clock so screens can update widgets safely. Screens subscribe
with `ws_client.on("message", callback)` and should unsubscribe with
`.off(...)` when they leave, to avoid piling up dead callbacks.
"""

import json
import threading
import time

import websocket
from kivy.clock import Clock

from .config import load_config


class WSClient:
    def __init__(self):
        self._listeners: dict[str, list] = {}
        self._ws = None
        self._thread = None
        self._stop = False

    def on(self, event_type: str, callback):
        self._listeners.setdefault(event_type, []).append(callback)

    def off(self, event_type: str, callback):
        lst = self._listeners.get(event_type)
        if lst and callback in lst:
            lst.remove(callback)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _run_forever(self):
        backoff = 2
        while not self._stop:
            cfg = load_config()
            ip, port = cfg.get("server_ip"), cfg.get("server_port", 8765)
            wid, token = cfg.get("worker_id"), cfg.get("token")
            if not (ip and wid and token):
                time.sleep(3)
                continue

            url = f"ws://{ip}:{port}/ws/app?worker_id={wid}&token={token}"
            try:
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_close=self._on_close,
                )
                backoff = 2
                self._ws.run_forever(ping_interval=25, ping_timeout=10)
            except Exception:
                pass

            if self._stop:
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def _on_open(self, ws):
        self._dispatch("_connected", {})

    def _on_close(self, ws, *_args):
        self._dispatch("_disconnected", {})

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception:
            return
        self._dispatch(data.get("type"), data)

    def _dispatch(self, event_type, data):
        for cb in list(self._listeners.get(event_type, [])):
            Clock.schedule_once(lambda dt, cb=cb, data=data: cb(data))


ws_client = WSClient()
