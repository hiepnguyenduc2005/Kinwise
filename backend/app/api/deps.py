import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import session_scope
from app.models import AuthSession, User

_bearer = HTTPBearer(auto_error=False)


async def get_db(request: Request):
    async for session in session_scope(request.app.state.sessionmaker):
        yield session


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AppError(401, "unauthorized", "Sign in to continue.")
    payload = decode_access_token(credentials.credentials, request.app.state.settings.jwt_secret)
    try:
        session_id = uuid.UUID(payload["sid"])
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AppError(401, "invalid_token", "Sign in again to continue.") from exc
    auth_session = await session.get(AuthSession, session_id)
    if auth_session is None or auth_session.revoked_at is not None or auth_session.user_id != user_id:
        raise AppError(401, "invalid_token", "Sign in again to continue.")
    from app.core.security import utcnow

    if auth_session.expires_at < utcnow():
        raise AppError(401, "invalid_token", "Sign in again to continue.")
    user = await session.get(User, user_id)
    if user is None or user.disabled_at is not None:
        raise AppError(401, "invalid_token", "Sign in again to continue.")
    if user.role != payload.get("role"):
        raise AppError(401, "invalid_token", "Sign in again to continue.")
    return user


async def require_guardian(user: User = Depends(get_current_user)) -> User:
    if user.role != "guardian":
        raise AppError(403, "forbidden", "This action is only available to guardians.")
    return user


async def require_child(user: User = Depends(get_current_user)) -> User:
    if user.role != "child":
        raise AppError(403, "forbidden", "This action is only available to child accounts.")
    return user
