from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router(name="help")

HELP_TEXT = (
    "❓ <b>Помощь</b>\n\n"
    "🟢 Зелёный — аккаунт свободен\n"
    "🟡 Жёлтый — cooldown &lt; 24 часов\n"
    "🔴 Красный — cooldown &gt; 24ч или истёк\n\n"
    "<b>Команды:</b>\n"
    "/start — главное меню\n"
    "/status — быстрый статус\n"
    "/add — добавить аккаунт\n"
    "/help — эта справка\n\n"
    "Бот <b>не</b> логинится в твои аккаунты, не хранит пароли и не проверяет "
    "лимиты автоматически — ты сам нажимаешь Cooldown когда уткнулся в лимит."
)


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:main")]
        ]
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=_back_kb())


@router.callback_query(F.data == "menu:help")
async def open_help(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(HELP_TEXT, reply_markup=_back_kb())
    await callback.answer()
