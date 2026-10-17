import uuid
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    worker_id = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(120), nullable=False)
    token_hash = Column(String(128), nullable=False)
    # "worker" | "vip" | "admin" — vip/admin may broadcast to everyone.
    role = Column(String(16), nullable=False, default="worker")
    avatar_path = Column(String(255), nullable=True)
    is_online = Column(Boolean, default=False, nullable=False)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Base64 X25519 public key (PyNaCl), uploaded by the client after it
    # generates its keypair on first login. The matching private key never
    # leaves the device. Null until the client has logged in at least once
    # post-upgrade — older messages / accounts stay unencrypted until then.
    public_key = Column(String(64), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    # "direct" | "group"
    type = Column(String(16), nullable=False)
    name = Column(String(120), nullable=True)  # group name only
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    members = relationship("ConversationMember", cascade="all, delete-orphan")


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id"),)

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(16), nullable=False, default="member")  # member | owner
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # "text" | "image" | "file" | "voice" | "system"
    type = Column(String(16), nullable=False, default="text")
    body = Column(Text, nullable=True)
    media_path = Column(String(255), nullable=True)
    media_mime = Column(String(120), nullable=True)
    media_size = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)  # voice notes
    # groups together messages fanned out from one VIP broadcast action
    broadcast_group_id = Column(String(32), nullable=True, index=True)
    # End-to-end encryption (text only — see README). When True, `body`
    # is opaque ciphertext the server never decrypts.
    # "direct": body is a base64 nacl.public.Box encrypted message.
    # "group":  body is a base64 nacl.secret.SecretBox ciphertext of the
    #           text, encrypted with a random per-message key; enc_keys
    #           holds that key sealed (nacl.public.SealedBox) separately
    #           for each recipient, so each can unwrap only their own copy.
    encrypted = Column(Boolean, default=False, nullable=False)
    enc_scheme = Column(String(16), nullable=True)
    enc_keys = Column(Text, nullable=True)  # JSON: {user_id: sealed_key_b64}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    sender = relationship("User")


class ReadReceipt(Base):
    __tablename__ = "read_receipts"
    __table_args__ = (UniqueConstraint("message_id", "user_id"),)

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(String(32), primary_key=True, default=_uuid)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    call_type = Column(String(8), nullable=False)  # audio | video
    started_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
