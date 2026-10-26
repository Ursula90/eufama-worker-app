import json
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from .. import contacts_cache, crypto
from ..config import load_config
from ..media_helpers import VoiceRecorder, open_url_external, take_photo
from ..netclient import ApiError, get, post, post_multipart
from ..ws_client import ws_client

KV = """
<ChatDetailScreen>:
    name: 'chat_detail'
    DarkScreen:
        BoxLayout:
            orientation: 'vertical'

            TopBar:
                Button:
                    text: '←'
                    size_hint_x: None
                    width: dp(40)
                    background_color: 0,0,0,0
                    background_normal: ''
                    color: 0, 0.7, 1, 1
                    on_release: root.go_back()
                Label:
                    text: root.title_text
                    bold: True
                    color: 0.9, 0.93, 0.96, 1
                    halign: 'left'
                    text_size: self.size
                Button:
                    text: 'zzZ'
                    size_hint_x: None
                    width: dp(46)
                    background_color: 0,0,0,0
                    background_normal: ''
                    color: 1, 0.7, 0, 1
                    on_release: root.send_buzz()
                Button:
                    text: '📞'
                    size_hint_x: None
                    width: dp(40)
                    background_color: 0,0,0,0
                    background_normal: ''
                    on_release: root.start_call('audio')
                Button:
                    text: '🎥'
                    size_hint_x: None
                    width: dp(40)
                    background_color: 0,0,0,0
                    background_normal: ''
                    on_release: root.start_call('video')

            ScrollView:
                id: scroll
                BoxLayout:
                    id: messages_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: [dp(10), dp(10)]
                    spacing: dp(8)

            BoxLayout:
                size_hint_y: None
                height: dp(56)
                padding: [dp(8), dp(6)]
                spacing: dp(6)

                Button:
                    text: '📷'
                    size_hint_x: None
                    width: dp(44)
                    background_color: 0,0,0,0
                    background_normal: ''
                    on_release: root.attach_photo()

                TextInput:
                    id: message_input
                    hint_text: 'Scrie un mesaj...'
                    multiline: False
                    background_color: 0.06, 0.08, 0.13, 1
                    foreground_color: 0.9, 0.93, 0.96, 1
                    on_text_validate: root.send_text()

                Button:
                    id: mic_btn
                    text: '🎙'
                    size_hint_x: None
                    width: dp(44)
                    background_color: 0,0,0,0
                    background_normal: ''
                    on_press: root.start_recording()
                    on_release: root.stop_recording()

                RoundButton:
                    text: '➤'
                    size_hint_x: None
                    width: dp(48)
                    on_release: root.send_text()
"""
Builder.load_string(KV)


class ClickableBubble(ButtonBehavior, BoxLayout):
    pass


class ChatDetailScreen(Screen):
    conversation_id = NumericProperty(0)
    title_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._recorder = VoiceRecorder()
        self._last_message_id = 0
        self.convo_type = None
        self.convo_member_ids = []

    def on_pre_enter(self):
        self.ids.messages_box.clear_widgets()
        self._last_message_id = 0
        self.convo_type = None
        self.convo_member_ids = []
        # Disabled until _load_history knows convo_type/member_ids — without
        # this, typing+sending fast enough to beat that network round trip
        # would silently fall through to the plaintext branch below instead
        # of encrypting, since convo_type is still None at that point.
        self.ids.message_input.disabled = True
        ws_client.on("message", self._on_ws_message)
        threading.Thread(target=self._load_history, daemon=True).start()

    def on_leave(self):
        ws_client.off("message", self._on_ws_message)

    # ── history + live updates ──────────────────────────────
    def _load_history(self):
        try:
            if not contacts_cache.all_contacts():
                contacts_cache.refresh()
            convo = get(f"/conversations/{self.conversation_id}", timeout=15)
            self.convo_type = convo["type"]
            self.convo_member_ids = convo["member_ids"]
            messages = get(f"/conversations/{self.conversation_id}/messages", timeout=15)
            Clock.schedule_once(lambda dt: self._render_all(messages))
        except Exception:
            pass
        finally:
            Clock.schedule_once(lambda dt: setattr(self.ids.message_input, "disabled", False))

    def _other_member_pubkey(self):
        """Direct conversations only — the single other participant's key."""
        my_id = load_config().get("user_id")
        other_id = next((uid for uid in self.convo_member_ids if uid != my_id), None)
        contact = contacts_cache.get_user(other_id) if other_id is not None else None
        return contact.get("public_key") if contact else None

    def _group_member_pubkeys(self):
        """Group conversations — every member's key, including my own
        (so I can decrypt my own sent history later), or None if anyone
        in the group hasn't uploaded a key yet."""
        my_id = load_config().get("user_id")
        my_pubkey = crypto.my_public_key()
        if not my_pubkey:
            return None
        keys = {my_id: my_pubkey}
        for uid in self.convo_member_ids:
            if uid == my_id:
                continue
            contact = contacts_cache.get_user(uid)
            if not contact or not contact.get("public_key"):
                return None
            keys[uid] = contact["public_key"]
        return keys

    def _render_all(self, messages):
        for msg in messages:
            self._append_message(msg, scroll=False)
        self._scroll_to_bottom()

    def _on_ws_message(self, data):
        msg = data.get("message", {})
        if msg.get("conversation_id") == self.conversation_id:
            self._append_message(msg)

    def _append_message(self, msg, scroll=True):
        self._last_message_id = max(self._last_message_id, msg["id"])
        self.ids.messages_box.add_widget(self._build_bubble(msg))
        if scroll:
            self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        Clock.schedule_once(lambda dt: setattr(self.ids.scroll, "scroll_y", 0), 0.05)

    # ── bubble rendering ────────────────────────────────────
    def _build_bubble(self, msg):
        my_id = load_config().get("user_id")
        mine = msg["sender_id"] == my_id
        bg = (0.05, 0.35, 0.55, 1) if mine else (0.1, 0.13, 0.2, 1)
        align = "right" if mine else "left"

        row = BoxLayout(size_hint_y=None, height="1dp")
        row.bind(minimum_height=lambda w, v: setattr(row, "height", v))

        bubble = BoxLayout(
            orientation="vertical", size_hint=(None, None), padding=[dp(10), dp(8)], spacing=dp(4),
        )
        bubble.width = dp(260)
        with bubble.canvas.before:
            Color(*bg)
            rr = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[10])
        bubble.bind(pos=lambda *_: setattr(rr, "pos", bubble.pos))
        bubble.bind(size=lambda *_: setattr(rr, "size", bubble.size))

        content = self._build_content(msg)
        bubble.add_widget(content)
        bubble.bind(minimum_height=lambda w, v: setattr(bubble, "height", v))

        ts = (msg.get("created_at") or "")[11:16]
        ts_lbl = Label(text=ts, font_size="10sp", color=(0.5, 0.58, 0.7, 1), size_hint_y=None, height=14)
        bubble.add_widget(ts_lbl)

        spacer = BoxLayout()
        if align == "right":
            row.add_widget(spacer)
            row.add_widget(bubble)
        else:
            row.add_widget(bubble)
            row.add_widget(spacer)
        return row

    def _build_content(self, msg):
        mtype = msg["type"]
        if mtype == "text":
            lbl = Label(
                text=crypto.decrypt_message_body(msg, self.convo_member_ids), color=(0.92, 0.95, 0.98, 1),
                size_hint_y=None, halign="left", valign="top",
            )
            lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
            lbl.bind(texture_size=lambda w, v: setattr(lbl, "height", v[1]))
            return lbl
        if mtype == "image":
            img = AsyncImage(source=msg.get("media_url"), size_hint_y=None, height=180, allow_stretch=True)
            return img
        if mtype == "voice":
            dur = (msg.get("duration_ms") or 0) / 1000
            return self._open_button(f"🎙 Mesaj vocal ({dur:.0f}s) — atinge pt. redare", msg.get("media_url"))
        if mtype == "file":
            return self._open_button("📎 Fișier atașat — atinge pt. deschidere", msg.get("media_url"))
        return Label(text=f"[{mtype}]", color=(0.6, 0.6, 0.6, 1), size_hint_y=None, height=20)

    def _open_button(self, text, url):
        btn = ClickableBubble(size_hint_y=None, height=36)
        lbl = Label(text=text, font_size="12sp", color=(0.7, 0.85, 1, 1))
        btn.add_widget(lbl)
        if url:
            btn.bind(on_release=lambda *_: open_url_external(url))
        return btn

    # ── sending ──────────────────────────────────────────────
    def send_text(self):
        text = self.ids.message_input.text.strip()
        if not text:
            return
        self.ids.message_input.text = ""
        threading.Thread(target=self._send_text_thread, args=(text,), daemon=True).start()

    def _send_text_thread(self, text):
        fields = {"type": "text"}

        if self.convo_type == "direct":
            other_pubkey = self._other_member_pubkey()
            if other_pubkey:
                fields["body"] = crypto.encrypt_direct(text, other_pubkey)
                fields["encrypted"] = "true"
                fields["enc_scheme"] = "direct"
            else:
                fields["body"] = text
        elif self.convo_type == "group":
            pubkeys = self._group_member_pubkeys()
            if pubkeys:
                body_b64, sealed_keys = crypto.encrypt_group(text, pubkeys)
                fields["body"] = body_b64
                fields["encrypted"] = "true"
                fields["enc_scheme"] = "group"
                fields["enc_keys"] = json.dumps(sealed_keys)
            else:
                fields["body"] = text
        else:
            fields["body"] = text

        try:
            msg = post_multipart(f"/conversations/{self.conversation_id}/messages", fields)
            Clock.schedule_once(lambda dt: self._append_message(msg))
        except ApiError:
            pass

    def attach_photo(self):
        take_photo(self._on_photo_ready)

    def _on_photo_ready(self, path):
        if path:
            threading.Thread(target=self._send_thread, args=({"type": "image"}, path), daemon=True).start()

    def start_recording(self):
        self._recorder.start()
        self.ids.mic_btn.text = "⏺"

    def stop_recording(self):
        self.ids.mic_btn.text = "🎙"
        path, duration_ms = self._recorder.stop()
        if path:
            threading.Thread(
                target=self._send_thread, args=({"type": "voice", "duration_ms": duration_ms}, path), daemon=True,
            ).start()

    def _send_thread(self, fields, file_path):
        try:
            msg = post_multipart(f"/conversations/{self.conversation_id}/messages", fields, file_path=file_path)
            Clock.schedule_once(lambda dt: self._append_message(msg))
        except ApiError:
            pass

    # ── buzz + calls ─────────────────────────────────────────
    def send_buzz(self):
        threading.Thread(target=lambda: self._try(lambda: post("/buzz", {"conversation_id": self.conversation_id})), daemon=True).start()

    def start_call(self, call_type):
        threading.Thread(target=self._start_call_thread, args=(call_type,), daemon=True).start()

    def _start_call_thread(self, call_type):
        try:
            resp = post(f"/conversations/{self.conversation_id}/calls", {"call_type": call_type})
            Clock.schedule_once(lambda dt: open_url_external(resp["join_url"]))
        except ApiError:
            pass

    def _try(self, fn):
        try:
            fn()
        except ApiError:
            pass

    def go_back(self):
        App.get_running_app().back_to_home()
