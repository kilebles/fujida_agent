from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder='Или введите вручную в формате +7...'
    )