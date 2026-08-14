"""
Database connection and session management for the application.
This module sets up the database connection using SQLModel and provides a dependency function to get a database session for each request. The database URL is read from the application settings, which are configured to load from environment variables or a .env file.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

engine_kwargs: dict[str, Any] = {
    "echo": getattr(settings, "DB_ECHO", False),
    "future": True,
    "pool_pre_ping": True,  # Tests connections before execution to drop dead links
}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = getattr(settings, "DB_POOL_SIZE", 20)
    engine_kwargs["max_overflow"] = getattr(settings, "DB_MAX_OVERFLOW", 10)
    engine_kwargs["pool_timeout"] = getattr(settings, "DB_POOL_TIMEOUT", 30)

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

"""
Configure the async session generator factory passing SQLModel's AsyncSession
"""
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# Dependency function to get a database session for each request. This function creates a new session, yields it to the endpoint, and ensures that the session is closed after the request is completed.
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding a unique, thread-safe asynchronous database session.
    Automatically handles connection cleanup and closing at request finalization.
    """
    async with async_session_maker() as session:
        try:
            # If everything goes smoothly, commits are handled inside the endpoints
            yield session

        except Exception:
            # Production Polish: Catch unhandled endpoint errors to prevent corrupt database states
            await session.rollback()
            raise

        finally:
            # Explicitly close the session to release the connection back to the pool
            await session.close()
