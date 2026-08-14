import sys
import os
import asyncio

import alembic_postgresql_enum
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from sqlmodel import SQLModel

# 1. Append the root runtime directory to Python's lookup path list
sys.path.append(os.getcwd())

# 2. Import your application's absolute database variables
# (This ensures all models inherit from SQLModel's shared structural layout registry)
from app.models.user import User
from app.models.profile import Profile
from app.models.token import Token  # Keeps Alembic tracking synchronized!
from app.core.config import settings

# This is the standard Alembic Config object
config = context.config

# Overwrite the empty ini template property with your explicit database URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Provide SQLModel's metadata mapping layer to Alembic's tracker
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (Generates raw SQL scripts without a DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Applies the tracking context inside a synchronous environment wrapper."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Creates an async engine directly and handles the connection lifecycle cleanly."""

    # Instantiate the engine using your application settings directly to bypass config parsing errors
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Executes the synchronous migration runner via SQLAlchemy's run_sync channel
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (Connects directly to your PostgreSQL database)."""

    # Try to grab an existing running loop to prevent event loop nesting collisions.
    # If no loop is active, fall back to standard loop initialization.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Securely schedule the migration task onto the active event loop
        loop.create_task(run_async_migrations())
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()

else:
    run_migrations_online()
