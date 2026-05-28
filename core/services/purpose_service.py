from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.models.subscription import Purpose
from core.repositories.purpose_repo import PurposeRepository


class PurposeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PurposeRepository(session)

    async def list_for_owner(self, owner_id: int) -> list[Purpose]:
        return await self.repo.list_for_owner(owner_id)

    async def get_or_create(self, *, owner_id: int, name: str) -> Purpose:
        name = name.strip()
        if not name:
            raise ValueError("Purpose name must not be empty")
        existing = await self.repo.find_by_name(owner_id, name)
        if existing is not None:
            return existing
        purpose = await self.repo.create(owner_id=owner_id, name=name)
        await self.session.commit()
        return purpose

    async def delete(self, purpose: Purpose) -> None:
        await self.repo.delete(purpose)
        await self.session.commit()
