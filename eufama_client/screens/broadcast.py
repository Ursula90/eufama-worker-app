import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen

from ..netclient import ApiError, post

KV = """
<BroadcastScreen>:
    name: 'broadcast'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(16)
        spacing: dp(12)

        Label:
            text: '⭐ Difuzare VIP către toată echipa'
            bold: True
            color: 1, 0.7, 0, 1
            font_size: '15sp'
            size_hint_y: None
            height: dp(28)

        Label:
            text: 'Mesajul va ajunge instant la fiecare angajat, în conversația lui cu tine — la fel ca o listă de difuzare.'
            font_size: '12sp'
            color: 0.6, 0.7, 0.85, 1
            size_hint_y: None
            height: dp(50)
            halign: 'left'
            valign: 'top'
            text_size: self.width, None

        TextInput:
            id: broadcast_input
            hint_text: 'Scrie anunțul...'
            background_color: 0.06, 0.08, 0.13, 1
            foreground_color: 0.9, 0.93, 0.96, 1

        RoundButton:
            id: send_btn
            text: 'Trimite la toți'
            bold: True
            bg_color: 0.7, 0.4, 0, 1
            size_hint_y: None
            height: dp(48)
            on_release: root.send_broadcast()

        Label:
            id: status_label
            text: ''
            font_size: '12sp'
            color: 0, 0.8, 0.4, 1
            size_hint_y: None
            height: dp(24)
"""
Builder.load_string(KV)


class BroadcastScreen(Screen):
    def send_broadcast(self):
        text = self.ids.broadcast_input.text.strip()
        if not text:
            self.ids.status_label.color = (1, 0.3, 0.3, 1)
            self.ids.status_label.text = "// Scrie un mesaj înainte de trimitere"
            return

        self.ids.send_btn.disabled = True
        threading.Thread(target=self._send_thread, args=(text,), daemon=True).start()

    def _send_thread(self, text):
        try:
            recipients = post("/broadcast", {"body": text})
            Clock.schedule_once(lambda dt: self._ok(len(recipients)))
        except ApiError as e:
            Clock.schedule_once(lambda dt: self._fail(e.message))

    def _ok(self, count):
        self.ids.send_btn.disabled = False
        self.ids.broadcast_input.text = ""
        self.ids.status_label.color = (0, 0.8, 0.4, 1)
        self.ids.status_label.text = f"Trimis la {count} angajați."

    def _fail(self, message):
        self.ids.send_btn.disabled = False
        self.ids.status_label.color = (1, 0.3, 0.3, 1)
        self.ids.status_label.text = f"// Eroare: {message}"
