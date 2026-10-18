from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    url = normalize_database_url(settings.database_url)
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["poolclass"] = NullPool
        kwargs["pool_pre_ping"] = False
    engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_fks(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def normalize_database_url(url: str) -> str:
    """Accept Tiger Cloud libpq URLs and convert them for asyncpg."""
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    if "sslmode=" in url and "+asyncpg" in url:
        url = url.replace("sslmode=", "ssl=")
    return url


async def session_scope(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
