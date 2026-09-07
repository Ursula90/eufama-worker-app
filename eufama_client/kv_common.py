"""Shared KV widget templates used across screens. Imported once from
main.py before any Screen is instantiated so the templates are already
registered in the Factory by the time KV rules reference them."""

from kivy.lang import Builder

from . import widgets  # noqa: F401 — registers RoundButton (and its Factory entry)

Builder.load_string("""
#:import dp kivy.metrics.dp

<DarkScreen@Screen>:
    canvas.before:
        Color:
            rgba: 0.02, 0.03, 0.07, 1
        Rectangle:
            pos: self.pos
            size: self.size

<TopBar@BoxLayout>:
    size_hint_y: None
    height: dp(48)
    padding: [dp(12), 0]
    canvas.before:
        Color:
            rgba: 0.06, 0.08, 0.13, 1
        Rectangle:
            pos: self.pos
            size: self.size

<NavButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    bold: True
    font_size: '12sp'
""")
