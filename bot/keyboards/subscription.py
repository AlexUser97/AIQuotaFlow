from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.models.subscription import Purpose, SubscriptionAccount
from core.services.status_service import StatusService

PROVIDERS = ("Claude", "ChatGPT", "Gemini", "Grok", "Custom")
PLANS = ("Free", "Pro", "Max", "Team", "Custom")


def provider_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for provider in PROVIDERS:
        builder.button(text=provider, callback_data=f"add:provider:{provider}")
    builder.button(text="✖️ Отменить", callback_data="add:cancel")
    builder.adjust(3, 2, 1)
    return builder.as_markup()


def plan_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in PLANS:
        builder.button(text=plan, callback_data=f"add:plan:{plan}")
    builder.button(text="✖️ Отменить", callback_data="add:cancel")
    builder.adjust(3, 2, 1)
    return builder.as_markup()


def add_details_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📧 Email", callback_data=f"sub:edit:email:{subscription_id}"
    )
    builder.button(
        text="🎯 Цели", callback_data=f"sub:edit:purposes:{subscription_id}"
    )
    builder.button(
        text="📅 Дата подписки",
        callback_data=f"sub:edit:enddate:{subscription_id}",
    )
    builder.button(
        text="📝 Заметки", callback_data=f"sub:edit:notes:{subscription_id}"
    )
    builder.button(text="⏭ Пропустить", callback_data=f"sub:open:{subscription_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def cooldown_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hours, label in (
        (1, "1ч"),
        (3, "3ч"),
        (5, "5ч ⭐"),
        (6, "6ч"),
        (12, "12ч"),
        (24, "24ч"),
    ):
        builder.button(
            text=label, callback_data=f"sub:cd:set:{subscription_id}:{hours}"
        )
    builder.button(
        text="✍️ Своё время",
        callback_data=f"sub:cd:custom:{subscription_id}",
    )
    builder.button(
        text="⬅️ Назад", callback_data=f"sub:open:{subscription_id}"
    )
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()


def subscriptions_list_keyboard(
    subscriptions: list[SubscriptionAccount],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sub in subscriptions:
        status = StatusService.get_visual_status(sub)
        label = sub.login_email or sub.account_name
        builder.button(
            text=f"{status.value} {label}",
            callback_data=f"sub:open:{sub.id}",
        )
    builder.button(text="➕ Добавить", callback_data="sub:add")
    builder.button(text="⬅️ Назад", callback_data="menu:main")
    rows: list[int] = [1] * len(subscriptions) + [2]
    builder.adjust(*rows)
    return builder.as_markup()


def subscription_actions_keyboard(
    subscription: SubscriptionAccount,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⏳ Cooldown", callback_data=f"sub:cd:menu:{subscription.id}"
    )
    builder.button(
        text="✅ Доступен", callback_data=f"sub:available:{subscription.id}"
    )
    builder.button(
        text="🔴 Исчерпан", callback_data=f"sub:exhausted:{subscription.id}"
    )
    builder.button(
        text="✏️ Редактировать", callback_data=f"sub:edit:menu:{subscription.id}"
    )
    builder.button(
        text="🗑 Удалить", callback_data=f"sub:delete:{subscription.id}"
    )
    builder.button(text="⬅️ Назад", callback_data="menu:subs")
    builder.adjust(3, 2, 1)
    return builder.as_markup()


def subscription_edit_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏷 Название", callback_data=f"sub:edit:name:{subscription_id}"
    )
    builder.button(
        text="📧 Email", callback_data=f"sub:edit:email:{subscription_id}"
    )
    builder.button(
        text="📦 Провайдер", callback_data=f"sub:edit:provider:{subscription_id}"
    )
    builder.button(
        text="💎 Тариф", callback_data=f"sub:edit:plan:{subscription_id}"
    )
    builder.button(
        text="📅 Дата подписки",
        callback_data=f"sub:edit:enddate:{subscription_id}",
    )
    builder.button(
        text="🎯 Цели", callback_data=f"sub:edit:purposes:{subscription_id}"
    )
    builder.button(
        text="📝 Заметки", callback_data=f"sub:edit:notes:{subscription_id}"
    )
    builder.button(text="⬅️ Назад", callback_data=f"sub:open:{subscription_id}")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def purposes_select_keyboard(
    subscription_id: int,
    purposes: list[Purpose],
    selected_ids: set[int],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for purpose in purposes:
        marker = "✅" if purpose.id in selected_ids else "▫️"
        builder.button(
            text=f"{marker} {purpose.name}",
            callback_data=f"sub:purpose:toggle:{subscription_id}:{purpose.id}",
        )
    builder.button(
        text="➕ Новая цель",
        callback_data=f"sub:purpose:new:{subscription_id}",
    )
    builder.button(
        text="💾 Сохранить",
        callback_data=f"sub:purpose:save:{subscription_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑 Да, удалить",
        callback_data=f"sub:delete:confirm:{subscription_id}",
    )
    builder.button(
        text="↩️ Отмена",
        callback_data=f"sub:open:{subscription_id}",
    )
    builder.adjust(1, 1)
    return builder.as_markup()
