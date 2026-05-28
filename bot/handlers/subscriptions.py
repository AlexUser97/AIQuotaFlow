from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.fsm.add_subscription import AddSubscription
from bot.fsm.edit_subscription import EditSubscription
from bot.keyboards.subscription import (
    PLANS,
    PROVIDERS,
    add_details_keyboard,
    confirm_delete_keyboard,
    cooldown_keyboard,
    plan_keyboard,
    provider_keyboard,
    purposes_select_keyboard,
    subscription_actions_keyboard,
    subscription_edit_keyboard,
    subscriptions_list_keyboard,
)
from core.models.subscription import SubscriptionAccount
from core.models.user import User
from core.services.notification_service import format_local_time
from core.services.purpose_service import PurposeService
from core.services.status_service import StatusColor, StatusService
from core.services.subscription_service import SubscriptionService

router = Router(name="subscriptions")


def _account_label(sub: SubscriptionAccount) -> str:
    return sub.login_email or sub.account_name


def _sort_subscriptions(
    subs: Iterable[SubscriptionAccount], mode: str
) -> list[SubscriptionAccount]:
    items = list(subs)
    if mode == "status":
        order = {StatusColor.GREEN: 0, StatusColor.YELLOW: 1, StatusColor.RED: 2}
        items.sort(key=lambda s: (order[StatusService.get_visual_status(s)], s.created_at))
    return items


def _format_purposes(sub: SubscriptionAccount) -> str:
    if not sub.purposes:
        return "—"
    return ", ".join(p.name for p in sub.purposes)


def _format_end_date(sub: SubscriptionAccount) -> str:
    if sub.subscription_end_date is None:
        return "—"
    return sub.subscription_end_date.strftime("%d.%m.%Y")


def _format_cooldown_line(sub: SubscriptionAccount, user: User) -> str:
    if sub.cooldown_until is None:
        return "—"
    remaining = StatusService.format_remaining(sub.cooldown_until)
    local_hm = format_local_time(
        sub.cooldown_until, user.timezone, user.time_format_24h
    )
    return f"{local_hm} (через {remaining})"


def _subscription_card(sub: SubscriptionAccount, user: User) -> str:
    status = StatusService.get_visual_status(sub)
    label = _account_label(sub)
    lines = [
        f"{status.value} <b>{label}</b>",
        f"{sub.provider} {sub.plan}",
        "",
        f"🏷 account_name: <i>{sub.account_name}</i>",
    ]
    if sub.login_email:
        lines.append(f"📧 {sub.login_email}")
    lines.append(f"📅 Подписка до: {_format_end_date(sub)}")
    lines.append(f"⏰ Cooldown: {_format_cooldown_line(sub, user)}")
    lines.append(f"🎯 Цели: {_format_purposes(sub)}")
    if sub.notes:
        lines.append(f"📝 Заметки: {sub.notes}")

    if status == StatusColor.RED and sub.current_status in ("exhausted", "inactive"):
        lines.append("")
        lines.append("Статус: <i>исчерпан</i>" if sub.current_status == "exhausted" else "Статус: <i>неактивен</i>")
    return "\n".join(lines)


def _list_text(subs: list[SubscriptionAccount], user: User) -> str:
    if not subs:
        return (
            "📋 <b>Мои подписки</b>\n\n"
            "Пока ничего не добавлено. Жми <b>➕ Добавить</b>, чтобы начать."
        )
    lines = ["📋 <b>Мои подписки</b>", ""]
    for sub in subs:
        status = StatusService.get_visual_status(sub)
        label = _account_label(sub)
        purposes = _format_purposes(sub)
        tail = (
            ""
            if not sub.cooldown_until
            else (
                f"\n   Сброс через {StatusService.format_remaining(sub.cooldown_until)}"
                if status != StatusColor.GREEN
                else ""
            )
        )
        if status == StatusColor.RED and sub.current_status in ("exhausted", "inactive"):
            tail += "\n   " + ("Исчерпан" if sub.current_status == "exhausted" else "Неактивен")
        elif (
            status == StatusColor.RED
            and sub.subscription_end_date
            and sub.subscription_end_date < datetime.utcnow().date()
        ):
            tail += "\n   Подписка истекла"
        meta = f"{sub.provider} · {sub.plan}"
        if purposes != "—":
            meta += f" · {purposes}"
        lines.append(f"{status.value} <b>{label}</b>\n   {meta}{tail}")
    return "\n\n".join(lines)


async def _show_list(
    message: Message,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    subs = await subscription_service.list_for_owner(current_user.id)
    subs = _sort_subscriptions(subs, current_user.sort_mode)
    await message.edit_text(
        _list_text(subs, current_user),
        reply_markup=subscriptions_list_keyboard(subs),
    )


async def _open_subscription_view(
    message: Message,
    sub: SubscriptionAccount,
    user: User,
) -> None:
    await message.edit_text(
        _subscription_card(sub, user),
        reply_markup=subscription_actions_keyboard(sub),
    )


# --- list ---
@router.callback_query(F.data == "menu:subs")
async def open_subs(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    state: FSMContext,
) -> None:
    await state.clear()
    if callback.message is not None:
        await _show_list(callback.message, current_user, subscription_service)
    await callback.answer()


# --- add: entry points ---
@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    await _start_add_flow(message, state)


@router.callback_query(F.data == "sub:add")
async def cb_add(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is not None:
        await _start_add_flow(callback.message, state, edit=True)
    await callback.answer()


async def _start_add_flow(
    message: Message, state: FSMContext, *, edit: bool = False
) -> None:
    await state.clear()
    await state.set_state(AddSubscription.provider)
    text = "Выбери провайдера:"
    if edit:
        await message.edit_text(text, reply_markup=provider_keyboard())
    else:
        await message.answer(text, reply_markup=provider_keyboard())


@router.callback_query(F.data == "add:cancel")
async def cancel_add(
    callback: CallbackQuery,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    await state.clear()
    if callback.message is not None:
        await _show_list(callback.message, current_user, subscription_service)
    await callback.answer("Отменено")


@router.callback_query(
    AddSubscription.provider, F.data.startswith("add:provider:")
)
async def add_set_provider(callback: CallbackQuery, state: FSMContext) -> None:
    provider = callback.data.rsplit(":", 1)[-1]
    if provider not in PROVIDERS:
        await callback.answer("Неизвестный провайдер", show_alert=True)
        return
    await state.update_data(provider=provider)
    await state.set_state(AddSubscription.account_name)
    if callback.message is not None:
        await callback.message.edit_text(
            "Введи название аккаунта — например <code>Claude работа</code> или "
            "email <code>ivan.work@gmail.com</code>."
        )
    await callback.answer()


@router.message(AddSubscription.account_name)
async def add_set_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Введи ещё раз.")
        return
    if len(name) > 200:
        await message.answer("Слишком длинное название. До 200 символов.")
        return
    await state.update_data(account_name=name)
    await state.set_state(AddSubscription.plan)
    await message.answer("Выбери тариф:", reply_markup=plan_keyboard())


@router.callback_query(AddSubscription.plan, F.data.startswith("add:plan:"))
async def add_set_plan(
    callback: CallbackQuery,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    plan = callback.data.rsplit(":", 1)[-1]
    if plan not in PLANS:
        await callback.answer("Неизвестный тариф", show_alert=True)
        return
    data = await state.get_data()
    provider = data.get("provider")
    account_name = data.get("account_name")
    if not provider or not account_name:
        await state.clear()
        await callback.answer("Что-то пошло не так. Начни заново через /add", show_alert=True)
        return

    login_email = account_name if "@" in account_name else None
    sub = await subscription_service.create(
        owner_id=current_user.id,
        provider=provider,
        account_name=account_name,
        plan=plan,
        login_email=login_email,
    )
    await state.clear()

    text = (
        "✅ <b>Аккаунт добавлен!</b>\n\n"
        f"{sub.provider} {sub.plan} — {_account_label(sub)}\n\n"
        "Хочешь добавить детали?"
    )
    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=add_details_keyboard(sub.id))
    await callback.answer()


# --- open single subscription ---
@router.callback_query(F.data.startswith("sub:open:"))
async def open_subscription(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    state: FSMContext,
) -> None:
    await state.clear()
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer()


# --- cooldown ---
@router.callback_query(F.data.startswith("sub:cd:menu:"))
async def cooldown_menu(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    if callback.message is not None:
        await callback.message.edit_text(
            f"Выбери время cooldown для <b>{_account_label(sub)}</b>:",
            reply_markup=cooldown_keyboard(sub.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:cd:set:"))
async def cooldown_set(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    parts = callback.data.split(":")
    sub_id = int(parts[3])
    hours = int(parts[4])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.set_cooldown(sub, hours=hours)
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer(f"Cooldown на {hours}ч установлен")


@router.callback_query(F.data.startswith("sub:cd:custom:"))
async def cooldown_custom_ask(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    state: FSMContext,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await state.set_state(EditSubscription.waiting_custom_cooldown)
    await state.update_data(subscription_id=sub.id)
    if callback.message is not None:
        await callback.message.edit_text(
            "Введи длительность cooldown.\n\n"
            "Примеры: <code>2ч</code>, <code>45м</code>, <code>1ч 30м</code>, "
            "<code>90</code> (минут).",
        )
    await callback.answer()


def _parse_duration(text: str) -> tuple[int, int] | None:
    """Return (hours, minutes) or None if can't parse."""
    text = text.strip().lower().replace(",", ".")
    if not text:
        return None
    if text.isdigit():
        return (0, int(text))
    hours = 0
    minutes = 0
    buf = ""
    for ch in text + " ":
        if ch.isdigit() or ch == ".":
            buf += ch
        elif ch in ("ч", "h"):
            if buf:
                hours += int(float(buf))
                buf = ""
        elif ch in ("м", "m"):
            if buf:
                minutes += int(float(buf))
                buf = ""
        elif ch.isspace():
            continue
        else:
            return None
    if buf:
        return None
    if hours == 0 and minutes == 0:
        return None
    return (hours, minutes)


@router.message(EditSubscription.waiting_custom_cooldown)
async def cooldown_custom_set(
    message: Message,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if not sub_id:
        await state.clear()
        await message.answer("Сессия истекла. Открой аккаунт заново.")
        return
    parsed = _parse_duration(message.text or "")
    if parsed is None:
        await message.answer("Не разобрал. Введи как <code>2ч 30м</code> или <code>90</code> минут.")
        return
    hours, minutes = parsed
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await state.clear()
        await message.answer("Аккаунт не найден")
        return
    await subscription_service.set_cooldown(sub, hours=hours, minutes=minutes)
    await state.clear()
    await message.answer(
        _subscription_card(sub, current_user),
        reply_markup=subscription_actions_keyboard(sub),
    )


@router.callback_query(F.data.startswith("sub:available:"))
async def mark_available(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.mark_available(sub)
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Помечен как доступный")


@router.callback_query(F.data.startswith("sub:exhausted:"))
async def mark_exhausted(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.mark_exhausted(sub)
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Помечен как исчерпанный")


# --- delete ---
@router.callback_query(F.data.regexp(r"^sub:delete:\d+$"))
async def delete_prompt(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    if callback.message is not None:
        await callback.message.edit_text(
            f"Удалить <b>{_account_label(sub)}</b>?\nДанные не восстановить.",
            reply_markup=confirm_delete_keyboard(sub.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:delete:confirm:"))
async def delete_confirm(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.delete(sub)
    if callback.message is not None:
        await _show_list(callback.message, current_user, subscription_service)
    await callback.answer("Удалено")


# --- edit menu ---
@router.callback_query(F.data.startswith("sub:edit:menu:"))
async def edit_menu(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    if callback.message is not None:
        await callback.message.edit_text(
            f"Что меняем у <b>{_account_label(sub)}</b>?",
            reply_markup=subscription_edit_keyboard(sub.id),
        )
    await callback.answer()


# --- edit email ---
@router.callback_query(F.data.startswith("sub:edit:email:"))
async def edit_email_ask(
    callback: CallbackQuery, state: FSMContext
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    await state.set_state(EditSubscription.waiting_email)
    await state.update_data(subscription_id=sub_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Очистить email", callback_data=f"sub:edit:email:clear:{sub_id}")
    builder.button(text="⬅️ Назад", callback_data=f"sub:open:{sub_id}")
    builder.adjust(1, 1)
    if callback.message is not None:
        await callback.message.edit_text(
            "Введи email (или нажми «Очистить email», чтобы убрать его).",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:edit:email:clear:"))
async def edit_email_clear(
    callback: CallbackQuery,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.update_fields(sub, clear_email=True)
    await state.clear()
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Email очищен")


@router.message(EditSubscription.waiting_email)
async def edit_email_set(
    message: Message,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if not sub_id:
        await state.clear()
        return
    email = (message.text or "").strip()
    if "@" not in email or len(email) > 200:
        await message.answer("Это не похоже на email. Попробуй ещё раз.")
        return
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await state.clear()
        await message.answer("Аккаунт не найден")
        return
    await subscription_service.update_fields(sub, login_email=email)
    await state.clear()
    await message.answer(
        _subscription_card(sub, current_user),
        reply_markup=subscription_actions_keyboard(sub),
    )


# --- edit name ---
@router.callback_query(F.data.startswith("sub:edit:name:"))
async def edit_name_ask(callback: CallbackQuery, state: FSMContext) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    await state.set_state(EditSubscription.waiting_name)
    await state.update_data(subscription_id=sub_id)
    if callback.message is not None:
        await callback.message.edit_text("Введи новое название аккаунта.")
    await callback.answer()


@router.message(EditSubscription.waiting_name)
async def edit_name_set(
    message: Message,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if not sub_id:
        await state.clear()
        return
    name = (message.text or "").strip()
    if not name or len(name) > 200:
        await message.answer("Название должно быть от 1 до 200 символов.")
        return
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await state.clear()
        return
    await subscription_service.update_fields(sub, account_name=name)
    await state.clear()
    await message.answer(
        _subscription_card(sub, current_user),
        reply_markup=subscription_actions_keyboard(sub),
    )


# --- edit provider ---
@router.callback_query(F.data.startswith("sub:edit:provider:"))
async def edit_provider_ask(callback: CallbackQuery, state: FSMContext) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    await state.set_state(EditSubscription.waiting_provider)
    await state.update_data(subscription_id=sub_id)
    builder = InlineKeyboardBuilder()
    for p in PROVIDERS:
        builder.button(text=p, callback_data=f"sub:edit:provider:set:{sub_id}:{p}")
    builder.button(text="⬅️ Назад", callback_data=f"sub:open:{sub_id}")
    builder.adjust(3, 2, 1)
    if callback.message is not None:
        await callback.message.edit_text(
            "Выбери провайдера:", reply_markup=builder.as_markup()
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:edit:provider:set:"))
async def edit_provider_set(
    callback: CallbackQuery,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    parts = callback.data.split(":")
    sub_id = int(parts[4])
    provider = parts[5]
    if provider not in PROVIDERS:
        await callback.answer("Неизвестный провайдер", show_alert=True)
        return
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.update_fields(sub, provider=provider)
    await state.clear()
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Провайдер обновлён")


# --- edit plan ---
@router.callback_query(F.data.startswith("sub:edit:plan:") & ~F.data.startswith("sub:edit:plan:set:"))
async def edit_plan_ask(callback: CallbackQuery, state: FSMContext) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    await state.set_state(EditSubscription.waiting_plan)
    await state.update_data(subscription_id=sub_id)
    builder = InlineKeyboardBuilder()
    for plan in PLANS:
        builder.button(text=plan, callback_data=f"sub:edit:plan:set:{sub_id}:{plan}")
    builder.button(text="⬅️ Назад", callback_data=f"sub:open:{sub_id}")
    builder.adjust(3, 2, 1)
    if callback.message is not None:
        await callback.message.edit_text(
            "Выбери тариф:", reply_markup=builder.as_markup()
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:edit:plan:set:"))
async def edit_plan_set(
    callback: CallbackQuery,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    parts = callback.data.split(":")
    sub_id = int(parts[4])
    plan = parts[5]
    if plan not in PLANS:
        await callback.answer("Неизвестный тариф", show_alert=True)
        return
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.update_fields(sub, plan=plan)
    await state.clear()
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Тариф обновлён")


# --- edit end_date ---
def _parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@router.callback_query(F.data.startswith("sub:edit:enddate:"))
async def edit_enddate_ask(
    callback: CallbackQuery, state: FSMContext
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    await state.set_state(EditSubscription.waiting_end_date)
    await state.update_data(subscription_id=sub_id)
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚫 Без даты",
        callback_data=f"sub:edit:enddate:clear:{sub_id}",
    )
    builder.button(text="⬅️ Назад", callback_data=f"sub:open:{sub_id}")
    builder.adjust(1, 1)
    if callback.message is not None:
        await callback.message.edit_text(
            "Введи дату окончания подписки в формате <code>DD.MM.YYYY</code>\n"
            "Например: <code>15.07.2025</code>",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:edit:enddate:clear:"))
async def edit_enddate_clear(
    callback: CallbackQuery,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.update_fields(sub, clear_end_date=True)
    await state.clear()
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Дата снята")


@router.message(EditSubscription.waiting_end_date)
async def edit_enddate_set(
    message: Message,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if not sub_id:
        await state.clear()
        return
    d = _parse_date(message.text or "")
    if d is None:
        await message.answer("Не разобрал. Формат: <code>DD.MM.YYYY</code>")
        return
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await state.clear()
        return
    await subscription_service.update_fields(sub, subscription_end_date=d)
    await state.clear()
    await message.answer(
        _subscription_card(sub, current_user),
        reply_markup=subscription_actions_keyboard(sub),
    )


# --- edit notes ---
@router.callback_query(F.data.startswith("sub:edit:notes:"))
async def edit_notes_ask(callback: CallbackQuery, state: FSMContext) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    await state.set_state(EditSubscription.waiting_notes)
    await state.update_data(subscription_id=sub_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Очистить", callback_data=f"sub:edit:notes:clear:{sub_id}")
    builder.button(text="⬅️ Назад", callback_data=f"sub:open:{sub_id}")
    builder.adjust(1, 1)
    if callback.message is not None:
        await callback.message.edit_text(
            "Введи заметку (свободный текст).",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:edit:notes:clear:"))
async def edit_notes_clear(
    callback: CallbackQuery,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.update_fields(sub, clear_notes=True)
    await state.clear()
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Заметка очищена")


@router.message(EditSubscription.waiting_notes)
async def edit_notes_set(
    message: Message,
    state: FSMContext,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if not sub_id:
        await state.clear()
        return
    notes = (message.text or "").strip()
    if len(notes) > 1000:
        await message.answer("Слишком длинная заметка. До 1000 символов.")
        return
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await state.clear()
        return
    await subscription_service.update_fields(sub, notes=notes)
    await state.clear()
    await message.answer(
        _subscription_card(sub, current_user),
        reply_markup=subscription_actions_keyboard(sub),
    )


# --- purposes ---
@router.callback_query(F.data.startswith("sub:edit:purposes:"))
async def edit_purposes_open(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    purpose_service: PurposeService,
    state: FSMContext,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    purposes = await purpose_service.list_for_owner(current_user.id)
    selected_ids = {p.id for p in sub.purposes}
    await state.update_data(
        purposes_selected=list(selected_ids), subscription_id=sub.id
    )
    if callback.message is not None:
        await callback.message.edit_text(
            f"Выбери цели для <b>{_account_label(sub)}</b>:",
            reply_markup=purposes_select_keyboard(sub.id, purposes, selected_ids),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:purpose:toggle:"))
async def purpose_toggle(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    purpose_service: PurposeService,
    state: FSMContext,
) -> None:
    parts = callback.data.split(":")
    sub_id = int(parts[3])
    purpose_id = int(parts[4])
    data = await state.get_data()
    selected: list[int] = list(data.get("purposes_selected", []))
    if purpose_id in selected:
        selected.remove(purpose_id)
    else:
        selected.append(purpose_id)
    await state.update_data(purposes_selected=selected, subscription_id=sub_id)

    purposes = await purpose_service.list_for_owner(current_user.id)
    if callback.message is not None:
        await callback.message.edit_reply_markup(
            reply_markup=purposes_select_keyboard(sub_id, purposes, set(selected))
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:purpose:new:"))
async def purpose_new_ask(
    callback: CallbackQuery, state: FSMContext
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    await state.set_state(EditSubscription.waiting_new_purpose)
    await state.update_data(subscription_id=sub_id)
    if callback.message is not None:
        await callback.message.edit_text(
            "Введи название новой цели (workspace).\n"
            "Например: <code>SaaS проект</code>, <code>🎓</code>, <code>работа</code>.",
        )
    await callback.answer()


@router.message(EditSubscription.waiting_new_purpose)
async def purpose_new_set(
    message: Message,
    state: FSMContext,
    current_user: User,
    purpose_service: PurposeService,
    subscription_service: SubscriptionService,
) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if not sub_id:
        await state.clear()
        return
    name = (message.text or "").strip()
    if not name or len(name) > 100:
        await message.answer("Название должно быть от 1 до 100 символов.")
        return
    purpose = await purpose_service.get_or_create(owner_id=current_user.id, name=name)

    selected: list[int] = list(data.get("purposes_selected", []))
    if purpose.id not in selected:
        selected.append(purpose.id)

    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await state.clear()
        return
    purposes = await purpose_service.list_for_owner(current_user.id)
    await state.update_data(purposes_selected=selected, subscription_id=sub.id)
    await state.set_state(None)
    await message.answer(
        f"Выбери цели для <b>{_account_label(sub)}</b>:",
        reply_markup=purposes_select_keyboard(sub.id, purposes, set(selected)),
    )


@router.callback_query(F.data.startswith("sub:purpose:save:"))
async def purpose_save(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    state: FSMContext,
) -> None:
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    data = await state.get_data()
    selected: list[int] = list(data.get("purposes_selected", []))
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    await subscription_service.replace_purposes(sub, selected)
    await state.clear()
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if callback.message is not None and sub is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer("Цели сохранены")


# --- /status command shortcut ---
@router.message(Command("status"))
async def cmd_status(
    message: Message,
    current_user: User,
    subscription_service: SubscriptionService,
) -> None:
    subs = await subscription_service.list_for_owner(current_user.id)
    subs = _sort_subscriptions(subs, current_user.sort_mode)
    text = _list_text(subs, current_user)
    await message.answer(text, reply_markup=subscriptions_list_keyboard(subs))
