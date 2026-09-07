"""Shared helpers used by both the conversations and messages routers.

Split out on its own module so the two routers can import from a common
place without importing each other (would create a circular import).
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import PUBLIC_BASE_URL
from .models import Conversation, ConversationMember, Message
from .schemas import MessageOut


def member_ids(db: Session, conversation_id: int) -> list[int]:
    rows = db.query(ConversationMember.user_id).filter(
        ConversationMember.conversation_id == conversation_id
    ).all()
    return [r[0] for r in rows]


def require_member(db: Session, conversation_id: int, user_id: int) -> Conversation:
    convo = db.query(Conversation).get(conversation_id)
    if convo is None:
        raise HTTPException(404, "conversation not found")
    if user_id not in member_ids(db, conversation_id):
        raise HTTPException(403, "not a member of this conversation")
    return convo


def message_out(msg: Message) -> MessageOut:
    media_url = f"{PUBLIC_BASE_URL}/media/{msg.media_path}" if msg.media_path else None
    return MessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        type=msg.type,
        body=msg.body,
        media_url=media_url,
        media_mime=msg.media_mime,
        duration_ms=msg.duration_ms,
        broadcast_group_id=msg.broadcast_group_id,
        created_at=msg.created_at,
    )
