import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models import GuardianChildLink, NotificationDelivery, SafetyEvent, User
from app.services.commands import commands_text_for
from app.services.photon.service import PhotonMessagingService

logger = logging.getLogger(__name__)


async def fanout_safety_notification(
    session: AsyncSession,
    photon: PhotonMessagingService,
    event: SafetyEvent,
    child: User,
) -> None:
    """Text guardians who saved a phone. The text names the risk and category, not the child's words."""
    if not event.notification_eligible:
        return
    guardian_ids = list(
        await session.scalars(
            select(GuardianChildLink.guardian_id).where(
                GuardianChildLink.child_id == child.id,
                GuardianChildLink.status == "active",
            )
        )
    )
    if not guardian_ids:
        return
    guardians = list(await session.scalars(select(User).where(User.id.in_(guardian_ids), User.role == "guardian")))
    text = (
        f"Kinwise: a {event.severity} safety event ({event.category.replace('_', ' ')}) "
        f"was recorded for {child.display_name}. Open Kinwise for details."
    )
    for guardian in guardians:
        if not guardian.phone:
            session.add(
                NotificationDelivery(
                    id=uuid.uuid4(),
                    safety_event_id=event.id,
                    guardian_id=guardian.id,
                    channel="photon",
                    status="skipped_disabled",
                    provider_response={"reason": "No phone number is saved."},
                    created_at=utcnow(),
                )
            )
            continue
        await _deliver(session, photon, event, guardian, text, f"safety-{event.id}-{guardian.id}")
        await _deliver(
            session,
            photon,
            event,
            guardian,
            commands_text_for(child.display_name),
            f"guide-{event.id}-{guardian.id}",
        )


async def _deliver(
    session: AsyncSession,
    photon: PhotonMessagingService,
    event: SafetyEvent,
    guardian: User,
    text: str,
    idempotency_key: str,
) -> None:
    try:
        result = await photon.send_text(
            space_id=guardian.photon_space_id or "",
            text=text,
            idempotency_key=idempotency_key,
            phone=guardian.phone,
        )
    except Exception as exc:
        logger.warning("photon notification failed: %s", type(exc).__name__)
        result = {"status": "provider_error", "detail": type(exc).__name__}
    status = "sent" if result.get("status") in {"dispatched", "sent"} else str(result.get("status") or "failed")
    session.add(
        NotificationDelivery(
            id=uuid.uuid4(),
            safety_event_id=event.id,
            guardian_id=guardian.id,
            channel="photon",
            status=status,
            provider_response=result,
            created_at=utcnow(),
        )
    )
