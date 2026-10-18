import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_guardian
from app.core.errors import AppError
from app.core.security import utcnow
from app.models import (
    ChildAccessState,
    ChildProfile,
    Conversation,
    GuardianChildLink,
    GuardianInvitation,
    Message,
    NotificationDelivery,
    PhotonCommand,
    SafetyEvent,
    UsageEvent,
    User,
)
from app.schemas.api import (
    ChildCreateIn,
    ChildListItem,
    ChildOut,
    ChildOverviewOut,
    ChildSettingsIn,
    CommandOut,
    CommandSelectIn,
    ConversationSummaryOut,
    CredentialResetIn,
    GuardianLinkOut,
    InvitationAcceptIn,
    InvitationAcceptOut,
    InvitationOut,
    InvitationPendingOut,
    MessageOut,
    PhoneOut,
    PhonePrefsIn,
    PhoneUpdateIn,
    ReauthIn,
    SafetyEventOut,
)
from app.services.accounts import (
    accept_invitation,
    confirm_invitation,
    create_child,
    create_invitation,
    remove_guardian,
    require_active_link,
    reset_child_credentials,
    update_child_settings,
)
from app.services.analytics import usage_for_child
from app.services.commands import select_command_child, set_access
from app.services.present import child_out, conversation_out, message_out, safety_out
from app.services.verification import phone_preferences, set_guardian_phone

router = APIRouter()


async def _child_bundle(session: AsyncSession, child_id: uuid.UUID):
    child = await session.get(User, child_id)
    profile = await session.get(ChildProfile, child_id)
    state = await session.get(ChildAccessState, child_id)
    if child is None or child.role != "child" or profile is None or state is None:
        raise AppError(404, "not_found", "That child account was not found.")
    return child, profile, state


@router.get("/children", response_model=list[ChildListItem])
async def list_children(
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> list[ChildListItem]:
    rows = await session.execute(
        select(User, ChildProfile, ChildAccessState)
        .join(GuardianChildLink, GuardianChildLink.child_id == User.id)
        .join(ChildProfile, ChildProfile.child_id == User.id)
        .join(ChildAccessState, ChildAccessState.child_id == User.id)
        .where(GuardianChildLink.guardian_id == guardian.id, GuardianChildLink.status == "active")
        .order_by(User.display_name.asc())
    )
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    items: list[ChildListItem] = []
    for child, profile, state in rows.all():
        messages_today = await session.scalar(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.child_id == child.id, Message.sender_role == "child", Message.created_at >= start)
        )
        items.append(
            ChildListItem(
                id=child.id,
                username=child.username or "",
                display_name=child.display_name,
                age_band=profile.age_band,
                is_paused=state.is_paused,
                state_version=state.state_version,
                messages_today=int(messages_today or 0),
            )
        )
    return items


@router.post("/children", response_model=ChildOut)
async def post_child(
    body: ChildCreateIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> ChildOut:
    child, profile, state = await create_child(session, guardian, body, request.app.state.backboard)
    return child_out(child, profile, state)


@router.get("/children/{child_id}/overview", response_model=ChildOverviewOut)
async def overview(
    child_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> ChildOverviewOut:
    await require_active_link(session, guardian.id, child_id)
    child, profile, state = await _child_bundle(session, child_id)
    conversations = await session.scalars(
        select(Conversation).where(Conversation.child_id == child_id).order_by(Conversation.updated_at.desc()).limit(8)
    )
    events = await session.scalars(
        select(SafetyEvent).where(SafetyEvent.child_id == child_id).order_by(SafetyEvent.created_at.desc()).limit(8)
    )
    return ChildOverviewOut(
        child=child_out(child, profile, state),
        usage=await usage_for_child(session, child_id),
        recent_safety=[safety_out(event) for event in events],
        recent_conversations=[conversation_out(item) for item in conversations],
    )


@router.get("/children/{child_id}/conversations", response_model=list[ConversationSummaryOut])
async def conversations(
    child_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> list[ConversationSummaryOut]:
    await require_active_link(session, guardian.id, child_id)
    rows = await session.scalars(
        select(Conversation).where(Conversation.child_id == child_id).order_by(Conversation.updated_at.desc())
    )
    return [conversation_out(item) for item in rows]


@router.get("/children/{child_id}/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def conversation_messages(
    child_id: uuid.UUID,
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> list[MessageOut]:
    await require_active_link(session, guardian.id, child_id)
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.child_id == child_id)
    )
    if conversation is None:
        raise AppError(404, "not_found", "That conversation was not found.")
    rows = await session.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()))
    return [message_out(item, for_guardian=True) for item in rows]


@router.delete("/children/{child_id}/conversations/{conversation_id}")
async def delete_conversation(
    child_id: uuid.UUID,
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> dict:
    await require_active_link(session, guardian.id, child_id)
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.child_id == child_id)
    )
    if conversation is None:
        raise AppError(404, "not_found", "That conversation was not found.")
    event_ids = list(
        await session.scalars(select(SafetyEvent.id).where(SafetyEvent.conversation_id == conversation_id))
    )
    if event_ids:
        await session.execute(delete(NotificationDelivery).where(NotificationDelivery.safety_event_id.in_(event_ids)))
    await session.execute(delete(SafetyEvent).where(SafetyEvent.conversation_id == conversation_id))
    await session.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await session.execute(delete(UsageEvent).where(UsageEvent.conversation_id == conversation_id))
    await session.delete(conversation)
    return {"status": "deleted"}


@router.get("/children/{child_id}/safety-events", response_model=list[SafetyEventOut])
async def safety_events(
    child_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> list[SafetyEventOut]:
    await require_active_link(session, guardian.id, child_id)
    rows = await session.scalars(
        select(SafetyEvent).where(SafetyEvent.child_id == child_id).order_by(SafetyEvent.created_at.desc())
    )
    return [safety_out(item) for item in rows]


@router.get("/children/{child_id}/usage")
async def usage(
    child_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
):
    await require_active_link(session, guardian.id, child_id)
    return await usage_for_child(session, child_id)


@router.post("/children/{child_id}/pause")
async def pause_child(
    child_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
):
    await require_active_link(session, guardian.id, child_id)
    state = await set_access(
        session,
        request.app.state.manager,
        guardian_id=guardian.id,
        child_id=child_id,
        paused=True,
        source="app",
    )
    return {"is_paused": state.is_paused, "state_version": state.state_version, "updated_at": state.updated_at}


@router.post("/children/{child_id}/resume")
async def resume_child(
    child_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
):
    await require_active_link(session, guardian.id, child_id)
    state = await set_access(
        session,
        request.app.state.manager,
        guardian_id=guardian.id,
        child_id=child_id,
        paused=False,
        source="app",
    )
    return {"is_paused": state.is_paused, "state_version": state.state_version, "updated_at": state.updated_at}


@router.patch("/children/{child_id}/settings", response_model=ChildOut)
async def patch_settings(
    child_id: uuid.UUID,
    body: ChildSettingsIn,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> ChildOut:
    await update_child_settings(session, guardian, child_id, body)
    child, profile, state = await _child_bundle(session, child_id)
    return child_out(child, profile, state)


@router.post("/children/{child_id}/credentials")
async def reset_credentials(
    child_id: uuid.UUID,
    body: CredentialResetIn,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> dict:
    await reset_child_credentials(session, guardian, child_id, body)
    return {"status": "credentials_updated"}


@router.post("/children/{child_id}/invitations", response_model=InvitationOut)
async def invite(
    child_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> InvitationOut:
    host = request.client.host if request.client else "unknown"
    request.app.state.rate_limiter.check(f"invite:{host}:{guardian.id}", limit=20, window_seconds=3600)
    invitation, code = await create_invitation(session, guardian, child_id)
    return InvitationOut(invitation_id=invitation.id, code=code, expires_at=invitation.expires_at)


@router.post("/invitations/accept", response_model=InvitationAcceptOut)
async def accept(
    body: InvitationAcceptIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> InvitationAcceptOut:
    host = request.client.host if request.client else "unknown"
    request.app.state.rate_limiter.check(f"accept:{host}:{guardian.id}", limit=20, window_seconds=3600)
    invitation = await accept_invitation(session, guardian, body.code)
    return InvitationAcceptOut(invitation_id=invitation.id, child_id=invitation.child_id, status=invitation.status)


@router.post("/invitations/{invitation_id}/confirm")
async def confirm(
    invitation_id: uuid.UUID,
    body: ReauthIn,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> dict:
    await confirm_invitation(session, guardian, invitation_id, body.current_password)
    return {"status": "confirmed"}


@router.get("/children/{child_id}/invitations", response_model=list[InvitationPendingOut])
async def pending_invitations(
    child_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> list[InvitationPendingOut]:
    await require_active_link(session, guardian.id, child_id)
    rows = await session.scalars(
        select(GuardianInvitation)
        .where(GuardianInvitation.child_id == child_id, GuardianInvitation.inviting_guardian_id == guardian.id)
        .order_by(GuardianInvitation.created_at.desc())
    )
    items: list[InvitationPendingOut] = []
    for invitation in rows:
        name = None
        if invitation.accepted_by_guardian_id:
            acceptor = await session.get(User, invitation.accepted_by_guardian_id)
            name = acceptor.display_name if acceptor else None
        items.append(
            InvitationPendingOut(
                invitation_id=invitation.id,
                status=invitation.status,
                expires_at=invitation.expires_at,
                accepted_by_display_name=name,
            )
        )
    return items


@router.get("/children/{child_id}/guardians", response_model=list[GuardianLinkOut])
async def guardians(
    child_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> list[GuardianLinkOut]:
    await require_active_link(session, guardian.id, child_id)
    profile = await session.get(ChildProfile, child_id)
    rows = await session.execute(
        select(GuardianChildLink, User)
        .join(User, User.id == GuardianChildLink.guardian_id)
        .where(GuardianChildLink.child_id == child_id, GuardianChildLink.status == "active")
        .order_by(User.display_name.asc())
    )
    return [
        GuardianLinkOut(
            guardian_id=user.id,
            display_name=user.display_name,
            status=link.status,
            activated_at=link.activated_at,
            created_by_audit=bool(profile and profile.created_by_guardian_id == user.id),
        )
        for link, user in rows.all()
    ]


@router.delete("/children/{child_id}/guardians/{guardian_id}")
async def delete_guardian(
    child_id: uuid.UUID,
    guardian_id: uuid.UUID,
    body: ReauthIn,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> dict:
    await remove_guardian(session, guardian, child_id, guardian_id, body.current_password)
    return {"status": "revoked"}


@router.get("/phone", response_model=PhoneOut)
async def get_phone(guardian: User = Depends(require_guardian)) -> PhoneOut:
    return _phone_out(guardian)


@router.patch("/phone", response_model=PhoneOut)
async def update_phone(
    body: PhoneUpdateIn,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> PhoneOut:
    await set_guardian_phone(session, guardian, body.phone)
    return _phone_out(guardian)


@router.patch("/phone/preferences", response_model=PhoneOut)
async def patch_phone(
    body: PhonePrefsIn,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> PhoneOut:
    phone_preferences(guardian, messaging_enabled=body.messaging_enabled, photon_space_id=body.photon_space_id)
    await session.flush()
    return _phone_out(guardian)


@router.post("/safety-events/{event_id}/acknowledge", response_model=SafetyEventOut)
async def acknowledge(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> SafetyEventOut:
    event = await session.get(SafetyEvent, event_id)
    if event is None:
        raise AppError(404, "not_found", "That safety event was not found.")
    await require_active_link(session, guardian.id, event.child_id)
    event.resolution_status = "acknowledged"
    event.acknowledged_at = utcnow()
    event.acknowledged_by = guardian.id
    return safety_out(event)


@router.delete("/children/{child_id}/memory")
async def delete_memory(
    child_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> dict:
    await require_active_link(session, guardian.id, child_id)
    profile = await session.get(ChildProfile, child_id)
    deleted = 0
    if profile and profile.backboard_assistant_id:
        try:
            deleted = await request.app.state.backboard.delete_child_memory(profile.backboard_assistant_id)
        except Exception as exc:
            raise AppError(502, "memory_delete_failed", "Memory could not be deleted right now.") from exc
    return {"deleted": deleted}


@router.get("/commands", response_model=list[CommandOut])
async def list_commands(
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> list[CommandOut]:
    rows = await session.scalars(
        select(PhotonCommand)
        .where(PhotonCommand.guardian_id == guardian.id)
        .order_by(PhotonCommand.created_at.desc())
        .limit(30)
    )
    return [
        CommandOut(id=row.id, command=row.command, status=row.status, child_id=row.child_id, created_at=row.created_at, result=row.result)
        for row in rows
    ]


@router.post("/commands/{command_id}/select", response_model=CommandOut)
async def select_command(
    command_id: uuid.UUID,
    body: CommandSelectIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guardian: User = Depends(require_guardian),
) -> CommandOut:
    row = await select_command_child(
        session,
        request.app.state.manager,
        guardian,
        command_id,
        body.child_id,
        body.current_password,
    )
    return CommandOut(id=row.id, command=row.command, status=row.status, child_id=row.child_id, created_at=row.created_at, result=row.result)


def _phone_out(guardian: User) -> PhoneOut:
    return PhoneOut(
        phone=guardian.phone,
        messaging_enabled=guardian.messaging_enabled,
        photon_space_id=guardian.photon_space_id,
    )
