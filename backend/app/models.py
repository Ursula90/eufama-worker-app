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
