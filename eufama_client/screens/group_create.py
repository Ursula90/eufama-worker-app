import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from .. import contacts_cache
from ..netclient import ApiError, post

KV = """
<GroupCreateScreen>:
    name: 'group_create'
    DarkScreen:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(10)

            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(8)
                Button:
                    text: '←'
                    size_hint_x: None
                    width: dp(40)
                    background_color: 0,0,0,0
                    background_normal: ''
                    color: 0, 0.7, 1, 1
                    on_release: root.go_back()
                Label:
                    text: 'Grup nou'
                    bold: True
                    color: 0, 0.7, 1, 1

            TextInput:
                id: name_input
                hint_text: 'Numele grupului (ex: Șantier Nord)'
                multiline: False
                size_hint_y: None
                height: dp(44)
                background_color: 0.06, 0.08, 0.13, 1
                foreground_color: 0.9, 0.93, 0.96, 1

            Label:
                text: 'Selectează membrii:'
                size_hint_y: None
                height: dp(24)
                color: 0.6, 0.7, 0.85, 1
                halign: 'left'
                text_size: self.size

            ScrollView:
                BoxLayout:
                    id: members_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height

            RoundButton:
                text: 'Creează grupul'
                bold: True
                size_hint_y: None
                height: dp(48)
                on_release: root.create_group()

            Label:
                id: error_label
                text: ''
                color: 1, 0.3, 0.3, 1
                size_hint_y: None
                height: dp(24)
"""
Builder.load_string(KV)


class GroupCreateScreen(Screen):
    def on_pre_enter(self):
        self.ids.name_input.text = ""
        self.ids.error_label.text = ""
        self._checkboxes = {}
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            contacts_cache.refresh()
            Clock.schedule_once(lambda dt: self._render())
        except Exception:
            pass

    def _render(self):
        box = self.ids.members_box
        box.clear_widgets()
        self._checkboxes = {}
        for user in contacts_cache.all_contacts():
            row = BoxLayout(size_hint_y=None, height="44dp", spacing=8)
            cb = CheckBox()
            self._checkboxes[user["id"]] = cb
            row.add_widget(cb)
            lbl = Label(text=user["display_name"], color=(0.9, 0.93, 0.96, 1), halign="left", valign="middle")
            lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
            row.add_widget(lbl)
            box.add_widget(row)

    def create_group(self):
        name = self.ids.name_input.text.strip()
        selected = [uid for uid, cb in self._checkboxes.items() if cb.active]

        if not name:
            self.ids.error_label.text = "// Introdu un nume pentru grup"
            return
        if len(selected) < 1:
            self.ids.error_label.text = "// Selectează cel puțin un membru"
            return

        threading.Thread(target=self._create_thread, args=(name, selected), daemon=True).start()

    def _create_thread(self, name, selected):
        try:
            convo = post("/conversations", {"type": "group", "member_ids": selected, "name": name})
            Clock.schedule_once(lambda dt: App.get_running_app().open_chat(convo["id"], name))
        except ApiError as e:
            Clock.schedule_once(lambda dt: setattr(self.ids.error_label, "text", f"// Eroare: {e.message}"))

    def go_back(self):
        App.get_running_app().back_to_home()
