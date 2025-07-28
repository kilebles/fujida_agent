import asyncio
from aiogram.types import Message


async def delete_message(message: Message, delay: float = 3.0):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass