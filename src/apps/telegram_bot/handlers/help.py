from aiogram import Router, types
from aiogram.filters import Command
from logger import get_logger

router = Router()
logger = get_logger(__name__)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "<b>Техническая поддержка Fujida</b>\n\n"
        "📞 Телефон: <code>+79270355555</code>\n"
        "💬 <a href='https://t.me/fujida_corp'>Написать в Telegram</a>\n"
        "💬 <a href='https://wa.me/79270355555'>Написать в WhatsApp</a>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )