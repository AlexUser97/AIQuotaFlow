from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings
from db.base import Base

logger = logging.getLogger(__name__)


def _ensure_sqlite_dir(database_url: str) -> None:
    """Make sure the parent directory for the SQLite file exists."""
    if "sqlite" not in database_url:
        return
    # sqlite+aiosqlite:///data/aiquotaflow.db  -> data/aiquotaflow.db
    _, _, path = database_url.partition(":///")
    if not path:
        return
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.DATABASE_URL)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    """Create all tables. Idempotent — safe to call on each startup."""
    # Importing here so SQLAlchemy sees all mapped models before create_all.
    from core import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized at %s", settings.DATABASE_URL)
