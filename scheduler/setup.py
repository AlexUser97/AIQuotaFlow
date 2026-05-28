from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from scheduler.jobs import (
    cooldown_finished_job,
    subscription_expired_job,
    subscription_expiring_job,
)

logger = logging.getLogger(__name__)


def cooldown_job_id(subscription_id: int) -> str:
    return f"cooldown_{subscription_id}"


def expiry_job_id(subscription_id: int) -> str:
    return f"expiry_{subscription_id}"


def expiring_job_id(subscription_id: int) -> str:
    return f"expiring_{subscription_id}"


def create_scheduler(sync_database_url: str) -> AsyncIOScheduler:
    return AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=sync_database_url)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
        timezone="UTC",
    )


class SchedulerWrapper:
    """Thin wrapper that knows how to schedule our domain-specific jobs."""

    def __init__(self, scheduler: AsyncIOScheduler) -> None:
        self.scheduler = scheduler
        self._bot: Bot | None = None
        self._session_factory: async_sessionmaker | None = None

    def bind(self, bot: Bot, session_factory: async_sessionmaker) -> None:
        self._bot = bot
        self._session_factory = session_factory

    def start(self) -> None:
        self.scheduler.start()

    def shutdown(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover
            logger.exception("Scheduler shutdown failed")

    async def schedule_cooldown_finished(
        self, subscription_id: int, run_date: datetime
    ) -> None:
        if run_date.tzinfo is None:
            run_date = run_date.replace(tzinfo=timezone.utc)
        self.scheduler.add_job(
            cooldown_finished_job,
            trigger="date",
            run_date=run_date,
            args=[subscription_id],
            id=cooldown_job_id(subscription_id),
            replace_existing=True,
        )
        logger.info(
            "Scheduled cooldown_finished for subscription %s at %s",
            subscription_id,
            run_date.isoformat(),
        )

    async def schedule_subscription_expiring(
        self, subscription_id: int, run_date: datetime
    ) -> None:
        if run_date.tzinfo is None:
            run_date = run_date.replace(tzinfo=timezone.utc)
        self.scheduler.add_job(
            subscription_expiring_job,
            trigger="date",
            run_date=run_date,
            args=[subscription_id],
            id=expiring_job_id(subscription_id),
            replace_existing=True,
        )

    async def schedule_subscription_expired(
        self, subscription_id: int, run_date: datetime
    ) -> None:
        if run_date.tzinfo is None:
            run_date = run_date.replace(tzinfo=timezone.utc)
        self.scheduler.add_job(
            subscription_expired_job,
            trigger="date",
            run_date=run_date,
            args=[subscription_id],
            id=expiry_job_id(subscription_id),
            replace_existing=True,
        )

    def cancel_cooldown(self, subscription_id: int) -> None:
        self._remove(cooldown_job_id(subscription_id))

    def cancel_expiry(self, subscription_id: int) -> None:
        self._remove(expiry_job_id(subscription_id))
        self._remove(expiring_job_id(subscription_id))

    def _remove(self, job_id: str) -> None:
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            # job didn't exist — that's fine
            return

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            raise RuntimeError("Scheduler bot not bound")
        return self._bot

    @property
    def session_factory(self) -> async_sessionmaker:
        if self._session_factory is None:
            raise RuntimeError("Scheduler session factory not bound")
        return self._session_factory
