from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen

from ..config import load_config, update_config

KV = """
<AdminScreen>:
    name: 'admin'
    DarkScreen:
        BoxLayout:
            orientation: 'vertical'
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
Builder.load_string(KV)


class AdminScreen(Screen):
    def on_pre_enter(self):
        cfg = load_config()
        self.ids.server_ip_input.text = cfg.get("server_ip", "")
        self.ids.server_port_input.text = str(cfg.get("server_port", 8765))
        self.ids.prefill_worker_input.text = cfg.get("prefill_worker_id", "")

    def save_admin_config(self):
        ip = self.ids.server_ip_input.text.strip()
        port = self.ids.server_port_input.text.strip()
        prefill = self.ids.prefill_worker_input.text.strip()

        if not ip:
            self.ids.admin_status.text = "// Server IP required"
            self.ids.admin_status.color = (1, 0.3, 0.3, 1)
            return

        update_config(
            server_ip=ip,
            server_port=int(port) if port.isdigit() else 8765,
            prefill_worker_id=prefill,
        )

        self.ids.admin_status.text = "Saved. Returning to login..."
        self.ids.admin_status.color = (0, 0.8, 0.4, 1)
        Clock.schedule_once(lambda dt: setattr(self.manager, "current", "login"), 1.5)
