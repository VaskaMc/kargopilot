"""KargoPilot v4.5 Security and Identity Data Models.

Defines schemas for Users, Sessions, Token Families, WhatsApp Bindings,
Conversation States, Admin Ephemeral Challenges, and Structured Auth Audit Logs.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

try:
    from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

    class Base(DeclarativeBase):
        pass

    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    Base = object  # type: ignore


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    """Generate canonical UUIDv4 string."""
    return str(uuid.uuid4())


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"  # Logistics operator
    CUSTOMER = "CUSTOMER"  # Regular customer / shopper


class WhatsAppUserState(str, Enum):
    UNREGISTERED = "UNREGISTERED"
    AWAITING_CHOICE = "AWAITING_CHOICE"
    AWAITING_REGISTRATION_OTP = "AWAITING_REGISTRATION_OTP"
    AWAITING_WEB_LINK_CODE = "AWAITING_WEB_LINK_CODE"
    ACTIVE_BOUND = "ACTIVE_BOUND"
    BLOCKED = "BLOCKED"


class AuthChannel(str, Enum):
    WEB = "WEB"
    WHATSAPP_BOT = "WHATSAPP_BOT"
    REST_API = "REST_API"
    BACKGROUND_WORKER = "BACKGROUND_WORKER"


class AuditEventType(str, Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    LOGOUT_ALL_SESSIONS = "LOGOUT_ALL_SESSIONS"
    TOKEN_REFRESH_SUCCESS = "TOKEN_REFRESH_SUCCESS"
    TOKEN_REUSE_DETECTED = "TOKEN_REUSE_DETECTED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    PASSWORD_CHANGE_SUCCESS = "PASSWORD_CHANGE_SUCCESS"
    PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    PASSWORD_RESET_SUCCESS = "PASSWORD_RESET_SUCCESS"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_UNLOCKED = "ACCOUNT_UNLOCKED"
    WA_BIND_REQUEST = "WA_BIND_REQUEST"
    WA_BIND_SUCCESS = "WA_BIND_SUCCESS"
    WA_BIND_FAILED = "WA_BIND_FAILED"
    WA_UNBIND = "WA_UNBIND"
    ADMIN_COMMAND_ATTEMPT = "ADMIN_COMMAND_ATTEMPT"
    ADMIN_COMMAND_SUCCESS = "ADMIN_COMMAND_SUCCESS"
    ADMIN_COMMAND_DENIED = "ADMIN_COMMAND_DENIED"
    ADMIN_CHALLENGE_ISSUED = "ADMIN_CHALLENGE_ISSUED"
    ADMIN_CHALLENGE_VERIFIED = "ADMIN_CHALLENGE_VERIFIED"
    ADMIN_CHALLENGE_FAILED = "ADMIN_CHALLENGE_FAILED"
    ROLE_CHANGE = "ROLE_CHANGE"
    PERMISSION_DENIED = "PERMISSION_DENIED"


if HAS_SQLALCHEMY:

    class User(Base):
        __tablename__ = "users"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
        email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
        password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
        full_name: Mapped[str] = mapped_column(String(120), nullable=False)
        phone: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True)
        role: Mapped[str] = mapped_column(String(32), default=UserRole.CUSTOMER.value, index=True, nullable=False)
        is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
        failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
        locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
        updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
        )

        sessions: Mapped[list["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
        whatsapp_binding: Mapped[Optional["WhatsAppBinding"]] = relationship("WhatsAppBinding", back_populates="user", uselist=False)

    class UserSession(Base):
        __tablename__ = "user_sessions"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
        user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
        family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
        current_refresh_token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
        device_fingerprint: Mapped[Optional[str]] = mapped_column(String(128))
        ip_address: Mapped[Optional[str]] = mapped_column(String(45))
        user_agent: Mapped[Optional[str]] = mapped_column(Text)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
        last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
        expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
        revocation_reason: Mapped[Optional[str]] = mapped_column(String(64))

        user: Mapped["User"] = relationship("User", back_populates="sessions")
        refresh_tokens: Mapped[list["RefreshTokenRecord"]] = relationship("RefreshTokenRecord", back_populates="session", cascade="all, delete-orphan")

    class RefreshTokenRecord(Base):
        __tablename__ = "refresh_token_records"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
        session_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
        family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
        token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
        is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
        revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
        expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

        session: Mapped["UserSession"] = relationship("UserSession", back_populates="refresh_tokens")

    class WhatsAppBinding(Base):
        __tablename__ = "user_whatsapp_bindings"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
        user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
        whatsapp_jid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
        phone_e164: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
        verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
        is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

        user: Mapped["User"] = relationship("User", back_populates="whatsapp_binding")

    class WhatsAppConversationState(Base):
        __tablename__ = "whatsapp_conversation_states"

        whatsapp_jid: Mapped[str] = mapped_column(String(64), primary_key=True)
        current_state: Mapped[str] = mapped_column(String(32), default=WhatsAppUserState.UNREGISTERED.value, nullable=False)
        pending_phone: Mapped[Optional[str]] = mapped_column(String(32))
        challenge_otp_hash: Mapped[Optional[str]] = mapped_column(String(64))
        challenge_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
        challenge_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
        binding_code_hash: Mapped[Optional[str]] = mapped_column(String(64))
        context_payload: Mapped[Optional[str]] = mapped_column(Text)
        last_interaction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    class AdminChallenge(Base):
        __tablename__ = "admin_challenges"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
        user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
        whatsapp_jid: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
        action_type: Mapped[str] = mapped_column(String(64), nullable=False)
        challenge_code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
        status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
        expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    class AuthAuditLog(Base):
        __tablename__ = "auth_audit_logs"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
        event_id: Mapped[str] = mapped_column(String(36), index=True, default=gen_uuid, nullable=False)
        timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
        user_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
        actor_role: Mapped[Optional[str]] = mapped_column(String(32))
        event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
        ip_address: Mapped[Optional[str]] = mapped_column(String(45), index=True)
        user_agent: Mapped[Optional[str]] = mapped_column(Text)
        channel: Mapped[str] = mapped_column(String(32), default=AuthChannel.WEB.value, nullable=False)
        status: Mapped[str] = mapped_column(String(16), nullable=False)  # SUCCESS, FAILED, DENIED, BLOCKED
        reason: Mapped[Optional[str]] = mapped_column(String(255))
        metadata_json: Mapped[Optional[str]] = mapped_column(Text)

        __table_args__ = (
            Index("idx_auth_audit_event_time", "event_type", "timestamp"),
            Index("idx_auth_audit_user_time", "user_id", "timestamp"),
        )
