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
    public_key: Optional[str] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    worker_id: str
    token: str
    public_key: Optional[str] = None  # uploaded/refreshed on every login


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
    encrypted: bool = False
    enc_scheme: Optional[str] = None
    enc_keys: Optional[dict] = None
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


class BroadcastRecipientCipher(BaseModel):
    user_id: int
    body: str  # ciphertext encrypted to this one recipient's public key


class BroadcastRequest(BaseModel):
    body: Optional[str] = None  # plaintext — used when not encrypting
    encrypted: bool = False
    recipients: Optional[List[BroadcastRecipientCipher]] = None  # used when encrypted


class BuzzRequest(BaseModel):
    conversation_id: int


class CallStartRequest(BaseModel):
    call_type: str  # audio | video
