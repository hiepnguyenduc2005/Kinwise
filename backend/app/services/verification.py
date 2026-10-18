from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import User
from app.services.phone import normalize_phone


async def set_guardian_phone(session: AsyncSession, guardian: User, raw_phone: str | None) -> None:
    if raw_phone is None or not raw_phone.strip():
        guardian.phone = None
        guardian.messaging_enabled = False
        guardian.provider_identity = None
        return
    phone = normalize_phone(raw_phone)
    taken = await session.scalar(select(User.id).where(User.phone == phone, User.id != guardian.id))
    if taken is not None:
        raise AppError(409, "phone_taken", "That phone number is already in use.")
    if guardian.phone != phone:
        guardian.provider_identity = None
        guardian.photon_space_id = None
    guardian.phone = phone
    guardian.messaging_enabled = True


def phone_preferences(guardian: User, *, messaging_enabled: bool, photon_space_id: str | None) -> None:
    if messaging_enabled and not guardian.phone:
        raise AppError(409, "phone_missing", "Add a phone number before enabling messaging.")
    guardian.messaging_enabled = messaging_enabled
    if photon_space_id is not None:
        cleaned = photon_space_id.strip()
        if len(cleaned) > 160:
            raise AppError(422, "invalid_space", "That conversation id is too long.")
        guardian.photon_space_id = cleaned or None
