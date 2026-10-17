import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..chat_common import member_ids, message_out as _message_out, require_member
from ..config import MAX_UPLOAD_BYTES, MEDIA_DIR
from ..database import get_db
from ..models import Message, User
from ..schemas import MessageOut
from ..ws_manager import app_manager

router = APIRouter(prefix="/conversations", tags=["messages"])

ALLOWED_TYPES = {"text", "image", "file", "voice"}


def _save_upload(upload: UploadFile) -> tuple[str, str, int]:
    """Returns (relative_path, mime, size_bytes)."""
    ext = os.path.splitext(upload.filename or "")[1][:16]
    name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(MEDIA_DIR, name)

    size = 0
    with open(dest, "wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.remove(dest)
                raise HTTPException(413, "file too large")
            out.write(chunk)
    return name, upload.content_type or "application/octet-stream", size


@router.post("/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: int,
    type: str = Form("text"),
    body: str | None = Form(None),
    duration_ms: int | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_member(db, conversation_id, user.id)
    if type not in ALLOWED_TYPES:
        raise HTTPException(400, f"type must be one of {sorted(ALLOWED_TYPES)}")
    if type != "text" and file is None:
        raise HTTPException(400, f"{type} messages require a file upload")
    if type == "text" and not (body and body.strip()):
        raise HTTPException(400, "text messages require a non-empty body")

    media_path = media_mime = None
    media_size = None
    if file is not None:
        media_path, media_mime, media_size = _save_upload(file)

    msg = Message(
        conversation_id=conversation_id,
        sender_id=user.id,
        type=type,
        body=body,
        media_path=media_path,
        media_mime=media_mime,
        media_size=media_size,
        duration_ms=duration_ms,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    out = _message_out(msg)
    recipients = [uid for uid in member_ids(db, conversation_id) if uid != user.id]
    await app_manager.send_to_users(recipients, {"type": "message", "message": out.model_dump(mode="json")})
    return out


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: int,
    since_id: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_member(db, conversation_id, user.id)
    limit = max(1, min(limit, 200))
    q = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.id > since_id)
        .order_by(Message.id.asc())
        .limit(limit)
    )
    return [_message_out(m) for m in q.all()]
