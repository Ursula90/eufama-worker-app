"""
VIP broadcast: one message from a VIP/admin, fanned out into every other
worker's direct chat with that VIP — same idea as a WhatsApp broadcast
list. Each recipient sees it as a normal message from the VIP; recipients
never see each other.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..chat_common import message_out as _message_out
from ..database import get_db
from ..models import Message, User
from ..routers.conversations import get_or_create_direct
from ..schemas import BroadcastRequest, MessageOut
from ..ws_manager import app_manager

router = APIRouter(prefix="/broadcast", tags=["broadcast"])


@router.post("", response_model=list[MessageOut])
async def broadcast(
    req: BroadcastRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in ("vip", "admin"):
        raise HTTPException(403, "only VIP or admin accounts can broadcast")
    if not req.body.strip():
        raise HTTPException(400, "message body required")

    group_id = uuid.uuid4().hex
    recipients = db.query(User).filter(User.id != user.id).all()

    sent: list[MessageOut] = []
    for recipient in recipients:
        convo = get_or_create_direct(db, user.id, recipient.id)
        msg = Message(
            conversation_id=convo.id,
            sender_id=user.id,
            type="text",
            body=req.body,
            broadcast_group_id=group_id,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        out = _message_out(msg)
        sent.append(out)
        await app_manager.send_to_user(recipient.id, {"type": "message", "message": out.model_dump(mode="json")})

    return sent
