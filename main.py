from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import (
    help_router,
    settings_router,
    start_router,
    status_router,
    subscriptions_router,
)
from bot.middlewares import DIMiddleware, UserMiddleware
from config import settings
from core.services.notification_service import NotificationService
from db.engine import async_session_factory, init_db
from scheduler import SchedulerWrapper, create_scheduler
from scheduler.runtime import set_runtime

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


async def main() -> None:
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting AIQuotaFlow bot...")

    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    set_runtime(bot=bot, session_factory=async_session_factory)

    apscheduler = create_scheduler(settings.sync_database_url)
    scheduler = SchedulerWrapper(apscheduler)
    scheduler.bind(bot=bot, session_factory=async_session_factory)

    notification_service = NotificationService(bot)

    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(
        DIMiddleware(
            session_factory=async_session_factory,
            notification_service=notification_service,
            scheduler=scheduler,
        )
    )
    dp.update.outer_middleware(UserMiddleware())

    dp.include_router(start_router)
    dp.include_router(subscriptions_router)
    dp.include_router(status_router)
    dp.include_router(settings_router)
    dp.include_router(help_router)

    scheduler.start()
    logger.info("Bot started, polling...")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupted by user")
