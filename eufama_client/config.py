"""Local device config + small helpers shared by every screen."""

import json
import os

from kivy.utils import platform

if platform == "android":
    from android.storage import app_storage_path
    APP_DIR = app_storage_path()
else:
    APP_DIR = os.path.expanduser("~/.eufama_worker")
    os.makedirs(APP_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
QUEUE_FILE = os.path.join(APP_DIR, "offline_queue.json")
MEDIA_CACHE_DIR = os.path.join(APP_DIR, "media_cache")
os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

GPS_INTERVAL = 30  # seconds, safety GPS ping while on shift


def load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def update_config(**kwargs):
    cfg = load_config()
    cfg.update(kwargs)
    save_config(cfg)
    return cfg


def is_logged_in() -> bool:
    cfg = load_config()
    return bool(cfg.get("worker_id") and cfg.get("token") and cfg.get("user_id"))


def is_vip() -> bool:
    return load_config().get("role") in ("vip", "admin")
