import asyncio

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from openai import BadRequestError

from apps.telegram_bot.services.voice_service import transcribe_voice
from apps.knowledge_base.intent_router import route_intent_llm
from apps.knowledge_base.prompt_template import build_prompt_for_router_payload
from utils.text import strip_empty_fields, sanitize_telegram_html
from common.openai_client import ensure_openai_client
from logger import get_logger

logger = get_logger(__name__)
router = Router()


def split_message(text: str, limit: int = 4000) -> list[str]:
    parts: list[str] = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    return parts


async def stream_to_telegram(message: Message, prompt: str) -> None:
    bot = message.bot
    client = await ensure_openai_client()
    sent_message: Message | None = None
    buffer: list[str] = []
    full_text: list[str] = []
    last_flush = 0.0
    flush_interval = 1.2
    hard_limit = 4000
    flood_triggered = False

    try:
        async with client.responses.stream(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
        ) as stream:
            async for event in stream:
                if event.type != "response.output_text.delta":
                    continue

                buffer.append(event.delta)
                now = asyncio.get_running_loop().time()

                if buffer and (now - last_flush) >= flush_interval:
                    chunk = "".join(buffer)
                    buffer.clear()
                    full_text.append(chunk)
                    current = "".join(full_text)
                    html = sanitize_telegram_html(current)

                    if not sent_message:
                        stripped = html.strip()
                        if len(stripped) < 20 or stripped in {"<b>", "<i>", "<u>", "<s>", "<code>", "<pre>"}:
                            continue

                        sent_message = await bot.send_message(
                            chat_id=message.chat.id,
                            text=html[:hard_limit] or "…",
                        )
                    elif flood_triggered or len(html) > hard_limit:
                        for piece in split_message(html[len("".join(full_text)) - len(chunk):], hard_limit):
                            await bot.send_message(chat_id=message.chat.id, text=piece, parse_mode="HTML")
                        sent_message = None
                        full_text = []
                        flood_triggered = True
                    else:
                        try:
                            await bot.edit_message_text(
                                chat_id=message.chat.id,
                                message_id=sent_message.message_id,
                                text=html,
                                parse_mode="HTML",
                            )
                        except (TelegramRetryAfter, TelegramBadRequest):
                            flood_triggered = True
                            await bot.send_message(chat_id=message.chat.id, text=chunk, parse_mode="HTML")

                    last_flush = now

            if buffer:
                chunk = "".join(buffer)
                full_text.append(chunk)
                current = "".join(full_text)
                html = sanitize_telegram_html(current)

                if sent_message and not flood_triggered and len(html) <= hard_limit:
                    try:
                        await bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=sent_message.message_id,
                            text=html,
                            parse_mode="HTML",
                        )
                    except (TelegramRetryAfter, TelegramBadRequest):
                        flood_triggered = True
                        for piece in split_message(html, hard_limit):
                            await bot.send_message(chat_id=message.chat.id, text=piece, parse_mode="HTML")
                else:
                    for piece in split_message(html, hard_limit):
                        await bot.send_message(chat_id=message.chat.id, text=piece, parse_mode="HTML")

            await stream.get_final_response()
        return

    except BadRequestError as e:
        try:
            err = e.response.json().get("error") if hasattr(e, "response") else None
            if not (err and err.get("param") == "stream"):
                raise
        except Exception:
            pass

    resp = await client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "user", "content": prompt}],
    )
    text = sanitize_telegram_html(resp.output_text or "")
    for piece in split_message(text, hard_limit):
        await message.answer(piece, parse_mode="HTML")


@router.message(F.text | F.voice)
async def handle_user_message(message: Message) -> None:
    try:
        async with ChatActionSender.typing(
            bot=message.bot,
            chat_id=message.chat.id,
        ):
            user_prompt = message.text or await transcribe_voice(message)
            result = await route_intent_llm(user_prompt)
            clean = strip_empty_fields(
                {**result, "user_query": result.get("user_query") or user_prompt}
            )
            prompt = build_prompt_for_router_payload(clean)
            logger.info(
                "Final prompt for LLM | route=%s | user_query=%s\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
                clean.get("route"), clean.get("user_query"), prompt
            )
            await stream_to_telegram(message, prompt)

    except Exception as e:
        logger.exception("Handler error")
        await message.answer(f"Ошибка: {type(e).__name__}: {e}")
