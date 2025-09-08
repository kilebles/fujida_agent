from common.openai_client import ensure_openai_client


SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай на вопросы пользователей вежливо и понятно.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
Никогда не используй блоки кода (```html и т.п.).
Никогда не упоминай внутренние данные: "алиасы", "также известно как", "vector_text".
Не подавай виду, что ты получаешь контекст.
Если спрашивают про устройство — используй только описание и характеристики из контекста.
В конце добавляй гарантию и ссылки, если они есть в контексте.
"""

FALLBACK_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай на вопросы пользователей вежливо и понятно.
Никогда не говори, что ты чего то не знаешь.
Не придумывай ссылки.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
"""

FALLBACK_PROMPT = """
Сообщение пользователя: "{user_message}"

Правила ответа:
- Не используй смайлики.
- Если это приветствие, прощание или смолток ответь дружелюбно.
- Если сообщение явно связано с техникой Fujida (например "устройство", "характеристики", "камера", "модель"), но точных данных нет — мягко предложи обратиться в поддержку Fujida.
- Если сообщение похоже на название модели, попроси уточнить.
- Если вопрос совсем не по теме (погода, политика, животные и т.п.), дай лёгкий дружеский смолток-ответ.
"""


class AnswerService:
    def __init__(self, model: str = "gpt-4o") -> None:
        self._model = model

    async def generate(self, user_message: str, context: str) -> str:
        prompt = f"""
            Пользователь спросил: "{user_message}"

            Вот релевантные данные из базы знаний:
            {context}

            Сформулируй полезный ответ для пользователя.
            - Не придумывай информации, которой нет в контексте.
            - Не сокращай описания устройств.
            - Используй HTML для Telegram строго по правилам.
            """
        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.output_text.strip()

    async def fallback(self, user_message: str) -> str:
        prompt = FALLBACK_PROMPT.format(user_message=user_message)
        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.output_text.strip()