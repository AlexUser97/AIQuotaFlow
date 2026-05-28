from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker


@dataclass
class Runtime:
    bot: Bot
    session_factory: async_sessionmaker


_runtime: Runtime | None = None


def set_runtime(bot: Bot, session_factory: async_sessionmaker) -> None:
    global _runtime
    _runtime = Runtime(bot=bot, session_factory=session_factory)


def get_runtime() -> Runtime | None:
    return _runtime
