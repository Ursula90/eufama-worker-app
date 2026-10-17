"""
Short-lived, call-scoped tokens handed to each participant so the browser
call page never needs to know a worker's real login token. Kept in memory
only — a call token is worthless once the process restarts, which is fine
since it is only meant to live for the duration of one call.
"""

import secrets
import time
from typing import Optional

from .config import CALL_TOKEN_TTL_SECONDS

# token -> (call_id, user_id, expires_at)
_tokens: dict[str, tuple[str, int, float]] = {}


def issue_call_token(call_id: str, user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    _tokens[token] = (call_id, user_id, time.time() + CALL_TOKEN_TTL_SECONDS)
    return token


def resolve_call_token(token: str) -> Optional[tuple[str, int]]:
    entry = _tokens.get(token)
    if entry is None:
        return None
    call_id, user_id, expires_at = entry
    if time.time() > expires_at:
        _tokens.pop(token, None)
        return None
    return call_id, user_id
