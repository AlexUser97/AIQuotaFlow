from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from core.models.subscription import SubscriptionAccount
from core.models.user import User
from core.services.status_service import StatusColor

logger = logging.getLogger(__name__)


def _resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _account_label(subscription: SubscriptionAccount) -> str:
    return subscription.login_email or subscription.account_name


def format_local_time(
    dt: datetime, tz_name: str, time_format_24h: bool = True
) -> str:
    tz = _resolve_tz(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(tz)
    if time_format_24h:
        return local.strftime("%H:%M")
    return local.strftime("%I:%M %p").lstrip("0")


class NotificationService:
    """Builds and sends Telegram notifications about cooldowns and expirations."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send(self, telegram_id: int, text: str) -> None:
        try:
            await self.bot.send_message(telegram_id, text)
        except TelegramAPIError as exc:
            logger.warning(
                "Failed to send notification to %s: %s", telegram_id, exc
            )

    async def notify_cooldown_finished(
        self, user: User, subscription: SubscriptionAccount
    ) -> None:
        if not user.notifications_enabled:
            return
        label = _account_label(subscription)
        text = (
            f"{StatusColor.GREEN.value} <b>{label}</b> свободен!\n"
            f"{subscription.provider} {subscription.plan} — квота восстановилась.\n"
            f"Переключайся."
        )
        await self.send(user.telegram_id, text)

    async def notify_subscription_expiring(
        self, user: User, subscription: SubscriptionAccount
    ) -> None:
        if not user.notifications_enabled:
            return
        label = _account_label(subscription)
        end_date = subscription.subscription_end_date
        date_str = end_date.strftime("%d.%m.%Y") if end_date else ""
        text = (
            f"⏰ Подписка <b>{label}</b> скоро истекает.\n"
            f"{subscription.provider} {subscription.plan} — до {date_str}."
        )
        await self.send(user.telegram_id, text)

    async def notify_subscription_expired(
        self, user: User, subscription: SubscriptionAccount
    ) -> None:
        if not user.notifications_enabled:
            return
        label = _account_label(subscription)
        text = (
            f"{StatusColor.RED.value} Подписка <b>{label}</b> истекла.\n"
            f"{subscription.provider} {subscription.plan}."
        )
        await self.send(user.telegram_id, text)
