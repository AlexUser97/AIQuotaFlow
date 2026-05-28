from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from core.models.subscription import SubscriptionAccount
from core.repositories.purpose_repo import PurposeRepository
from core.repositories.subscription_repo import SubscriptionRepository

if TYPE_CHECKING:
    from scheduler.setup import SchedulerWrapper


class SubscriptionService:
    def __init__(
        self,
        session: AsyncSession,
        scheduler: "SchedulerWrapper | None" = None,
    ) -> None:
        self.session = session
        self.repo = SubscriptionRepository(session)
        self.purpose_repo = PurposeRepository(session)
        self.scheduler = scheduler

    async def list_for_owner(self, owner_id: int) -> list[SubscriptionAccount]:
        return await self.repo.list_for_owner(owner_id)

    async def get_for_owner(
        self, subscription_id: int, owner_id: int
    ) -> SubscriptionAccount | None:
        return await self.repo.get_for_owner(subscription_id, owner_id)

    async def create(
        self,
        *,
        owner_id: int,
        provider: str,
        account_name: str,
        plan: str,
        login_email: str | None = None,
        subscription_end_date: date | None = None,
        notes: str | None = None,
    ) -> SubscriptionAccount:
        subscription = await self.repo.create(
            owner_id=owner_id,
            provider=provider,
            account_name=account_name,
            plan=plan,
            login_email=login_email,
            subscription_end_date=subscription_end_date,
            notes=notes,
        )
        await self.session.commit()
        return subscription

    async def update_fields(
        self,
        subscription: SubscriptionAccount,
        *,
        provider: str | None = None,
        account_name: str | None = None,
        plan: str | None = None,
        login_email: str | None = None,
        subscription_end_date: date | None = None,
        notes: str | None = None,
        clear_email: bool = False,
        clear_end_date: bool = False,
        clear_notes: bool = False,
    ) -> SubscriptionAccount:
        if provider is not None:
            subscription.provider = provider
        if account_name is not None:
            subscription.account_name = account_name
        if plan is not None:
            subscription.plan = plan
        if login_email is not None:
            subscription.login_email = login_email
        elif clear_email:
            subscription.login_email = None
        if subscription_end_date is not None:
            subscription.subscription_end_date = subscription_end_date
        elif clear_end_date:
            subscription.subscription_end_date = None
        if notes is not None:
            subscription.notes = notes
        elif clear_notes:
            subscription.notes = None
        await self.session.commit()
        return subscription

    async def set_cooldown(
        self,
        subscription: SubscriptionAccount,
        hours: float | None = None,
        minutes: int | None = None,
    ) -> SubscriptionAccount:
        now = datetime.now(timezone.utc)
        delta = timedelta()
        if hours:
            delta += timedelta(hours=hours)
        if minutes:
            delta += timedelta(minutes=minutes)
        if delta.total_seconds() <= 0:
            raise ValueError("Cooldown duration must be positive")
        cooldown_until = now + delta
        await self.repo.set_cooldown(subscription, cooldown_until)
        await self.session.commit()

        if self.scheduler is not None:
            await self.scheduler.schedule_cooldown_finished(
                subscription_id=subscription.id,
                run_date=cooldown_until,
            )
        return subscription

    async def mark_available(
        self, subscription: SubscriptionAccount
    ) -> SubscriptionAccount:
        await self.repo.clear_cooldown(subscription, status="available")
        await self.session.commit()
        if self.scheduler is not None:
            self.scheduler.cancel_cooldown(subscription.id)
        return subscription

    async def mark_exhausted(
        self, subscription: SubscriptionAccount
    ) -> SubscriptionAccount:
        await self.repo.set_status(subscription, "exhausted")
        await self.session.commit()
        if self.scheduler is not None:
            self.scheduler.cancel_cooldown(subscription.id)
        return subscription

    async def delete(self, subscription: SubscriptionAccount) -> None:
        if self.scheduler is not None:
            self.scheduler.cancel_cooldown(subscription.id)
            self.scheduler.cancel_expiry(subscription.id)
        await self.repo.delete(subscription)
        await self.session.commit()

    async def replace_purposes(
        self,
        subscription: SubscriptionAccount,
        purpose_ids: list[int],
    ) -> SubscriptionAccount:
        purposes = []
        for pid in purpose_ids:
            purpose = await self.purpose_repo.get_for_owner(pid, subscription.owner_id)
            if purpose is not None:
                purposes.append(purpose)
        subscription.purposes = purposes
        await self.session.commit()
        await self.session.refresh(subscription, attribute_names=["purposes"])
        return subscription
