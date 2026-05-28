from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from core.services.user_service import UserService


def _extract_tg_user(event: TelegramObject):
    if isinstance(event, Update):
        if event.message is not None:
            return event.message.from_user
        if event.callback_query is not None:
            return event.callback_query.from_user
        if event.edited_message is not None:
            return event.edited_message.from_user
    if isinstance(event, (Message, CallbackQuery)):
        return event.from_user
    return getattr(event, "from_user", None)


class UserMiddleware(BaseMiddleware):
    """Auto-register the Telegram user and inject the DB-backed User into handlers."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = _extract_tg_user(event)
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        user_service: UserService = data["user_service"]
        user = await user_service.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        data["current_user"] = user
        return await handler(event, data)
