from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models import Conversation, Message, SafetyEvent
from app.schemas.api import SafetyCount, UsageDay, UsageOut


def _day_key(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:10]
    if value.tzinfo is None:
        return value.date().isoformat()
    return value.astimezone(utcnow().tzinfo).date().isoformat()


async def usage_for_child(session: AsyncSession, child_id: UUID) -> UsageOut:
    now = utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = start - timedelta(days=6)

    messages_today = await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.child_id == child_id,
            Message.sender_role == "child",
            Message.created_at >= start,
        )
    )
    conversations_today = await session.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.child_id == child_id, Conversation.created_at >= start)
    )
    stamp_rows = await session.scalars(
        select(Message.created_at)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.child_id == child_id,
            Message.sender_role == "child",
            Message.created_at >= week_start,
        )
    )
    buckets = {(start.date() - timedelta(days=offset)).isoformat(): 0 for offset in range(6, -1, -1)}
    for stamp in stamp_rows:
        key = _day_key(stamp)
        if key in buckets:
            buckets[key] += 1

    grouped = await session.execute(
        select(SafetyEvent.category, func.count())
        .where(SafetyEvent.child_id == child_id)
        .group_by(SafetyEvent.category)
    )
    return UsageOut(
        messages_today=int(messages_today or 0),
        conversations_today=int(conversations_today or 0),
        messages_last_7_days=[UsageDay(date=day, count=count) for day, count in buckets.items()],
        safety_counts=[SafetyCount(category=category, count=int(count)) for category, count in grouped.all()],
    )
