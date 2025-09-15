import asyncio

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from db.session import async_session_maker
from apps.telegram_bot.states.registration import Registration
from apps.telegram_bot.keyboards.phone_kb import get_phone_kb
from apps.telegram_bot.services.start_service import save_user_phone, has_user_phone
from utils.phone_validation import is_valid_phone
from utils.telegram import delete_message
from logger import get_logger

router = Router()
logger = get_logger(__name__)


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info("Received /start command")

    async with async_session_maker() as session:
        if await has_user_phone(session, user_id):
            logger.info("User already has phone in DB")
            await message.answer("Привет! Это ассистент Fujida. Чем могу помочь?")
        else:
            logger.info("User has no phone in DB, requesting phone number")
            await message.answer(
                "Привет! Пожалуйста, поделитесь номером телефона, чтобы продолжить.",
                reply_markup=get_phone_kb()
            )
            await state.set_state(Registration.wait_for_phone)


@router.message(Registration.wait_for_phone, F.contact)
async def handle_contact(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    first_name = message.from_user.first_name
    logger.info("Received phone via contact: %s", phone)

    async with async_session_maker() as session:
        await save_user_phone(session, user_id, first_name, phone)

    logger.info("Phone saved to DB")
    await state.clear()
    await message.answer(
        "Спасибо! Номер сохранён.\n\nПривет! Это ассистент Fujida. Чем могу помочь?",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(Registration.wait_for_phone)
async def handle_manual_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    logger.info("Received manual phone input")

    if not is_valid_phone(phone):
        logger.warning("Invalid phone format: %s", phone)
        msg = await message.answer("Пожалуйста, введите корректный номер телефона")
        asyncio.create_task(delete_message(msg))
        return

    user_id = message.from_user.id
    first_name = message.from_user.first_name
    logger.info("Manual phone accepted: %s", phone)

    async with async_session_maker() as session:
        await save_user_phone(session, user_id, first_name, phone)

    logger.info("Phone saved to DB")
    await state.clear()
    await message.answer(
        "Спасибо! Номер сохранён.\n\nПривет! Это ассистент Fujida. Чем могу помочь?",
        reply_markup=ReplyKeyboardRemove()
    )
