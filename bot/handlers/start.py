from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main_menu import main_menu_keyboard
from core.models.user import User

router = Router(name="start")


def _greet_text(user: User) -> str:
    first_name = user.first_name or "друг"
    return (
        f"Привет, <b>{first_name}</b>! 👋\n\n"
        "Я <b>AIQuotaFlow</b> — личный планировщик AI-аккаунтов.\n"
        "Сам отмечаешь когда упёрся в лимит — я считаю время и присылаю "
        "уведомление, когда квота восстановилась.\n\n"
        "Выбери раздел:"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, current_user: User, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_greet_text(current_user), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:main")
async def open_main_menu(
    callback: CallbackQuery, current_user: User, state: FSMContext
) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(
            _greet_text(current_user), reply_markup=main_menu_keyboard()
        )
    await callback.answer()
