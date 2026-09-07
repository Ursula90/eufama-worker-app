"""Offline GPS-ping queue for the safety screen — unchanged behaviour from
the original app, just re-pointed at the new netclient helper so it goes
through the same base-URL/error handling as everything else."""

import json
import os
from datetime import datetime

from .config import QUEUE_FILE
from .netclient import ApiError, post


def queue_load() -> list:
    try:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def queue_save(entries: list):
    try:
        entries = entries[-500:]
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f)
    except Exception:
        pass


def queue_push(payload: dict):
    q = queue_load()
    payload["queued_at"] = datetime.now().isoformat()
    q.append(payload)
    queue_save(q)


def try_post(endpoint: str, payload: dict) -> bool:
    try:
        post(endpoint, payload, auth=False)
        return True
    except (ApiError, Exception):
        return False


def queue_flush() -> int:
    q = queue_load()
    if not q:
        return 0
    sent = 0
    remaining = []
    for entry in q:
        if try_post("/ping", entry):
            sent += 1
        else:
            remaining.append(entry)
    queue_save(remaining)
    return sent
