"""Attention effects for the incoming 'Buzz' — vibration + screen shake +
sound, same spirit as the old Yahoo! Messenger nudge."""

import os

from kivy.animation import Animation
from kivy.core.audio import SoundLoader
from kivy.utils import platform

_ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
_buzz_sound = None


def _load_buzz_sound():
    global _buzz_sound
    if _buzz_sound is None:
        path = os.path.join(_ASSET_DIR, "buzz.wav")
        if os.path.exists(path):
            _buzz_sound = SoundLoader.load(path)
    return _buzz_sound


def vibrate(duration: float = 0.4):
    if platform == "android":
        try:
            from plyer import vibrator
            vibrator.vibrate(duration)
        except Exception:
            pass


def shake_widget(widget, distance: float = 14, cycles: int = 4, step: float = 0.045):
    if widget is None:
        return
    ox = widget.x
    anim = Animation(x=ox - distance, duration=step)
    for _ in range(cycles):
        anim += Animation(x=ox + distance, duration=step * 2)
        anim += Animation(x=ox - distance, duration=step * 2)
    anim += Animation(x=ox, duration=step)
    Animation.cancel_all(widget, "x")
    anim.start(widget)


def play_buzz_sound():
    sound = _load_buzz_sound()
    if sound:
        sound.stop()
        sound.play()


def trigger_buzz(shake_target=None):
    vibrate()
    shake_widget(shake_target)
    play_buzz_sound()
