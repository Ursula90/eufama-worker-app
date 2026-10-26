"""
Short-lived tokens for the VIP/admin live map page, same pattern as
call_tokens.py — the browser map page never needs to know the admin's
real login token, just a token scoped to viewing dispatch data.
"""

import secrets
import time
from typing import Optional

from .config import CALL_TOKEN_TTL_SECONDS

# token -> (user_id, expires_at)
_tokens: dict[str, tuple[int, float]] = {}


def issue_admin_token(user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    _tokens[token] = (user_id, time.time() + CALL_TOKEN_TTL_SECONDS)
    return token


def resolve_admin_token(token: str) -> Optional[int]:
    entry = _tokens.get(token)
    if entry is None:
        return None
    user_id, expires_at = entry
    if time.time() > expires_at:
        _tokens.pop(token, None)
        return None
    return user_id
