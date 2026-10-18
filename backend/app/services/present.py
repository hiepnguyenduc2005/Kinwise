import uuid

from app.models import (
    ChildAccessState,
    ChildProfile,
    Conversation,
    GuardianChildLink,
    Message,
    SafetyEvent,
    User,
)
from app.schemas.api import (
    AccessOut,
    ChildOut,
    ConversationSummaryOut,
    MessageOut,
    SafetyEventOut,
    UserOut,
)

SUPERVISION_NOTICE = (
    "A linked guardian can see your ordinary conversations, usage, and safety alerts. "
    "If Kinwise closes a chat to keep you safe, a linked guardian can still read what was said. "
    "A high or critical event sends guardians a text that does not include what you wrote."
)

CHILD_CLOSED_TEXT = "Kinwise closed this chat to keep you safe."


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        role=user.role,  # type: ignore[arg-type]
        display_name=user.display_name,
        email=user.email,
        username=user.username,
    )


def access_out(state: ChildAccessState) -> AccessOut:
    return AccessOut(is_paused=state.is_paused, state_version=state.state_version, updated_at=state.updated_at)


def child_out(user: User, profile: ChildProfile, state: ChildAccessState) -> ChildOut:
    return ChildOut(
        id=user.id,
        username=user.username or "",
        display_name=user.display_name,
        age_band=profile.age_band,
        created_at=user.created_at,
        access=access_out(state),
    )


def message_out(message: Message, *, for_guardian: bool) -> MessageOut:
    if message.restricted and not for_guardian:
        return MessageOut(
            id=message.id,
            sender_role=message.sender_role,
            content=CHILD_CLOSED_TEXT,
            restricted=True,
            created_at=message.created_at,
        )
    return MessageOut(
        id=message.id,
        sender_role=message.sender_role,
        content=message.content,
        restricted=message.restricted,
        child_facing_text=CHILD_CLOSED_TEXT if message.restricted else None,
        created_at=message.created_at,
    )


def conversation_out(conversation: Conversation, *, for_child: bool = False) -> ConversationSummaryOut:
    if for_child and conversation.ended:
        title = "Closed conversation"
        summary = CHILD_CLOSED_TEXT
    else:
        title = conversation.title
        summary = conversation.summary
    return ConversationSummaryOut(
        id=conversation.id,
        title=title,
        summary=summary,
        ended=conversation.ended,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def safety_out(event: SafetyEvent) -> SafetyEventOut:
    if event.notification_eligible:
        action = "A text and a phone alert were sent. The text does not include the child's words."
    else:
        action = "No phone alert was required for this event."
    return SafetyEventOut(
        id=event.id,
        category=event.category,
        severity=event.severity,
        created_at=event.created_at,
        resolution_status=event.resolution_status,
        notification_eligible=event.notification_eligible,
        summary=event.summary_for_guardian,
        recommended_action=action,
        conversation_id=event.conversation_id,
        message_id=event.message_id,
    )


def access_payload(child_id: uuid.UUID, state: ChildAccessState) -> dict:
    return {
        "type": "access_state",
        "child_id": str(child_id),
        "is_paused": state.is_paused,
        "state_version": state.state_version,
        "updated_at": state.updated_at.isoformat(),
    }


def link_is_active(link: GuardianChildLink | None) -> bool:
    return link is not None and link.status == "active"
