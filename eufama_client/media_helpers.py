"""Camera / voice-note / external-browser helpers for chat attachments and
audio+video calls. All Android-specific bits degrade to no-ops on desktop
so the app stays runnable for local testing (matches the existing pattern
already used for GPS and the camera in the safety screen)."""

import os
import time

from kivy.utils import platform

from .config import MEDIA_CACHE_DIR


def new_media_path(ext: str) -> str:
    return os.path.join(MEDIA_CACHE_DIR, f"{int(time.time() * 1000)}.{ext}")


def take_photo(on_complete):
    """on_complete(path_or_None) is called back with the captured file."""
    if platform == "android":
        try:
            from plyer import camera
            path = new_media_path("jpg")
            camera.take_picture(filename=path, on_complete=lambda p: on_complete(path))
            return
        except Exception:
            pass
    on_complete(None)


def open_url_external(url: str):
    """Opens a URL in the system browser — used for audio/video calls,
    which run WebRTC in Chrome's mature stack rather than in Kivy."""
    if platform == "android":
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            PythonActivity.mActivity.startActivity(intent)
            return
        except Exception:
            pass
    import webbrowser
    webbrowser.open(url)


class VoiceRecorder:
    """Push-to-record voice notes via plyer's Android MediaRecorder facade."""

    def __init__(self):
        self._path = None
        self._start_time = None

    def start(self) -> bool:
        self._path = new_media_path("3gp")
        self._start_time = time.time()
        if platform == "android":
            try:
                from plyer import audio
                audio.file_path = self._path
                audio.start()
                return True
            except Exception:
                pass
        return False

    def stop(self):
        """Returns (file_path_or_None, duration_ms)."""
        duration_ms = int((time.time() - (self._start_time or time.time())) * 1000)
        if platform == "android":
            try:
                from plyer import audio
                audio.stop()
            except Exception:
                pass
        path, self._path = self._path, None
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path, duration_ms
        return None, 0
