import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_invitation_code,
    new_refresh_token,
    utcnow,
    verify_password,
    verify_password_dummy,
)
from app.models import (
    AuthSession,
    ChildAccessState,
    ChildProfile,
    GuardianAction,
    GuardianChildLink,
    GuardianInvitation,
    User,
)
from app.schemas.api import (
    ChildCreateIn,
    ChildSettingsIn,
    CredentialResetIn,
    LoginIn,
    RegisterGuardianIn,
    TokenOut,
)
from app.services.backboard.service import BackboardMemoryService
from app.services.phone import normalize_phone
from app.services.present import child_out, user_out

logger = logging.getLogger(__name__)


async def register_guardian(
    session: AsyncSession,
    body: RegisterGuardianIn,
    settings: Settings,
    user_agent: str | None,
) -> TokenOut:
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise AppError(409, "email_taken", "An account with that email already exists.")
    phone = normalize_phone(body.phone) if body.phone else None
    if phone is not None:
        taken = await session.scalar(select(User.id).where(User.phone == phone))
        if taken is not None:
            raise AppError(409, "phone_taken", "That phone number is already in use.")
    now = utcnow()
    user = User(
        id=uuid.uuid4(),
        role="guardian",
        email=body.email,
        username=None,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        phone=phone,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        if "phone" in str(getattr(exc, "orig", exc)).lower():
            raise AppError(409, "phone_taken", "That phone number is already in use.") from exc
        raise AppError(409, "email_taken", "An account with that email already exists.") from exc
    return await _issue_session(session, user, settings, user_agent)


async def login(
    session: AsyncSession,
    body: LoginIn,
    settings: Settings,
    user_agent: str | None,
) -> TokenOut:
    if body.email:
        user = await session.scalar(select(User).where(User.email == body.email, User.role == "guardian"))
    else:
        user = await session.scalar(select(User).where(User.username == body.username, User.role == "child"))
    if user is None:
        verify_password_dummy(body.password)
        raise AppError(401, "invalid_credentials", "Those credentials don't match.")
    if user.disabled_at is not None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Those credentials don't match.")
    return await _issue_session(session, user, settings, user_agent)


async def refresh_session(session: AsyncSession, raw_token: str, settings: Settings, user_agent: str | None) -> TokenOut:
    current = await _session_for_refresh(session, raw_token)
    user = await session.get(User, current.user_id)
    if user is None or user.disabled_at is not None:
        raise AppError(401, "invalid_token", "Sign in again to continue.")
    now = utcnow()
    replacement, raw = _build_session(user, settings, user_agent, now)
    current.revoked_at = now
    current.replaced_by_session_id = replacement.id
    session.add(replacement)
    await session.flush()
    return _token_out(user, replacement, settings, raw)


async def logout(session: AsyncSession, raw_token: str) -> None:
    current = await session.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(raw_token)))
    if current is None or current.revoked_at is not None:
        return
    user = await session.get(User, current.user_id)
    if user is not None and user.role == "child":
        state = await session.get(ChildAccessState, user.id)
        if state is not None and state.is_paused:
            raise AppError(
                409,
                "access_paused",
                "A guardian paused Kinwise, so sign out stays off until they resume it.",
            )
    current.revoked_at = utcnow()


async def change_password(session: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AppError(401, "invalid_credentials", "The current password doesn't match.")
    user.password_hash = hash_password(new_password)
    user.updated_at = utcnow()
    sessions = await session.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)))
    now = utcnow()
    for auth_session in sessions:
        auth_session.revoked_at = now


async def create_child(
    session: AsyncSession,
    guardian: User,
    body: ChildCreateIn,
    backboard: BackboardMemoryService,
) -> tuple[User, ChildProfile, ChildAccessState]:
    taken = await session.scalar(select(User).where(User.username == body.username))
    if taken is not None:
        raise AppError(409, "username_taken", "That username is already in use.")
    now = utcnow()
    child = User(
        id=uuid.uuid4(),
        role="child",
        username=body.username,
        email=None,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        created_at=now,
        updated_at=now,
    )
    profile = ChildProfile(
        child_id=child.id,
        age_band=body.age_band,
        created_by_guardian_id=guardian.id,
        created_at=now,
        updated_at=now,
    )
    link = GuardianChildLink(
        id=uuid.uuid4(),
        guardian_id=guardian.id,
        child_id=child.id,
        status="active",
        created_at=now,
        activated_at=now,
    )
    access = ChildAccessState(child_id=child.id, is_paused=False, state_version=1, updated_at=now)
    session.add(child)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(409, "username_taken", "That username is already in use.") from exc
    session.add_all([profile, link, access])
    await session.flush()
    try:
        assistant_id = await backboard.ensure_assistant(name=f"Kinwise {body.display_name}")
        profile.backboard_assistant_id = assistant_id
    except Exception:
        logger.warning("backboard assistant was not created for child %s", child.id)
    session.add(
        GuardianAction(
            id=uuid.uuid4(),
            guardian_id=guardian.id,
            child_id=child.id,
            action="create_child",
            source="app",
            result="created",
            created_at=now,
        )
    )
    return child, profile, access


async def reset_child_credentials(session: AsyncSession, guardian: User, child_id: uuid.UUID, body: CredentialResetIn) -> None:
    await _reauthenticate(guardian, body.current_password)
    await require_active_link(session, guardian.id, child_id)
    child = await _require_child_user(session, child_id)
    child.password_hash = hash_password(body.new_password)
    child.updated_at = utcnow()
    now = utcnow()
    sessions = await session.scalars(select(AuthSession).where(AuthSession.user_id == child.id, AuthSession.revoked_at.is_(None)))
    for auth_session in sessions:
        auth_session.revoked_at = now
    session.add(
        GuardianAction(
            id=uuid.uuid4(),
            guardian_id=guardian.id,
            child_id=child_id,
            action="reset_child_credentials",
            source="app",
            result="updated",
            created_at=now,
        )
    )


async def update_child_settings(session: AsyncSession, guardian: User, child_id: uuid.UUID, body: ChildSettingsIn) -> None:
    await require_active_link(session, guardian.id, child_id)
    child = await _require_child_user(session, child_id)
    profile = await session.get(ChildProfile, child_id)
    if profile is None:
        raise AppError(404, "not_found", "That child profile was not found.")
    if body.display_name:
        child.display_name = body.display_name.strip()
    if body.age_band:
        profile.age_band = body.age_band
    now = utcnow()
    child.updated_at = now
    profile.updated_at = now


async def create_invitation(session: AsyncSession, guardian: User, child_id: uuid.UUID) -> tuple[GuardianInvitation, str]:
    await require_active_link(session, guardian.id, child_id)
    code = new_invitation_code()
    now = utcnow()
    invitation = GuardianInvitation(
        id=uuid.uuid4(),
        child_id=child_id,
        inviting_guardian_id=guardian.id,
        code_hash=hash_token(code),
        status="open",
        expires_at=now + timedelta(hours=24),
        created_at=now,
    )
    session.add(invitation)
    session.add(
        GuardianAction(
            id=uuid.uuid4(),
            guardian_id=guardian.id,
            child_id=child_id,
            action="invite_guardian",
            source="app",
            result="issued",
            created_at=now,
        )
    )
    return invitation, code


async def accept_invitation(session: AsyncSession, guardian: User, code: str) -> GuardianInvitation:
    invitation = await session.scalar(select(GuardianInvitation).where(GuardianInvitation.code_hash == hash_token(code.strip().upper())))
    now = utcnow()
    if invitation is None or invitation.status != "open" or invitation.expires_at < now:
        raise AppError(400, "invalid_invitation", "That invitation code is invalid, expired, or already used.")
    if invitation.inviting_guardian_id == guardian.id:
        raise AppError(400, "invalid_invitation", "Ask a different guardian to enter this code.")
    existing = await session.scalar(
        select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == guardian.id,
            GuardianChildLink.child_id == invitation.child_id,
        )
    )
    if existing is not None and existing.status in {"active", "pending"}:
        raise AppError(409, "duplicate_link", "You are already connected to this child.")
    if existing is None:
        existing = GuardianChildLink(
            id=uuid.uuid4(),
            guardian_id=guardian.id,
            child_id=invitation.child_id,
            status="pending",
            created_at=now,
        )
        session.add(existing)
    else:
        existing.status = "pending"
        existing.revoked_at = None
        existing.activated_at = None
    invitation.status = "pending_confirmation"
    invitation.accepted_by_guardian_id = guardian.id
    invitation.accepted_at = now
    session.add(
        GuardianAction(
            id=uuid.uuid4(),
            guardian_id=guardian.id,
            child_id=invitation.child_id,
            action="accept_invitation",
            source="app",
            result="pending_confirmation",
            created_at=now,
        )
    )
    return invitation


async def confirm_invitation(session: AsyncSession, guardian: User, invitation_id: uuid.UUID, current_password: str) -> None:
    await _reauthenticate(guardian, current_password)
    invitation = await session.get(GuardianInvitation, invitation_id)
    if invitation is None:
        raise AppError(404, "not_found", "That invitation was not found.")
    if invitation.inviting_guardian_id != guardian.id:
        raise AppError(403, "forbidden", "Only the guardian who created the invitation can confirm it.")
    if invitation.status != "pending_confirmation" or invitation.expires_at < utcnow():
        raise AppError(400, "invalid_invitation", "That invitation is no longer waiting for confirmation.")
    if invitation.accepted_by_guardian_id is None:
        raise AppError(400, "invalid_invitation", "That invitation has not been accepted yet.")
    link = await session.scalar(
        select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == invitation.accepted_by_guardian_id,
            GuardianChildLink.child_id == invitation.child_id,
        )
    )
    if link is None:
        raise AppError(400, "invalid_invitation", "The pending guardian link is missing.")
    now = utcnow()
    link.status = "active"
    link.activated_at = now
    invitation.status = "confirmed"
    session.add(
        GuardianAction(
            id=uuid.uuid4(),
            guardian_id=guardian.id,
            child_id=invitation.child_id,
            action="confirm_invitation",
            source="app",
            result="active",
            created_at=now,
        )
    )


async def remove_guardian(
    session: AsyncSession,
    actor: User,
    child_id: uuid.UUID,
    guardian_id: uuid.UUID,
    current_password: str,
) -> None:
    await _reauthenticate(actor, current_password)
    await require_active_link(session, actor.id, child_id)
    target = await session.scalar(
        select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == guardian_id,
            GuardianChildLink.child_id == child_id,
            GuardianChildLink.status == "active",
        )
    )
    if target is None:
        raise AppError(404, "not_found", "That guardian is not actively linked.")
    active_count = await session.scalar(
        select(func.count())
        .select_from(GuardianChildLink)
        .where(GuardianChildLink.child_id == child_id, GuardianChildLink.status == "active")
    )
    if int(active_count or 0) <= 1:
        raise AppError(409, "last_guardian", "A child must keep at least one active guardian.")
    now = utcnow()
    target.status = "revoked"
    target.revoked_at = now
    session.add(
        GuardianAction(
            id=uuid.uuid4(),
            guardian_id=actor.id,
            child_id=child_id,
            action="remove_guardian",
            source="app",
            result="revoked",
            metadata_json={"removed_guardian_id": str(guardian_id)},
            created_at=now,
        )
    )


async def require_active_link(session: AsyncSession, guardian_id: uuid.UUID, child_id: uuid.UUID) -> GuardianChildLink:
    link = await session.scalar(
        select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == guardian_id,
            GuardianChildLink.child_id == child_id,
            GuardianChildLink.status == "active",
        )
    )
    if link is None:
        raise AppError(403, "forbidden", "You are not a guardian for this child.")
    return link


async def active_guardian_ids(session: AsyncSession, child_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(GuardianChildLink.guardian_id).where(
                GuardianChildLink.child_id == child_id,
                GuardianChildLink.status == "active",
            )
        )
    )


def child_response(child: User, profile: ChildProfile, state: ChildAccessState):
    return child_out(child, profile, state)


async def _require_child_user(session: AsyncSession, child_id: uuid.UUID) -> User:
    child = await session.get(User, child_id)
    if child is None or child.role != "child":
        raise AppError(404, "not_found", "That child account was not found.")
    return child


async def _reauthenticate(user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise AppError(401, "reauthentication_failed", "Enter your current password to continue.")


async def _session_for_refresh(session: AsyncSession, raw_token: str) -> AuthSession:
    current = await session.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(raw_token)))
    if current is None or current.revoked_at is not None or current.expires_at < utcnow():
        raise AppError(401, "invalid_token", "Sign in again to continue.")
    return current


def _build_session(user: User, settings: Settings, user_agent: str | None, now) -> tuple[AuthSession, str]:
    raw = new_refresh_token()
    auth_session = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        refresh_token_hash=hash_token(raw),
        expires_at=now + timedelta(days=settings.refresh_token_days),
        created_at=now,
        user_agent=(user_agent or "")[:255] or None,
    )
    return auth_session, raw


async def _issue_session(session: AsyncSession, user: User, settings: Settings, user_agent: str | None) -> TokenOut:
    auth_session, raw = _build_session(user, settings, user_agent, utcnow())
    session.add(auth_session)
    await session.flush()
    return _token_out(user, auth_session, settings, raw)


def _token_out(user: User, auth_session: AuthSession, settings: Settings, raw_refresh: str | None = None) -> TokenOut:
    if raw_refresh is None:
        raise AppError(500, "server_error", "A session could not be issued.")
    access = create_access_token(
        user_id=str(user.id),
        role=user.role,
        session_id=str(auth_session.id),
        secret=settings.jwt_secret,
        minutes=settings.access_token_minutes,
    )
    return TokenOut(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_minutes * 60,
        user=user_out(user),
    )
