import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)

from app.db.types import UTCDateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('guardian', 'child')", name="ck_users_role"),
        CheckConstraint(
            "(role = 'guardian' AND email IS NOT NULL) OR (role = 'child' AND username IS NOT NULL)",
            name="ck_users_identity",
        ),
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        Index("uq_users_username_lower", text("lower(username)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    username: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    messaging_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    photon_space_id: Mapped[str | None] = mapped_column(String(160))
    provider_identity: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ChildProfile(Base):
    __tablename__ = "child_profiles"

    child_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    age_band: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_guardian_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    backboard_assistant_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class GuardianChildLink(Base):
    __tablename__ = "guardian_child_links"
    __table_args__ = (
        UniqueConstraint("guardian_id", "child_id", name="uq_guardian_child"),
        CheckConstraint("status IN ('pending', 'active', 'revoked')", name="ck_link_status"),
        Index("ix_links_child", "child_id"),
        Index("ix_links_guardian", "guardian_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    guardian_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    child_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    replaced_by_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class GuardianInvitation(Base):
    __tablename__ = "guardian_invitations"
    __table_args__ = (
        Index("ix_invitations_child", "child_id"),
        Index("ix_invitations_code_hash", "code_hash"),
        CheckConstraint(
            "status IN ('open', 'pending_confirmation', 'confirmed', 'revoked', 'expired')",
            name="ck_invitation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    child_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    inviting_guardian_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    accepted_by_guardian_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_child", "child_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    child_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(280))
    ended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation", "conversation_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("conversations.id"), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety: Mapped[dict | None] = mapped_column(JSON)
    delivery_state: Mapped[str] = mapped_column(String(24), nullable=False, default="delivered")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class SafetyEvent(Base):
    __tablename__ = "safety_events"
    __table_args__ = (Index("ix_safety_events_child", "child_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    child_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("conversations.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("messages.id"))
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    notification_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_suppressed_reason: Mapped[str | None] = mapped_column(String(80))
    resolution_status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    summary_for_guardian: Mapped[str] = mapped_column(String(280), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))


class ChildAccessState(Base):
    __tablename__ = "child_access_state"

    child_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    pause_source: Mapped[str | None] = mapped_column(String(16))


class GuardianAction(Base):
    __tablename__ = "guardian_actions"
    __table_args__ = (Index("ix_guardian_actions_child", "child_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    guardian_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    child_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[str] = mapped_column(String(48), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_child", "child_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    child_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("conversations.id"))
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (Index("ix_deliveries_event", "safety_event_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    safety_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("safety_events.id"))
    guardian_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_response: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class PhotonCommand(Base):
    __tablename__ = "photon_commands"
    __table_args__ = (Index("ix_photon_commands_guardian", "guardian_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    guardian_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    child_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    webhook_message_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    command: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    confirmation_code_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    raw_text: Mapped[str] = mapped_column(String(280), nullable=False)
    result: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class WebhookReceipt(Base):
    __tablename__ = "webhook_receipts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
