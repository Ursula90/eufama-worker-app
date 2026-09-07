"""
The "Buzz" — same idea as the old Yahoo! Messenger nudge: an instant,
attention-grabbing WebSocket event with no persisted message. The
receiving app shakes the screen, vibrates and plays a sound.
"""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..chat_common import member_ids, require_member
from ..config import BUZZ_COOLDOWN_SECONDS
from ..database import get_db
from ..models import User
from ..schemas import BuzzRequest
from ..ws_manager import app_manager

router = APIRouter(prefix="/buzz", tags=["buzz"])

# (sender_id, target_id) -> last-sent monotonic timestamp
_last_buzz: dict[tuple[int, int], float] = {}


@router.post("")
async def send_buzz(
    req: BuzzRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_member(db, req.conversation_id, user.id)
    targets = [uid for uid in member_ids(db, req.conversation_id) if uid != user.id]
    if not targets:
        raise HTTPException(400, "no one else in this conversation")

    now = time.monotonic()
    throttled = []
    for target in targets:
        key = (user.id, target)
        last = _last_buzz.get(key, 0.0)
        if now - last < BUZZ_COOLDOWN_SECONDS:
            throttled.append(target)
            continue
        _last_buzz[key] = now
        await app_manager.send_to_user(target, {
            "type": "buzz",
            "conversation_id": req.conversation_id,
            "from": user.id,
            "from_name": user.display_name,
        })

    return {"sent_to": [t for t in targets if t not in throttled], "throttled": throttled}
