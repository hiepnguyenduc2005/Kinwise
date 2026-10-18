"""Create synthetic Kinwise demo accounts and conversations.

Never put real children's information in this script. Passwords are hashed
with Argon2id and are not stored in plaintext.

Accounts
- ada@kinwise.demo / DemoPass123
- sam@kinwise.demo / DemoPass123
- alex / DemoPass123
"""

import asyncio
import sys
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.security import hash_password, utcnow
from app.db.base import Base
from app.db.session import create_sessionmaker
from app.main import create_app
from app.models import (
    ChildAccessState,
    ChildProfile,
    Conversation,
    GuardianChildLink,
    Message,
    SafetyEvent,
    UsageEvent,
    User,
)
from sqlalchemy import select


async def _user_by_email(session, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def _user_by_username(session, username: str) -> User | None:
    return await session.scalar(select(User).where(User.username == username))


async def seed() -> None:
    settings = get_settings()
    app = create_app(settings)
    engine = app.state.engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = create_sessionmaker(engine)
    now = utcnow()
    async with maker() as session:
        ada = await _user_by_email(session, "ada@kinwise.demo")
        if ada is None:
            ada = User(
                id=uuid.uuid4(),
                role="guardian",
                email="ada@kinwise.demo",
                password_hash=hash_password("DemoPass123"),
                display_name="Ada",
                created_at=now,
                updated_at=now,
            )
            session.add(ada)
            await session.flush()
        sam = await _user_by_email(session, "sam@kinwise.demo")
        if sam is None:
            sam = User(
                id=uuid.uuid4(),
                role="guardian",
                email="sam@kinwise.demo",
                password_hash=hash_password("DemoPass123"),
                display_name="Sam",
                created_at=now,
                updated_at=now,
            )
            session.add(sam)
            await session.flush()
        alex = await _user_by_username(session, "alex")
        if alex is None:
            alex = User(
                id=uuid.uuid4(),
                role="child",
                username="alex",
                password_hash=hash_password("DemoPass123"),
                display_name="Alex",
                created_at=now,
                updated_at=now,
            )
            session.add(alex)
            await session.flush()
            session.add(
                ChildProfile(
                    child_id=alex.id,
                    age_band="9-11",
                    created_by_guardian_id=ada.id,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(ChildAccessState(child_id=alex.id, is_paused=False, state_version=1, updated_at=now))
        for guardian in (ada, sam):
            existing = await session.scalar(
                select(GuardianChildLink).where(
                    GuardianChildLink.guardian_id == guardian.id,
                    GuardianChildLink.child_id == alex.id,
                )
            )
            if existing is None:
                session.add(
                    GuardianChildLink(
                        id=uuid.uuid4(),
                        guardian_id=guardian.id,
                        child_id=alex.id,
                        status="active",
                        created_at=now,
                        activated_at=now,
                    )
                )
        already = await session.scalar(select(Conversation).where(Conversation.child_id == alex.id))
        if already is None:
            earlier = now - timedelta(hours=2)
            conversation = Conversation(
                id=uuid.uuid4(),
                child_id=alex.id,
                title="Volcano science fair",
                summary="Alex is building a volcano for a science fair.",
                ended=False,
                created_at=earlier,
                updated_at=earlier,
            )
            session.add(conversation)
            session.add_all(
                [
                    Message(
                        id=uuid.uuid4(),
                        conversation_id=conversation.id,
                        sender_role="child",
                        content="I'm building a volcano for my science fair.",
                        restricted=False,
                        delivery_state="delivered",
                        created_at=earlier,
                    ),
                    Message(
                        id=uuid.uuid4(),
                        conversation_id=conversation.id,
                        sender_role="assistant",
                        content="A baking-soda volcano is a friendly way to watch a chemical reaction. We can plan the labels for your board next.",
                        restricted=False,
                        delivery_state="delivered",
                        created_at=earlier + timedelta(seconds=2),
                    ),
                    UsageEvent(
                        id=uuid.uuid4(),
                        child_id=alex.id,
                        conversation_id=conversation.id,
                        event_type="message_sent",
                        created_at=earlier,
                    ),
                ]
            )
            restricted = Conversation(
                id=uuid.uuid4(),
                child_id=alex.id,
                title="Restricted conversation",
                summary="Synthetic demo disclosure used only to show the guardian transcript.",
                ended=True,
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=30),
            )
            session.add(restricted)
            hidden = Message(
                id=uuid.uuid4(),
                conversation_id=restricted.id,
                sender_role="child",
                content="Synthetic demo disclosure used only to show guardian redaction.",
                restricted=True,
                delivery_state="delivered",
                created_at=now - timedelta(minutes=30),
            )
            session.add(hidden)
            session.add(
                SafetyEvent(
                    id=uuid.uuid4(),
                    child_id=alex.id,
                    conversation_id=restricted.id,
                    message_id=hidden.id,
                    category="self_harm",
                    severity="high",
                    notification_eligible=True,
                    notify_suppressed_reason=None,
                    resolution_status="open",
                    summary_for_guardian="A safeguarding restriction applies. Details are not shown to linked guardians.",
                    created_at=now - timedelta(minutes=30),
                )
            )
        await session.commit()
    await engine.dispose()
    print("Demo accounts are ready.")
    print("Guardian Ada: ada@kinwise.demo / DemoPass123")
    print("Guardian Sam: sam@kinwise.demo / DemoPass123")
    print("Child Alex: alex / DemoPass123")


if __name__ == "__main__":
    asyncio.run(seed())
