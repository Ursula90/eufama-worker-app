"""Reusable widget classes with real Kivy Properties.

`bg_color` used to be handled with a `self.bg_color if hasattr(self,
'bg_color') else (...)` trick in a plain `<RoundButton@Button>` KV
template. That's fragile: Kivy auto-creates ad-hoc properties (defaulting
to None) for every name referenced in a rule tree before per-instance
values are applied, so `hasattr` can be True with the value still None,
crashing `Color.rgba` on a plain `NoneType`. Declaring `bg_color` as a
real ListProperty here removes that whole failure mode.
"""

from kivy.factory import Factory
from kivy.lang import Builder
from kivy.properties import ListProperty
from kivy.uix.button import Button


class RoundButton(Button):
    bg_color = ListProperty([0.05, 0.4, 0.8, 1])


Factory.register("RoundButton", cls=RoundButton)

Builder.load_string("""
<RoundButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: self.bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12,]
""")
