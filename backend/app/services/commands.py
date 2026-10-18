import logging
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow, verify_password
from app.models import (
    ChildAccessState,
    GuardianAction,
    GuardianChildLink,
    PhotonCommand,
    User,
    WebhookReceipt,
)
from app.realtime.manager import ConnectionManager
from app.services.photon.service import PhotonMessagingService
from app.services.present import access_payload

logger = logging.getLogger(__name__)

COMMANDS_TEXT = "Kinwise commands are STATUS, PAUSE, and RESUME."


def commands_text_for(display_name: str) -> str:
    return f"Kinwise commands for kid {display_name} are STATUS, PAUSE, and RESUME."


def parse_command(text: str) -> tuple[str, str | None]:
    parts = text.strip().split()
    if not parts:
        return "unknown", None
    head = parts[0].lower()
    if head not in {"status", "pause", "resume"}:
        return "unknown", None
    argument = parts[1].strip() if len(parts) > 1 else None
    return head, argument


async def process_inbound_message(
    session: AsyncSession,
    *,
    photon: PhotonMessagingService,
    manager: ConnectionManager,
    payload: dict,
) -> dict:
    message = payload.get("message") or {}
    message_id = str(message.get("id") or "")
    if payload.get("event") != "messages" or not message_id:
        return {"status": "ignored"}
    if message.get("direction") not in {None, "inbound"}:
        return {"status": "ignored"}
    content = message.get("content") or {}
    if content.get("type") not in {None, "text"}:
        return {"status": "ignored"}

    existing = await session.scalar(select(PhotonCommand).where(PhotonCommand.webhook_message_id == message_id))
    if existing is not None:
        return {"status": "duplicate", "command_id": str(existing.id)}

    receipt = await session.scalar(select(WebhookReceipt).where(WebhookReceipt.external_id == message_id))
    if receipt is None:
        session.add(
            WebhookReceipt(
                id=uuid.uuid4(),
                provider="photon",
                external_id=message_id,
                received_at=utcnow(),
            )
        )

    sender = str((message.get("sender") or {}).get("id") or "")
    text = str(content.get("text") or "")
    space = payload.get("space") or {}
    guardian = await _match_guardian_phone(session, sender)
    if guardian is None or not guardian.phone:
        session.add(
            _command(
                guardian_id=guardian.id if guardian else None,
                message_id=message_id,
                command="unknown",
                status="rejected",
                result="unauthorized",
                raw_text=text,
            )
        )
        return {"status": "rejected"}

    guardian.provider_identity = sender[:128]
    space_id = str(space.get("id") or "")
    if space_id:
        guardian.photon_space_id = space_id[:160]

    command, argument = parse_command(text)
    children = await _linked_children(session, guardian.id)
    reply_space = guardian.photon_space_id or ""

    if command == "status":
        summary = _status_summary(children)
        row = _command(
            guardian_id=guardian.id,
            message_id=message_id,
            command="status",
            status="executed",
            result="ok",
            raw_text=text,
            child_id=children[0][1].id if len(children) == 1 else None,
        )
        row.executed_at = utcnow()
        session.add(row)
        await _reply(photon, reply_space, summary, f"status-{message_id}")
        return {"status": "executed"}

    if command in {"pause", "resume"}:
        target = _select_child(children, argument)
        if target is None:
            row = _command(
                guardian_id=guardian.id,
                message_id=message_id,
                command=command,
                status="needs_child_selection" if len(children) > 1 and not argument else "rejected",
                result="needs_child_selection" if len(children) > 1 and not argument else "unknown_child",
                raw_text=text,
            )
            session.add(row)
            names = ", ".join(user.username or "" for _, user in children)
            await _reply(
                photon,
                reply_space,
                f"You supervise more than one child. Reply {command.upper()} and a username. Usernames: {names}.",
                f"select-{message_id}",
            )
            return {"status": row.status}

        _state, child_user = target
        pausing = command == "pause"
        child_name = child_user.display_name
        row = _command(
            guardian_id=guardian.id,
            message_id=message_id,
            command=command,
            status="executed",
            result="paused" if pausing else "active",
            raw_text=text,
            child_id=child_user.id,
        )
        row.executed_at = utcnow()
        session.add(row)
        await _apply_access_change(
            session,
            manager,
            guardian_id=guardian.id,
            child_id=child_user.id,
            pausing=pausing,
            source="photon",
        )
        verb = "paused" if pausing else "resumed"
        await _reply(
            photon,
            reply_space,
            f"Kinwise {verb} {child_name}.",
            f"access-{message_id}",
        )
        return {"status": "executed", "command_id": str(row.id)}

    session.add(
        _command(
            guardian_id=guardian.id,
            message_id=message_id,
            command="unknown",
            status="rejected",
            result="unknown_command",
            raw_text=text,
        )
    )
    await _reply(photon, reply_space, COMMANDS_TEXT, f"unknown-{message_id}")
    return {"status": "rejected"}


async def select_command_child(
    session: AsyncSession,
    manager: ConnectionManager,
    guardian: User,
    command_id: uuid.UUID,
    child_id: uuid.UUID,
    current_password: str,
) -> PhotonCommand:
    if not verify_password(current_password, guardian.password_hash):
        raise AppError(401, "reauthentication_failed", "Enter your current password to continue.")
    row = await session.get(PhotonCommand, command_id)
    if row is None or row.guardian_id != guardian.id:
        raise AppError(404, "not_found", "That command was not found.")
    if row.status != "needs_child_selection" or row.command not in {"pause", "resume"}:
        raise AppError(400, "invalid_command", "That command does not need a child selection.")
    link = await session.scalar(
        select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == guardian.id,
            GuardianChildLink.child_id == child_id,
            GuardianChildLink.status == "active",
        )
    )
    if link is None:
        raise AppError(403, "forbidden", "You are not a guardian for this child.")
    await _apply_access_change(
        session,
        manager,
        guardian_id=guardian.id,
        child_id=child_id,
        pausing=row.command == "pause",
        source="app",
    )
    row.child_id = child_id
    row.status = "executed"
    row.result = "executed"
    row.executed_at = utcnow()
    return row


async def set_access(
    session: AsyncSession,
    manager: ConnectionManager,
    *,
    guardian_id: uuid.UUID,
    child_id: uuid.UUID,
    paused: bool,
    source: str,
) -> ChildAccessState:
    return await _apply_access_change(
        session,
        manager,
        guardian_id=guardian_id,
        child_id=child_id,
        pausing=paused,
        source=source,
    )


async def _apply_access_change(
    session: AsyncSession,
    manager: ConnectionManager,
    *,
    guardian_id: uuid.UUID,
    child_id: uuid.UUID,
    pausing: bool,
    source: str,
) -> ChildAccessState:
    state = await session.get(ChildAccessState, child_id)
    if state is None:
        raise AppError(404, "not_found", "Access state is not available for this child.")
    now = utcnow()
    state.is_paused = pausing
    state.state_version += 1
    state.updated_by = guardian_id
    state.updated_at = now
    state.pause_source = source if pausing else source
    session.add(
        GuardianAction(
            id=uuid.uuid4(),
            guardian_id=guardian_id,
            child_id=child_id,
            action="pause" if pausing else "resume",
            source=source,
            result="paused" if pausing else "active",
            created_at=now,
        )
    )
    await session.commit()
    await manager.publish(child_id, access_payload(child_id, state))
    return state


async def _match_guardian_phone(session: AsyncSession, sender: str) -> User | None:
    if not sender:
        return None
    normalized = sender if sender.startswith("+") else sender
    guardian = await session.scalar(select(User).where(User.role == "guardian", User.phone == normalized))
    if guardian is not None:
        return guardian
    return await session.scalar(select(User).where(User.role == "guardian", User.provider_identity == sender))


async def _linked_children(session: AsyncSession, guardian_id: uuid.UUID) -> list[tuple[ChildAccessState, User]]:
    rows = await session.execute(
        select(User, ChildAccessState)
        .join(GuardianChildLink, GuardianChildLink.child_id == User.id)
        .join(ChildAccessState, ChildAccessState.child_id == User.id)
        .where(GuardianChildLink.guardian_id == guardian_id, GuardianChildLink.status == "active")
        .order_by(User.username.asc())
    )
    return [(state, user) for user, state in rows.all()]


def _select_child(children: list[tuple[ChildAccessState, User]], argument: str | None):
    if argument:
        wanted = argument.lower()
        for state, user in children:
            if (user.username or "").lower() == wanted:
                return state, user
        return None
    if len(children) == 1:
        state, user = children[0]
        return state, user
    return None


def _status_summary(children: list[tuple[ChildAccessState, User]]) -> str:
    if not children:
        return "You have no linked children in Kinwise."
    parts = [f"{user.display_name} is {'paused' if state.is_paused else 'active'}" for state, user in children]
    return "Kinwise status: " + "; ".join(parts) + "."


def _command(
    *,
    guardian_id: uuid.UUID | None,
    message_id: str,
    command: str,
    status: str,
    result: str,
    raw_text: str,
    child_id: uuid.UUID | None = None,
) -> PhotonCommand:
    return PhotonCommand(
        id=uuid.uuid4(),
        guardian_id=guardian_id,
        child_id=child_id,
        webhook_message_id=message_id,
        command=command,
        status=status,
        raw_text=raw_text[:280],
        result=result,
        created_at=utcnow(),
    )


async def _reply(photon: PhotonMessagingService, space_id: str, text: str, key: str) -> None:
    if not space_id:
        return
    try:
        await photon.send_text(space_id=space_id, text=text, idempotency_key=key)
    except Exception:
        logger.warning("photon command reply failed")
