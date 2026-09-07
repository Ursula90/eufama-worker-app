"""Tiny in-memory cache of the company directory (GET /users), so every
screen that needs to turn a user_id into a display name doesn't have to
hit the network itself."""

from .config import load_config
from .netclient import get

_contacts: dict[int, dict] = {}


def refresh() -> dict:
    users = get("/users")
    _contacts.clear()
    for u in users:
        _contacts[u["id"]] = u
    return _contacts


def all_contacts() -> list:
    return sorted(_contacts.values(), key=lambda u: u["display_name"].lower())


def get_user(user_id: int) -> dict | None:
    return _contacts.get(user_id)


def name_for(user_id: int) -> str:
    cfg = load_config()
    if user_id == cfg.get("user_id"):
        return "Tu"
    u = _contacts.get(user_id)
    return u["display_name"] if u else f"#{user_id}"
