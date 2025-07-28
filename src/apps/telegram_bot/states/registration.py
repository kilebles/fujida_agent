from aiogram.fsm.state import StatesGroup, State


class Registration(StatesGroup):
    wait_for_phone = State()