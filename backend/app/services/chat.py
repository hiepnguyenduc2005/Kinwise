import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.models import ChildAccessState, ChildProfile, Conversation, Message, SafetyEvent, UsageEvent, User
from app.schemas.api import ConversationCreateIn, SendMessageIn, SendMessageOut
from app.services.backboard.service import BackboardMemoryService
from app.services.gemini.client import GeminiError, GoogleGeminiClient
from app.services.notifications import fanout_safety_notification
from app.services.photon.service import PhotonMessagingService
from app.services.present import access_out, conversation_out, message_out
from app.services.safety.policy import evaluate_turn
from app.services.safety.prompts import SYSTEM_INSTRUCTION, build_prompt

logger = logging.getLogger(__name__)


async def create_conversation(session: AsyncSession, child: User, body: ConversationCreateIn) -> Conversation:
    now = utcnow()
    conversation = Conversation(
        id=uuid.uuid4(),
        child_id=child.id,
        title=(body.title or "New conversation").strip() or "New conversation",
        ended=False,
        created_at=now,
        updated_at=now,
    )
    session.add(conversation)
    session.add(
        UsageEvent(
            id=uuid.uuid4(),
            child_id=child.id,
            conversation_id=conversation.id,
            event_type="conversation_created",
            created_at=now,
        )
    )
    await session.flush()
    return conversation


async def list_conversations(session: AsyncSession, child_id: uuid.UUID) -> list[Conversation]:
    rows = await session.scalars(
        select(Conversation).where(Conversation.child_id == child_id).order_by(Conversation.updated_at.desc())
    )
    return list(rows)


async def list_messages(session: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    rows = await session.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    )
    return list(rows)


async def owned_conversation(session: AsyncSession, child_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.child_id == child_id)
    )
    if conversation is None:
        raise AppError(404, "not_found", "That conversation was not found.")
    return conversation


async def send_child_message(
    session: AsyncSession,
    *,
    settings: Settings,
    gemini: GoogleGeminiClient,
    backboard: BackboardMemoryService,
    photon: PhotonMessagingService,
    child: User,
    conversation_id: uuid.UUID,
    body: SendMessageIn,
) -> SendMessageOut:
    conversation = await owned_conversation(session, child.id, conversation_id)
    if conversation.ended:
        raise AppError(409, "conversation_ended", "Kinwise closed this chat to keep you safe.")
    state = await _access_state(session, child.id)
    if state.is_paused:
        raise AppError(409, "access_paused", "Kinwise is paused right now. A guardian can turn it back on.")

    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.child_id == child.id, Message.sender_role == "child", Message.created_at >= start)
    )
    if int(sent_today or 0) >= settings.daily_message_limit:
        raise AppError(429, "usage_limit", "Today's message limit has been reached.")

    now = utcnow()
    user_message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        sender_role="child",
        content=body.content.strip(),
        restricted=False,
        delivery_state="delivered",
        created_at=now,
    )
    session.add(user_message)
    session.add(
        UsageEvent(
            id=uuid.uuid4(),
            child_id=child.id,
            conversation_id=conversation.id,
            event_type="message_sent",
            created_at=now,
        )
    )
    await session.commit()

    profile = await session.get(ChildProfile, child.id)
    if profile is None:
        raise AppError(404, "not_found", "That child profile was not found.")

    memories = await _memories(backboard, profile.backboard_assistant_id, body.content)
    history = await _history(session, conversation.id, exclude=user_message.id)
    prompt = build_prompt(
        age_band=profile.age_band,
        display_name=child.display_name,
        memories=memories,
        history=history,
        child_message=user_message.content,
    )

    raw: str | None = None
    failure: str | None = None
    try:
        raw = await gemini.generate_turn(system_instruction=SYSTEM_INSTRUCTION, prompt=prompt)
    except GeminiError as exc:
        failure = exc.code

    decision = evaluate_turn(
        child_text=user_message.content,
        age_band=profile.age_band,
        raw_model_output=raw,
        failure=failure,
    )

    await session.refresh(state)
    close_chat = decision.risk_level in {"high", "critical"}
    user_message.restricted = close_chat
    if close_chat:
        conversation.ended = True
    if conversation.title == "New conversation":
        conversation.title = user_message.content[:48]
    if decision.conversation_summary:
        conversation.summary = decision.conversation_summary

    event = None
    if decision.record_event:
        event = SafetyEvent(
            id=uuid.uuid4(),
            child_id=child.id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            category=decision.categories[0] if decision.categories else "general",
            severity=decision.severity,
            notification_eligible=decision.notification_eligible,
            notify_suppressed_reason=decision.notify_suppressed_reason,
            resolution_status="open",
            summary_for_guardian=decision.summary_for_guardian,
            created_at=utcnow(),
        )
        session.add(event)

    if state.is_paused:
        await session.commit()
        raise AppError(409, "response_withheld", "Kinwise was paused before a reply could be delivered.")

    assistant = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        sender_role="assistant",
        content=decision.final_text,
        restricted=close_chat,
        safety={
            "risk_level": decision.risk_level,
            "categories": decision.categories,
            "source": decision.source,
            "reason": decision.reason,
        },
        delivery_state="fallback" if decision.source != "model" else "delivered",
        created_at=utcnow(),
    )
    session.add(assistant)
    conversation.updated_at = assistant.created_at

    if decision.store_memory and profile.backboard_assistant_id:
        try:
            await backboard.store_memory(
                profile.backboard_assistant_id,
                user_message.content,
                metadata={"child_id": str(child.id), "source": "kinwise"},
            )
        except Exception:
            logger.warning("backboard memory was not stored for child %s", child.id)

    if event is not None:
        await fanout_safety_notification(session, photon, event, child)

    await session.flush()
    return SendMessageOut(
        user_message=message_out(user_message, for_guardian=False),
        assistant_message=message_out(assistant, for_guardian=False),
        access=access_out(state),
        conversation_ended=conversation.ended,
    )


def serialize_conversation(conversation: Conversation):
    return conversation_out(conversation, for_child=True)


async def _access_state(session: AsyncSession, child_id: uuid.UUID) -> ChildAccessState:
    state = await session.get(ChildAccessState, child_id)
    if state is None:
        raise AppError(409, "access_missing", "Access state is not available for this account.")
    return state


async def _memories(backboard: BackboardMemoryService, assistant_id: str | None, query: str) -> list[str]:
    if not assistant_id:
        return []
    try:
        return await backboard.retrieve_context(assistant_id, query)
    except Exception:
        logger.warning("backboard retrieval failed")
        return []


async def _history(session: AsyncSession, conversation_id: uuid.UUID, exclude: uuid.UUID) -> list[tuple[str, str]]:
    rows = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.id != exclude, Message.delivery_state != "withheld")
            .order_by(Message.created_at.desc())
            .limit(8)
        )
    )
    rows.reverse()
    history: list[tuple[str, str]] = []
    for row in rows:
        if row.restricted:
            continue
        speaker = "Child" if row.sender_role == "child" else "Kinwise"
        history.append((speaker, row.content[:400]))
    return history
