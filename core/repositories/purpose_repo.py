from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.models.subscription import Purpose
from core.repositories.base import BaseRepository


class PurposeRepository(BaseRepository[Purpose]):
    model = Purpose

    async def list_for_owner(self, owner_id: int) -> list[Purpose]:
        stmt = (
            select(Purpose)
            .where(Purpose.owner_id == owner_id)
            .options(selectinload(Purpose.subscriptions))
            .order_by(Purpose.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_owner(
        self, purpose_id: int, owner_id: int
    ) -> Purpose | None:
        stmt = (
            select(Purpose)
            .where(Purpose.id == purpose_id, Purpose.owner_id == owner_id)
            .options(selectinload(Purpose.subscriptions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name(self, owner_id: int, name: str) -> Purpose | None:
        stmt = select(Purpose).where(
            Purpose.owner_id == owner_id, Purpose.name == name
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, *, owner_id: int, name: str) -> Purpose:
        purpose = Purpose(owner_id=owner_id, name=name)
        return await self.add(purpose)
