import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")


class UserOut(BaseModel):
    id: uuid.UUID
    role: Literal["guardian", "child"]
    display_name: str
    email: str | None = None
    username: str | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class RegisterGuardianIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    phone: str | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@") or " " in cleaned:
            raise ValueError("Enter a valid email address.")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name is required.")
        return cleaned


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    email: str | None = None
    username: str | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("username")
    @classmethod
    def _username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @model_validator(mode="after")
    def _one_identifier(self) -> "LoginIn":
        if bool(self.email) == bool(self.username):
            raise ValueError("Provide either an email or a username.")
        return self


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=512)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ProfilePatchIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name is required.")
        return cleaned


class AccessOut(BaseModel):
    is_paused: bool
    state_version: int
    updated_at: datetime


class ChildCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    age_band: str

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned[:1].isalpha() or not all(char.isalnum() or char == "_" for char in cleaned):
            raise ValueError("Usernames start with a letter and use letters, numbers, or underscores.")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name is required.")
        return cleaned

    @field_validator("age_band")
    @classmethod
    def _band(cls, value: str) -> str:
        if value not in AGE_BANDS:
            raise ValueError("Choose an age band: 6-8, 9-11, 12-14, or 15-17.")
        return value


class ChildOut(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    age_band: str
    created_at: datetime
    access: AccessOut


class ChildListItem(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    age_band: str
    is_paused: bool
    state_version: int
    messages_today: int


class ChildMeOut(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    age_band: str
    supervision_notice: str


class UsageDay(BaseModel):
    date: str
    count: int


class SafetyCount(BaseModel):
    category: str
    count: int


class UsageOut(BaseModel):
    messages_today: int
    conversations_today: int
    messages_last_7_days: list[UsageDay]
    safety_counts: list[SafetyCount]


class ConversationSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    summary: str | None
    ended: bool
    created_at: datetime
    updated_at: datetime


class SafetyEventOut(BaseModel):
    id: uuid.UUID
    category: str
    severity: str
    created_at: datetime
    resolution_status: str
    notification_eligible: bool
    summary: str
    recommended_action: str
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None


class ChildOverviewOut(BaseModel):
    child: ChildOut
    usage: UsageOut
    recent_safety: list[SafetyEventOut]
    recent_conversations: list[ConversationSummaryOut]


class ChildSettingsIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    age_band: str | None = None

    @field_validator("age_band")
    @classmethod
    def _band(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in AGE_BANDS:
            raise ValueError("Choose an age band: 6-8, 9-11, 12-14, or 15-17.")
        return value


class CredentialResetIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class InvitationOut(BaseModel):
    invitation_id: uuid.UUID
    code: str
    expires_at: datetime


class InvitationAcceptIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class InvitationAcceptOut(BaseModel):
    invitation_id: uuid.UUID
    child_id: uuid.UUID
    status: str


class InvitationPendingOut(BaseModel):
    invitation_id: uuid.UUID
    status: str
    expires_at: datetime
    accepted_by_display_name: str | None = None


class ReauthIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class GuardianLinkOut(BaseModel):
    guardian_id: uuid.UUID
    display_name: str
    status: str
    activated_at: datetime | None
    created_by_audit: bool


class PhoneUpdateIn(BaseModel):
    phone: str | None = Field(default=None, max_length=24)


class PhoneOut(BaseModel):
    phone: str | None
    messaging_enabled: bool
    photon_space_id: str | None = None


class PhonePrefsIn(BaseModel):
    messaging_enabled: bool
    photon_space_id: str | None = None


class ConversationCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=80)


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_role: str
    content: str | None
    restricted: bool
    child_facing_text: str | None = None
    created_at: datetime


class SendMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class SendMessageOut(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut | None
    access: AccessOut
    conversation_ended: bool = False


class CommandOut(BaseModel):
    id: uuid.UUID
    command: str
    status: str
    child_id: uuid.UUID | None
    created_at: datetime
    result: str


class CommandSelectIn(BaseModel):
    child_id: uuid.UUID
    current_password: str = Field(min_length=1, max_length=128)
