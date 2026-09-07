import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from .. import contacts_cache
from ..netclient import ApiError, post

KV = """
<ContactRow@BoxLayout>:
    size_hint_y: None
    height: dp(64)
    padding: [dp(14), dp(8)]
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: 0.06, 0.08, 0.13, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [8,]

<ContactsScreen>:
    name: 'contacts'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        spacing: dp(8)

        BoxLayout:
            size_hint_y: None
            height: dp(44)
            spacing: dp(8)
            Label:
                text: 'Contacte EUFAMA'
                bold: True
                color: 0, 0.7, 1, 1
                font_size: '16sp'
            RoundButton:
                text: '+ Grup nou'
                size_hint_x: 0.4
                font_size: '12sp'
                on_release: root.open_group_create()

        ScrollView:
            BoxLayout:
                id: contacts_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
"""
Builder.load_string(KV)


class ContactsScreen(Screen):
    def on_pre_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            contacts_cache.refresh()
            Clock.schedule_once(lambda dt: self._render())
        except Exception:
            pass

    def _render(self):
        box = self.ids.contacts_box
        box.clear_widgets()
        for user in contacts_cache.all_contacts():
            box.add_widget(self._build_row(user))

    def _build_row(self, user):
        row = BoxLayout(size_hint_y=None, height="64dp", padding=[14, 8], spacing=10)
        with row.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.06, 0.08, 0.13, 1)
            rr = RoundedRectangle(pos=row.pos, size=row.size, radius=[8])
        row.bind(pos=lambda *_: setattr(rr, "pos", row.pos))
        row.bind(size=lambda *_: setattr(rr, "size", row.size))

        from kivy.uix.label import Label
        from kivy.uix.button import Button

        dot_color = (0, 0.85, 0.4, 1) if user.get("is_online") else (0.4, 0.45, 0.55, 1)
        role_tag = "  ⭐ VIP" if user.get("role") in ("vip", "admin") else ""

        name_lbl = Label(
            text=f"[color={_hex(dot_color)}]●[/color]  {user['display_name']}{role_tag}",
            markup=True, halign="left", valign="middle", color=(0.9, 0.93, 0.96, 1),
        )
        name_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        row.add_widget(name_lbl)

        chat_btn = Button(
            text="💬", size_hint_x=None, width="48dp",
            background_normal="", background_color=(0, 0, 0, 0), color=(0, 0.7, 1, 1),
        )
        chat_btn.bind(on_release=lambda *_: self._start_chat(user))
        row.add_widget(chat_btn)
        return row

    def _start_chat(self, user):
        threading.Thread(target=self._start_chat_thread, args=(user,), daemon=True).start()

    def _start_chat_thread(self, user):
        try:
            convo = post("/conversations", {"type": "direct", "member_ids": [user["id"]]})
            Clock.schedule_once(
                lambda dt: App.get_running_app().open_chat(convo["id"], user["display_name"])
            )
        except ApiError:
            pass

    def open_group_create(self):
        App.get_running_app().open_group_create()


def _hex(rgba):
    r, g, b, _ = rgba
    return "%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
