from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User
from core.repositories.user_repo import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def get_or_create(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        user = await self.repo.get_by_telegram_id(telegram_id)
        if user is None:
            user = await self.repo.create(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
            )
            await self.session.commit()
            return user

        changed = False
        if user.username != username:
            user.username = username
            changed = True
        if user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            await self.session.commit()
        return user

    async def update_settings(
        self,
        user: User,
        *,
        timezone: str | None = None,
        reminder_minutes: int | None = None,
        notifications_enabled: bool | None = None,
        time_format_24h: bool | None = None,
        sort_mode: str | None = None,
    ) -> User:
        if timezone is not None:
            user.timezone = timezone
        if reminder_minutes is not None:
            user.reminder_minutes = reminder_minutes
        if notifications_enabled is not None:
            user.notifications_enabled = notifications_enabled
        if time_format_24h is not None:
            user.time_format_24h = time_format_24h
        if sort_mode is not None:
            user.sort_mode = sort_mode
        await self.session.commit()
        return user
