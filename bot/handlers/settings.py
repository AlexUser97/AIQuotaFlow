from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.models.user import User
from core.services.user_service import UserService

router = Router(name="settings")


class SettingsFSM(StatesGroup):
    waiting_timezone = State()


REMINDER_OPTIONS = (5, 15, 30, 60)


def _settings_text(user: User) -> str:
    notif = "ВКЛ" if user.notifications_enabled else "ВЫКЛ"
    fmt = "24ч" if user.time_format_24h else "12ч"
    sort_map = {"status": "по статусу", "created": "по дате добавления"}
    sort_label = sort_map.get(user.sort_mode, user.sort_mode)
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"🌍 Часовой пояс: <b>{user.timezone}</b>\n"
        f"⏰ Напоминание за: <b>{user.reminder_minutes} минут</b>\n"
        f"🔔 Уведомления: <b>{notif}</b>\n"
        f"🕐 Формат времени: <b>{fmt}</b>\n"
        f"📋 Сортировка: <b>{sort_label}</b>"
    )


def _settings_kb(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Часовой пояс", callback_data="settings:tz")
    builder.button(text="⏰ Напоминание", callback_data="settings:reminder")
    notif_label = "🔔 Уведомления: ВЫКЛ" if user.notifications_enabled else "🔔 Уведомления: ВКЛ"
    builder.button(text=notif_label, callback_data="settings:toggle_notif")
    fmt_label = "🕐 → 12ч" if user.time_format_24h else "🕐 → 24ч"
    builder.button(text=fmt_label, callback_data="settings:toggle_fmt")
    sort_label = "📋 Сортировка: дата" if user.sort_mode == "status" else "📋 Сортировка: статус"
    builder.button(text=sort_label, callback_data="settings:toggle_sort")
    builder.button(text="⬅️ В меню", callback_data="menu:main")
    builder.adjust(2, 1, 1, 1, 1)
    return builder.as_markup()


async def _show_settings(message: Message, user: User) -> None:
    await message.edit_text(_settings_text(user), reply_markup=_settings_kb(user))


@router.message(Command("settings"))
async def cmd_settings(message: Message, current_user: User) -> None:
    await message.answer(_settings_text(current_user), reply_markup=_settings_kb(current_user))


@router.callback_query(F.data == "menu:settings")
async def open_settings(callback: CallbackQuery, current_user: User) -> None:
    if callback.message is not None:
        await _show_settings(callback.message, current_user)
    await callback.answer()


@router.callback_query(F.data == "settings:toggle_notif")
async def toggle_notifications(
    callback: CallbackQuery, current_user: User, user_service: UserService
) -> None:
    await user_service.update_settings(
        current_user, notifications_enabled=not current_user.notifications_enabled
    )
    if callback.message is not None:
        await _show_settings(callback.message, current_user)
    await callback.answer("Сохранено")


@router.callback_query(F.data == "settings:toggle_fmt")
async def toggle_time_format(
    callback: CallbackQuery, current_user: User, user_service: UserService
) -> None:
    await user_service.update_settings(
        current_user, time_format_24h=not current_user.time_format_24h
    )
    if callback.message is not None:
        await _show_settings(callback.message, current_user)
    await callback.answer("Сохранено")


@router.callback_query(F.data == "settings:toggle_sort")
async def toggle_sort(
    callback: CallbackQuery, current_user: User, user_service: UserService
) -> None:
    new_mode = "created" if current_user.sort_mode == "status" else "status"
    await user_service.update_settings(current_user, sort_mode=new_mode)
    if callback.message is not None:
        await _show_settings(callback.message, current_user)
    await callback.answer("Сохранено")


@router.callback_query(F.data == "settings:reminder")
async def reminder_menu(callback: CallbackQuery, current_user: User) -> None:
    builder = InlineKeyboardBuilder()
    for minutes in REMINDER_OPTIONS:
        marker = "•" if current_user.reminder_minutes == minutes else " "
        builder.button(
            text=f"{marker} {minutes} мин",
            callback_data=f"settings:reminder:set:{minutes}",
        )
    builder.button(text="⬅️ Назад", callback_data="menu:settings")
    builder.adjust(2, 2, 1)
    if callback.message is not None:
        await callback.message.edit_text(
            "За сколько минут до окончания подписки напоминать?",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("settings:reminder:set:"))
async def reminder_set(
    callback: CallbackQuery, current_user: User, user_service: UserService
) -> None:
    minutes = int(callback.data.rsplit(":", 1)[-1])
    await user_service.update_settings(current_user, reminder_minutes=minutes)
    if callback.message is not None:
        await _show_settings(callback.message, current_user)
    await callback.answer("Сохранено")


@router.callback_query(F.data == "settings:tz")
async def ask_timezone(
    callback: CallbackQuery, current_user: User, state: FSMContext
) -> None:
    await state.set_state(SettingsFSM.waiting_timezone)
    text = (
        "Введи название часового пояса в формате IANA.\n\n"
        "Примеры:\n"
        "• <code>Europe/Moscow</code>\n"
        "• <code>Europe/Berlin</code>\n"
        "• <code>Asia/Almaty</code>\n"
        "• <code>America/New_York</code>\n"
        "• <code>UTC</code>"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Отмена", callback_data="menu:settings")
    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.message(SettingsFSM.waiting_timezone)
async def receive_timezone(
    message: Message,
    state: FSMContext,
    current_user: User,
    user_service: UserService,
) -> None:
    tz_name = (message.text or "").strip()
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        await message.answer(
            "Не нашёл такой часовой пояс. Введи в формате <code>Europe/Moscow</code>."
        )
        return
    await user_service.update_settings(current_user, timezone=tz_name)
    await state.clear()
    await message.answer(
        _settings_text(current_user), reply_markup=_settings_kb(current_user)
    )
