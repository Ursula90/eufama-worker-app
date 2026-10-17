from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    worker_id: str
    display_name: str
    role: str
    is_online: bool
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    worker_id: str
    token: str


class LoginResponse(BaseModel):
    user: UserOut


class AdminCreateUserRequest(BaseModel):
    worker_id: str
    display_name: str
    role: str = "worker"  # worker | vip | admin


class AdminCreateUserResponse(BaseModel):
    user: UserOut
    token: str  # plaintext token, shown once — save it for device provisioning


class ConversationCreateRequest(BaseModel):
    type: str  # direct | group
    member_ids: List[int]
    name: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    type: str
    body: Optional[str] = None
    media_url: Optional[str] = None
    media_mime: Optional[str] = None
    duration_ms: Optional[int] = None
    broadcast_group_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: int
    type: str
    name: Optional[str] = None
    member_ids: List[int]
    last_message: Optional[MessageOut] = None

    class Config:
        from_attributes = True


class BroadcastRequest(BaseModel):
    body: str


class BuzzRequest(BaseModel):
    conversation_id: int


class CallStartRequest(BaseModel):
    call_type: str  # audio | video
