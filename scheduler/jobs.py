from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _get_runtime():
    """Lazy import to avoid circular imports between scheduler and main."""
    from scheduler.runtime import get_runtime

    return get_runtime()


async def cooldown_finished_job(subscription_id: int) -> None:
    runtime = _get_runtime()
    if runtime is None:
        logger.warning("Runtime not available; skipping cooldown_finished_job")
        return

    bot = runtime.bot
    session_factory = runtime.session_factory

    from core.repositories.subscription_repo import SubscriptionRepository
    from core.repositories.user_repo import UserRepository
    from core.services.notification_service import NotificationService

    async with session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        subscription = await session.get(
            sub_repo.model, subscription_id
        )
        if subscription is None:
            logger.info("Subscription %s gone; skip", subscription_id)
            return

        # Flip status back to available.
        subscription.current_status = "available"
        subscription.cooldown_until = None
        await session.commit()

        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(subscription.owner_id)
        if user is None:
            return

        notif = NotificationService(bot)
        await notif.notify_cooldown_finished(user, subscription)


async def subscription_expiring_job(subscription_id: int) -> None:
    runtime = _get_runtime()
    if runtime is None:
        return
    bot = runtime.bot
    session_factory = runtime.session_factory

    from core.repositories.subscription_repo import SubscriptionRepository
    from core.repositories.user_repo import UserRepository
    from core.services.notification_service import NotificationService

    async with session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        subscription = await session.get(sub_repo.model, subscription_id)
        if subscription is None:
            return
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(subscription.owner_id)
        if user is None:
            return
        notif = NotificationService(bot)
        await notif.notify_subscription_expiring(user, subscription)


async def subscription_expired_job(subscription_id: int) -> None:
    runtime = _get_runtime()
    if runtime is None:
        return
    bot = runtime.bot
    session_factory = runtime.session_factory

    from core.repositories.subscription_repo import SubscriptionRepository
    from core.repositories.user_repo import UserRepository
    from core.services.notification_service import NotificationService

    async with session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        subscription = await session.get(sub_repo.model, subscription_id)
        if subscription is None:
            return
        subscription.current_status = "inactive"
        await session.commit()

        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(subscription.owner_id)
        if user is None:
            return
        notif = NotificationService(bot)
        await notif.notify_subscription_expired(user, subscription)
