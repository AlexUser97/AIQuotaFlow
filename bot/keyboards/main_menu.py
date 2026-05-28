from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Мои подписки", callback_data="menu:subs"),
        InlineKeyboardButton(text="📊 Статусы", callback_data="menu:status"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
    )
    return builder.as_markup()
