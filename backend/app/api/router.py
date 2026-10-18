from fastapi import APIRouter

from app.api import auth, children, conversations, guardian, realtime, webhooks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(guardian.router, prefix="/guardian", tags=["guardian"])
api_router.include_router(children.router, prefix="/children", tags=["children"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["realtime"])
