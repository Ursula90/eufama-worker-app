from kivy.app import App
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen, ScreenManager, NoTransition

from ..config import is_vip, load_config
from .broadcast import BroadcastScreen
from .chats_list import ChatsListScreen
from .contacts import ContactsScreen
from .safety import SafetyScreen

KV = """
<HomeScreen>:
    name: 'home'
    DarkScreen:
        BoxLayout:
            orientation: 'vertical'

            TopBar:
                Label:
                    text: 'EUFAMA CONNECT'
                    bold: True
                    color: 0, 0.7, 1, 1
                    font_size: '15sp'
                Label:
                    id: worker_name_label
                    text: ''
                    color: 0.5, 0.6, 0.8, 1
                    font_size: '11sp'
                Button:
                    text: 'Ieși'
                    size_hint_x: None
                    width: dp(50)
                    font_size: '11sp'
                    background_color: 0,0,0,0
                    background_normal: ''
                    color: 0.7, 0.3, 0.3, 1
                    on_release: root.logout()

            BoxLayout:
                id: inner_container

            BoxLayout:
                id: nav_bar
                size_hint_y: None
                height: dp(56)
                canvas.before:
                    Color:
                        rgba: 0.06, 0.08, 0.13, 1
                    Rectangle:
                        pos: self.pos
                        size: self.size
"""
Builder.load_string(KV)


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tabs_built = False
        self.inner_sm = None
        self._nav_buttons = {}

    def on_pre_enter(self):
        cfg = load_config()
        self.ids.worker_name_label.text = cfg.get("display_name", "")
        if not self._tabs_built:
            self._build_tabs()
        self.switch_tab("chats_list")

    def _build_tabs(self):
        self.inner_sm = ScreenManager(transition=NoTransition())
        self.inner_sm.add_widget(ChatsListScreen())
        self.inner_sm.add_widget(ContactsScreen())
        self.inner_sm.add_widget(SafetyScreen())
        if is_vip():
            self.inner_sm.add_widget(BroadcastScreen())
        self.ids.inner_container.add_widget(self.inner_sm)

        NavButton = Factory.NavButton
        tabs = [("chats_list", "💬\nChats"), ("contacts", "👤\nContacte"), ("safety", "🛟\nSiguranță")]
        if is_vip():
            tabs.append(("broadcast", "⭐\nDifuzare"))

        for name, label in tabs:
            btn = NavButton(text=label, color=(0.5, 0.6, 0.8, 1))
            btn.bind(on_release=lambda inst, n=name: self.switch_tab(n))
            self.ids.nav_bar.add_widget(btn)
            self._nav_buttons[name] = btn

        self._tabs_built = True

    def switch_tab(self, name):
        self.inner_sm.current = name
        for tab_name, btn in self._nav_buttons.items():
            btn.color = (0, 0.7, 1, 1) if tab_name == name else (0.5, 0.6, 0.8, 1)
        if name == "chats_list":
            self.inner_sm.get_screen("chats_list").refresh()

    def logout(self):
        App.get_running_app().logout()
