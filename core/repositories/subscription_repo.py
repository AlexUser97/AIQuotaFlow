from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.models.subscription import SubscriptionAccount
from core.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[SubscriptionAccount]):
    model = SubscriptionAccount

    async def list_for_owner(self, owner_id: int) -> list[SubscriptionAccount]:
        stmt = (
            select(SubscriptionAccount)
            .where(SubscriptionAccount.owner_id == owner_id)
            .options(selectinload(SubscriptionAccount.purposes))
            .order_by(SubscriptionAccount.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_owner(
        self, subscription_id: int, owner_id: int
    ) -> SubscriptionAccount | None:
        stmt = (
            select(SubscriptionAccount)
            .where(
                SubscriptionAccount.id == subscription_id,
                SubscriptionAccount.owner_id == owner_id,
            )
            .options(selectinload(SubscriptionAccount.purposes))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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
        subscription = SubscriptionAccount(
            owner_id=owner_id,
            provider=provider,
            account_name=account_name,
            plan=plan,
            login_email=login_email,
            subscription_end_date=subscription_end_date,
            notes=notes,
        )
        return await self.add(subscription)

    async def set_cooldown(
        self,
        subscription: SubscriptionAccount,
        cooldown_until: datetime,
    ) -> SubscriptionAccount:
        subscription.cooldown_until = cooldown_until
        subscription.current_status = "cooldown"
        await self.session.flush()
        return subscription

    async def clear_cooldown(
        self,
        subscription: SubscriptionAccount,
        status: str = "available",
    ) -> SubscriptionAccount:
        subscription.cooldown_until = None
        subscription.current_status = status
        await self.session.flush()
        return subscription

    async def set_status(
        self,
        subscription: SubscriptionAccount,
        status: str,
    ) -> SubscriptionAccount:
        subscription.current_status = status
        if status in ("exhausted", "inactive", "available"):
            if status == "available":
                subscription.cooldown_until = None
        await self.session.flush()
        return subscription
