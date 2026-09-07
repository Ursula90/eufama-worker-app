from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..call_tokens import issue_call_token
from ..chat_common import member_ids, require_member
from ..config import MAX_MESH_CALL_PARTICIPANTS, PUBLIC_BASE_URL
from ..database import get_db
from ..models import CallSession, User
from ..schemas import CallStartRequest
from ..ws_manager import app_manager

router = APIRouter(prefix="/conversations", tags=["calls"])


def _join_url(call_id: str, token: str, display_name: str, call_type: str) -> str:
    from urllib.parse import quote
    return (
        f"{PUBLIC_BASE_URL}/static/call.html?call_id={call_id}"
        f"&token={quote(token)}&name={quote(display_name)}&type={call_type}"
    )


@router.post("/{conversation_id}/calls")
async def start_call(
    conversation_id: int,
    req: CallStartRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_member(db, conversation_id, user.id)
    if req.call_type not in ("audio", "video"):
        raise HTTPException(400, "call_type must be audio or video")

    members = member_ids(db, conversation_id)
    if len(members) > MAX_MESH_CALL_PARTICIPANTS:
        raise HTTPException(
            409,
            f"group is larger than {MAX_MESH_CALL_PARTICIPANTS} participants — "
            "direct peer-to-peer calling doesn't scale past that; see README roadmap.",
        )

    call = CallSession(conversation_id=conversation_id, call_type=req.call_type, started_by=user.id)
    db.add(call)
    db.commit()
    db.refresh(call)

    my_token = issue_call_token(call.id, user.id)
    for member_id in members:
        if member_id == user.id:
            continue
        their_token = issue_call_token(call.id, member_id)
        await app_manager.send_to_user(member_id, {
            "type": "incoming_call",
            "call_id": call.id,
            "call_type": call.call_type,
            "conversation_id": conversation_id,
            "from": user.id,
            "from_name": user.display_name,
            "join_url": _join_url(call.id, their_token, user.display_name, call.call_type),
        })

    return {
        "call_id": call.id,
        "call_type": call.call_type,
        "join_url": _join_url(call.id, my_token, user.display_name, call.call_type),
    }


@router.post("/{conversation_id}/calls/{call_id}/end")
async def end_call(
    conversation_id: int,
    call_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_member(db, conversation_id, user.id)
    call = db.query(CallSession).get(call_id)
    if call is None or call.conversation_id != conversation_id:
        raise HTTPException(404, "call not found")

    call.ended_at = datetime.utcnow()
    db.commit()

    for member_id in member_ids(db, conversation_id):
        await app_manager.send_to_user(member_id, {"type": "call_ended", "call_id": call_id})

    return {"ok": True}
