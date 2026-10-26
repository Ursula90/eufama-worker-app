import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from .. import contacts_cache, crypto
from ..config import load_config
from ..netclient import get

KV = """
<ChatsListScreen>:
    name: 'chats_list'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        spacing: dp(8)

        Label:
            text: 'Conversații'
            bold: True
            color: 0, 0.7, 1, 1
            font_size: '16sp'
            size_hint_y: None
            height: dp(30)

        ScrollView:
            BoxLayout:
                id: chats_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)

        Label:
            id: empty_label
            text: ''
            color: 0.5, 0.6, 0.8, 1
            font_size: '13sp'
            size_hint_y: None
            height: dp(30) if self.text else 0
"""
Builder.load_string(KV)

_MEDIA_PREVIEW = {"image": "📷 Fotografie", "file": "📎 Fișier", "voice": "🎙 Mesaj vocal"}


class ClickableRow(ButtonBehavior, BoxLayout):
    pass


class ChatsListScreen(Screen):
    def on_pre_enter(self):
        self.refresh()

    def refresh(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            if not contacts_cache.all_contacts():
                contacts_cache.refresh()
            conversations = get("/conversations")
            Clock.schedule_once(lambda dt: self._render(conversations))
        except Exception:
            pass

    def _render(self, conversations):
        box = self.ids.chats_box
        box.clear_widgets()
        self.ids.empty_label.text = "Nicio conversație încă — mergi la Contacte." if not conversations else ""
        my_id = load_config().get("user_id")

        for convo in conversations:
            box.add_widget(self._build_row(convo, my_id))

    def _build_row(self, convo, my_id):
        if convo["type"] == "group":
            title = convo.get("name") or "Grup"
        else:
            other_id = next((uid for uid in convo["member_ids"] if uid != my_id), None)
            title = contacts_cache.name_for(other_id) if other_id is not None else "Conversație"

        last = convo.get("last_message")
        if last is None:
            preview = "Fără mesaje încă"
        elif last["type"] == "text":
            preview = crypto.decrypt_message_body(last, convo["member_ids"])
        else:
            preview = _MEDIA_PREVIEW.get(last["type"], last["type"])

        row = ClickableRow(
            size_hint_y=None, height="60dp", padding=[14, 6], spacing=10, orientation="horizontal",
        )
        with row.canvas.before:
            Color(0.06, 0.08, 0.13, 1)
            rr = RoundedRectangle(pos=row.pos, size=row.size, radius=[8])
        row.bind(pos=lambda *_: setattr(rr, "pos", row.pos))
        row.bind(size=lambda *_: setattr(rr, "size", row.size))
        row.bind(on_release=lambda *_: App.get_running_app().open_chat(convo["id"], title))

        text_col = BoxLayout(orientation="vertical")
        title_lbl = Label(text=title, bold=True, halign="left", valign="middle", color=(0.9, 0.93, 0.96, 1))
        title_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        preview_lbl = Label(
            text=preview, font_size="12sp", halign="left", valign="middle", color=(0.55, 0.62, 0.75, 1),
        )
        preview_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        text_col.add_widget(title_lbl)
        text_col.add_widget(preview_lbl)
        row.add_widget(text_col)
        return row
