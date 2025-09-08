from common.openai_client import ensure_openai_client
from logger.config import get_logger

logger = get_logger(__name__)


FAQ_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай так, как если бы ты лично консультировал клиента Fujida.
Сформируй ответ пользователю, на основе ныормации, которая тебе дана.
Если в контексте есть точный ответ, выбери его.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
"""

DEVICE_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай на вопросы пользователей вежливо и подробно.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
Никогда не используй блоки кода (```html и т.п.).
Используй только описание и характеристики из контекста.
В конце добавляй гарантию и ссылки, если они есть в контексте.

Очень важно:
- Используй Алиасы только для сопоставления моделей, не пиши их в ответе.
- Показывай только те модели из контекста, которые явно названы пользователем (или их варианты написания).
- Не добавляй модели, которые пользователь не упомянул.
- Если упомянуты сокращения (например, "про макс"), выбери самую подходящую модель из котекста по алиасам.
"""

OTHER_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай так, как если бы ты лично консультировал клиента Fujida.
Если вопрос не связан с техникой Fujida, дай лёгкий смолток-ответ.
Если пользователь задаёт общий вопрос про устройства, предложи уточнить модель или обратиться в поддержку.
Никогда не говори, что ты чего то не знаешь.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
"""

FALLBACK_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай так, как если бы ты лично консультировал клиента Fujida.
Никогда не говори, что ты чего-то не знаешь.
Не придумывай ссылки.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
"""

FALLBACK_PROMPT = """
Сообщение пользователя: "{user_message}"

Правила ответа:
- Не используй смайлики.
- Если это приветствие, прощание или смолток — ответь дружелюбно.
- Если сообщение явно связано с техникой Fujida (например "устройство", "характеристики", "камера", "модель"), но точных данных нет — мягко предложи обратиться в поддержку Fujida.
- Если сообщение похоже на название модели, попроси уточнить.
- Если вопрос совсем не по теме (погода, политика, животные и т.п.), дай лёгкий дружеский смолток-ответ.
"""


class AnswerService:
    def __init__(self, model: str = "gpt-4o") -> None:
        self._model = model

    async def generate(self, user_message: str, context: str, intent: str) -> str:
        if intent == "FAQ":
            system_prompt = FAQ_SYSTEM_PROMPT
        elif intent == "Device":
            system_prompt = DEVICE_SYSTEM_PROMPT
        else:
            system_prompt = OTHER_SYSTEM_PROMPT

        prompt = f"""
            Пользователь спросил: "{user_message}"
            Вот релевантные данные из базы знаний: {context}
            Сформулируй полезный ответ для пользователя.
            """
        logger.debug("AnswerService.generate prompt=%s", prompt)
        logger.debug("AnswerService.generate context=%s", context)

        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.output_text.strip()

    async def fallback(self, user_message: str) -> str:
        prompt = FALLBACK_PROMPT.format(user_message=user_message)
        logger.debug("AnswerService.fallback prompt=%s", prompt)

        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.output_text.strip()