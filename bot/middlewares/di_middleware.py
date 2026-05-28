from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.services.notification_service import NotificationService
from core.services.purpose_service import PurposeService
from core.services.subscription_service import SubscriptionService
from core.services.user_service import UserService

if TYPE_CHECKING:
    from scheduler.setup import SchedulerWrapper


class DIMiddleware(BaseMiddleware):
    """Open one async session per update and inject services into handler data."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        notification_service: NotificationService,
        scheduler: "SchedulerWrapper",
    ) -> None:
        self.session_factory = session_factory
        self.notification_service = notification_service
        self.scheduler = scheduler

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            data["user_service"] = UserService(session)
            data["subscription_service"] = SubscriptionService(
                session, scheduler=self.scheduler
            )
            data["purpose_service"] = PurposeService(session)
            data["notification_service"] = self.notification_service
            data["scheduler"] = self.scheduler
            return await handler(event, data)
