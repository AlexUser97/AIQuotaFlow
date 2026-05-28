from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.models.subscription import SubscriptionAccount
from core.models.user import User
from core.services.purpose_service import PurposeService
from core.services.status_service import StatusColor, StatusService
from core.services.subscription_service import SubscriptionService

router = Router(name="status")


def _account_label(sub: SubscriptionAccount) -> str:
    return sub.login_email or sub.account_name


def _filter_subs(
    subs: list[SubscriptionAccount], purpose_id: int | None
) -> list[SubscriptionAccount]:
    if purpose_id is None:
        return subs
    return [s for s in subs if any(p.id == purpose_id for p in s.purposes)]


def _status_text(
    subs: list[SubscriptionAccount],
    purpose_name: str | None,
) -> str:
    title = "📊 Статусы" if purpose_name is None else f"📊 {purpose_name}"
    if not subs:
        return (
            f"<b>{title}</b>\n\n"
            "Нет аккаунтов в этой категории."
        )

    greens: list[str] = []
    yellows: list[str] = []
    reds: list[str] = []

    for sub in subs:
        status = StatusService.get_visual_status(sub)
        label = _account_label(sub)
        meta = f"{sub.provider} {sub.plan}"
        if status == StatusColor.GREEN:
            greens.append(f"• <b>{label}</b> — {meta}")
        elif status == StatusColor.YELLOW:
            remaining = (
                StatusService.format_remaining(sub.cooldown_until)
                if sub.cooldown_until
                else "—"
            )
            yellows.append(f"• <b>{label}</b> — через {remaining}")
        else:
            tag = ""
            if sub.current_status == "exhausted":
                tag = " — исчерпан"
            elif sub.current_status == "inactive":
                tag = " — неактивен"
            elif sub.cooldown_until:
                tag = f" — сброс через {StatusService.format_remaining(sub.cooldown_until)}"
            reds.append(f"• <b>{label}</b>{tag}")

    parts = [f"<b>{title}</b>", ""]
    if greens:
        parts.append("🟢 <b>Доступны сейчас:</b>")
        parts.extend(greens)
        parts.append("")
    if yellows:
        parts.append("🟡 <b>Восстановятся в течение 24ч:</b>")
        parts.extend(yellows)
        parts.append("")
    if reds:
        parts.append("🔴 <b>Недоступны:</b>")
        parts.extend(reds)
        parts.append("")
    return "\n".join(parts).rstrip()


def _filter_kb(
    purposes: list,
    selected_purpose_id: int | None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    all_marker = "•" if selected_purpose_id is None else " "
    builder.button(text=f"{all_marker} Все", callback_data="status:filter:all")
    for purpose in purposes:
        marker = "•" if purpose.id == selected_purpose_id else " "
        builder.button(
            text=f"{marker} {purpose.name}",
            callback_data=f"status:filter:{purpose.id}",
        )
    builder.button(text="⬅️ В меню", callback_data="menu:main")
    rows = [1] + [1] * len(purposes) + [1]
    builder.adjust(*rows)
    return builder.as_markup()


@router.callback_query(F.data == "menu:status")
async def open_status(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    purpose_service: PurposeService,
) -> None:
    await _render_status(
        callback, current_user, subscription_service, purpose_service, None
    )


@router.callback_query(F.data == "status:filter:all")
async def filter_all(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    purpose_service: PurposeService,
) -> None:
    await _render_status(
        callback, current_user, subscription_service, purpose_service, None
    )


@router.callback_query(F.data.startswith("status:filter:"))
async def filter_purpose(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    purpose_service: PurposeService,
) -> None:
    raw = callback.data.rsplit(":", 1)[-1]
    if raw == "all":
        purpose_id = None
    else:
        try:
            purpose_id = int(raw)
        except ValueError:
            purpose_id = None
    await _render_status(
        callback, current_user, subscription_service, purpose_service, purpose_id
    )


async def _render_status(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    purpose_service: PurposeService,
    purpose_id: int | None,
) -> None:
    subs = await subscription_service.list_for_owner(current_user.id)
    purposes = await purpose_service.list_for_owner(current_user.id)

    purpose_name = None
    if purpose_id is not None:
        for p in purposes:
            if p.id == purpose_id:
                purpose_name = p.name
                break

    filtered = _filter_subs(subs, purpose_id)
    text = _status_text(filtered, purpose_name)
    if callback.message is not None:
        await callback.message.edit_text(
            text, reply_markup=_filter_kb(purposes, purpose_id)
        )
    await callback.answer()
