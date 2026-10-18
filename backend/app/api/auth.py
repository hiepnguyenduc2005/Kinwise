from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.api import ChangePasswordIn, LoginIn, ProfilePatchIn, RefreshIn, RegisterGuardianIn, TokenOut, UserOut
from app.services.accounts import change_password, login, logout, refresh_session, register_guardian
from app.services.present import user_out

router = APIRouter()


def _limit(request: Request, identifier: str) -> None:
    settings = request.app.state.settings
    if not settings.auth_rate_limit_enabled:
        return
    host = request.client.host if request.client else "unknown"
    request.app.state.rate_limiter.check(f"auth:{host}:{identifier}", limit=10, window_seconds=300)


@router.post("/guardian/register", response_model=TokenOut)
async def register(body: RegisterGuardianIn, request: Request, session: AsyncSession = Depends(get_db)) -> TokenOut:
    _limit(request, body.email)
    return await register_guardian(session, body, request.app.state.settings, request.headers.get("user-agent"))


@router.post("/login", response_model=TokenOut)
async def login_route(body: LoginIn, request: Request, session: AsyncSession = Depends(get_db)) -> TokenOut:
    _limit(request, body.email or body.username or "unknown")
    return await login(session, body, request.app.state.settings, request.headers.get("user-agent"))


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, request: Request, session: AsyncSession = Depends(get_db)) -> TokenOut:
    return await refresh_session(session, body.refresh_token, request.app.state.settings, request.headers.get("user-agent"))


@router.post("/logout")
async def logout_route(body: RefreshIn, session: AsyncSession = Depends(get_db)) -> dict:
    await logout(session, body.refresh_token)
    return {"status": "signed_out"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
async def patch_me(
    body: ProfilePatchIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    user.display_name = body.display_name
    from app.core.security import utcnow

    user.updated_at = utcnow()
    await session.flush()
    return user_out(user)


@router.post("/change-password")
async def change_password_route(
    body: ChangePasswordIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    await change_password(session, user, body.current_password, body.new_password)
    return {"status": "password_updated"}
