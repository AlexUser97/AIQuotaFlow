from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class EditSubscription(StatesGroup):
    waiting_email = State()
    waiting_name = State()
    waiting_end_date = State()
    waiting_notes = State()
    waiting_custom_cooldown = State()
    waiting_provider = State()
    waiting_plan = State()
    waiting_new_purpose = State()
