from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..chat_common import member_ids as _member_ids, require_member as _require_member, message_out as _message_out
from ..database import get_db
from ..models import Conversation, ConversationMember, Message, User
from ..schemas import ConversationCreateRequest, ConversationOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _find_existing_direct(db: Session, user_a: int, user_b: int):
    convos = db.query(Conversation).filter(Conversation.type == "direct").all()
    for c in convos:
        ids = set(_member_ids(db, c.id))
        if ids == {user_a, user_b}:
            return c
    return None


def get_or_create_direct(db: Session, user_a: int, user_b: int) -> Conversation:
    existing = _find_existing_direct(db, user_a, user_b)
    if existing:
        return existing
    convo = Conversation(type="direct", created_by=user_a)
    db.add(convo)
    db.flush()
    db.add(ConversationMember(conversation_id=convo.id, user_id=user_a, role="member"))
    db.add(ConversationMember(conversation_id=convo.id, user_id=user_b, role="member"))
    db.commit()
    db.refresh(convo)
    return convo


def _to_out(db: Session, convo: Conversation) -> ConversationOut:
    last = (
        db.query(Message)
        .filter(Message.conversation_id == convo.id)
        .order_by(Message.created_at.desc())
        .first()
    )
    return ConversationOut(
        id=convo.id,
        type=convo.type,
        name=convo.name,
        member_ids=_member_ids(db, convo.id),
        last_message=_message_out(last) if last else None,
    )


@router.post("", response_model=ConversationOut)
def create_conversation(
    req: ConversationCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.type not in ("direct", "group"):
        raise HTTPException(400, "type must be direct or group")

    member_ids = set(req.member_ids) | {user.id}
    if req.type == "direct":
        if len(member_ids) != 2:
            raise HTTPException(400, "direct conversation needs exactly 2 members")
        other = next(iter(member_ids - {user.id}))
        convo = get_or_create_direct(db, user.id, other)
        return _to_out(db, convo)

    if len(member_ids) < 2:
        raise HTTPException(400, "group needs at least 2 members")
    convo = Conversation(type="group", name=req.name or "Group chat", created_by=user.id)
    db.add(convo)
    db.flush()
    for i, uid in enumerate(member_ids):
        db.add(ConversationMember(
            conversation_id=convo.id, user_id=uid,
            role="owner" if uid == user.id else "member",
        ))
    db.commit()
    db.refresh(convo)
    return _to_out(db, convo)


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    my_convo_ids = db.query(ConversationMember.conversation_id).filter(
        ConversationMember.user_id == user.id
    ).all()
    ids = [r[0] for r in my_convo_ids]
    convos = db.query(Conversation).filter(Conversation.id.in_(ids)).all() if ids else []
    out = [_to_out(db, c) for c in convos]
    out.sort(key=lambda c: c.last_message.created_at if c.last_message else "", reverse=True)
    return out


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = _require_member(db, conversation_id, user.id)
    return _to_out(db, convo)
