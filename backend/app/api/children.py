from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_child
from app.core.errors import AppError
from app.models import ChildAccessState, ChildProfile, User
from app.schemas.api import AccessOut, ChildMeOut
from app.services.present import SUPERVISION_NOTICE, access_out

router = APIRouter()


@router.get("/me", response_model=ChildMeOut)
async def me(session: AsyncSession = Depends(get_db), child: User = Depends(require_child)) -> ChildMeOut:
    profile = await session.get(ChildProfile, child.id)
    if profile is None:
        raise AppError(404, "not_found", "That child profile was not found.")
    return ChildMeOut(
        id=child.id,
        username=child.username or "",
        display_name=child.display_name,
        age_band=profile.age_band,
        supervision_notice=SUPERVISION_NOTICE,
    )


@router.get("/me/access", response_model=AccessOut)
async def access(session: AsyncSession = Depends(get_db), child: User = Depends(require_child)) -> AccessOut:
    state = await session.get(ChildAccessState, child.id)
    if state is None:
        raise AppError(404, "not_found", "Access state is not available.")
    return access_out(state)
