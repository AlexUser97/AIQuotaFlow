from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from core.models.subscription import SubscriptionAccount


class StatusColor(str, Enum):
    GREEN = "🟢"
    YELLOW = "🟡"
    RED = "🔴"


class StatusService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def get_visual_status(
        cls, subscription: SubscriptionAccount, now: datetime | None = None
    ) -> StatusColor:
        current = now or cls._now()

        if subscription.current_status in ("exhausted", "inactive"):
            return StatusColor.RED

        if subscription.subscription_end_date is not None:
            if subscription.subscription_end_date < current.date():
                return StatusColor.RED

        if subscription.cooldown_until is None:
            return StatusColor.GREEN

        cooldown_until = subscription.cooldown_until
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)

        if cooldown_until <= current:
            return StatusColor.GREEN

        if cooldown_until <= current + timedelta(hours=24):
            return StatusColor.YELLOW

        return StatusColor.RED

    @classmethod
    def format_remaining(
        cls, cooldown_until: datetime, now: datetime | None = None
    ) -> str:
        current = now or cls._now()
        target = cooldown_until
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        delta = target - current
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "сейчас"

        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)

        if days > 0:
            return f"{days}д {hours}ч"
        if hours > 0:
            return f"{hours}ч {minutes}м"
        if minutes > 0:
            return f"{minutes}м"
        return "<1м"
