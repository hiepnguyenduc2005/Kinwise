import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401
from app.api.router import api_router
from app.core.config import Settings
from app.core.errors import AppError, app_error_handler
from app.core.rate_limit import RateLimiter
from app.db.base import Base
from app.db.session import create_engine, create_sessionmaker
from app.realtime.manager import ConnectionManager
from app.services.backboard.service import BackboardMemoryService
from app.services.gemini.client import GoogleGeminiClient
from app.services.photon.service import PhotonMessagingService

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    gemini=None,
    backboard=None,
    photon=None,
) -> FastAPI:
    settings = settings or Settings()
    settings.validate_runtime()
    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    gemini = gemini or GoogleGeminiClient(settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds)
    backboard = backboard or BackboardMemoryService(settings.backboard_api_key, settings.backboard_base_url)
    photon = photon or PhotonMessagingService(
        bridge_url=settings.spectrum_bridge_url,
        bridge_token=settings.spectrum_bridge_token,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_create_schema:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        try:
            yield
        finally:
            closer = getattr(backboard, "aclose", None)
            if closer:
                await closer()
            photon_closer = getattr(photon, "aclose", None)
            if photon_closer:
                await photon_closer()
            await engine.dispose()

    app = FastAPI(title="Kinwise", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.gemini = gemini
    app.state.backboard = backboard
    app.state.photon = photon
    app.state.manager = ConnectionManager()
    app.state.rate_limiter = RateLimiter()
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(api_router)

    @app.get("/api/v1/health")
    async def health() -> dict:
        database = "ok"
        try:
            async with sessionmaker() as session:
                await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        except Exception:
            database = "unavailable"
            logger.warning("health check could not reach the database")
        return {
            "status": "ok" if database == "ok" else "degraded",
            "service": "kinwise",
            "database": database,
            "environment": settings.environment,
            "integrations": {
                "gemini": settings.gemini_configured,
                "backboard": settings.backboard_configured,
                "photon_send": settings.photon_send_configured,
                "spectrum_bridge": bool(settings.spectrum_bridge_url and settings.spectrum_bridge_token),
            },
            "realtime": "in_process_single_instance",
        }

    return app


app = create_app()
