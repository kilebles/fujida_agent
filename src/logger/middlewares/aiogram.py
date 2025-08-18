from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from logger import get_logger
from logger.context import chat_id_var, user_id_var

logger = get_logger(__name__)


class TelegramContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        chat_token = None
        user_token = None
        try:
            chat_id = extract_chat_id(event)
            user_id = extract_user_id(event)
            if chat_id is not None:
                chat_token = chat_id_var.set(chat_id)
            if user_id is not None:
                user_token = user_id_var.set(user_id)
            return await handler(event, data)
        finally:
            if chat_token is not None:
                chat_id_var.reset(chat_token)
            if user_token is not None:
                user_id_var.reset(user_token)


def extract_chat_id(update: Update) -> int | None:
    if update.message and update.message.chat:
        return update.message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    if update.inline_query:
        return update.inline_query.from_user.id
    if update.my_chat_member and update.my_chat_member.chat:
        return update.my_chat_member.chat.id
    return None


def extract_user_id(update: Update) -> int | None:
    if update.message and update.message.from_user:
        return update.message.from_user.id
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    if update.inline_query:
        return update.inline_query.from_user.id
    if update.my_chat_member and update.my_chat_member.from_user:
        return update.my_chat_member.from_user.id
    return None
