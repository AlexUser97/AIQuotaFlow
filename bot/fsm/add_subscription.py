from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddSubscription(StatesGroup):
    provider = State()
    account_name = State()
    plan = State()
