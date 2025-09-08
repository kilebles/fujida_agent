from common.openai_client import ensure_openai_client


SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай на вопросы пользователей вежливо и понятно.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
Никогда не используй блоки кода (```html и т.п.) и не применяй Markdown и "*".
Никогда не упоминай внутренние данные: "алиасы", "также известно как", "vector_text".
Не подавай виду, что ты получаешь контекст.
Если спрашивают про устройство — используй только описание и характеристики из контекста.
В конце добавляй гарантию и ссылки, если они есть в контексте.
"""

FALLBACK_PROMPT = """
Ты — консультант компании Fujida.
Сообщение пользователя: "{user_message}"

Сформулируй вежливый и естественный ответ:
- Если сообщение похоже на приветствие, прощание или лёгкий смолток (например "привет", "как дела", "спасибо"), ответь так же в дружелюбной форме, без упоминания поддержки.
- Если вопрос связан с техникой Fujida (модели, устройства, характеристики), но точной информации нет, скажи, что лучше уточнить в поддержке Fujida.
- Если сообщение похоже на название модели, попроси уточнить название или порекомендуй обратиться в поддержку.
- Если вопрос совсем не по теме (погода, животные, политика и т.п.), дай короткий дружелюбный ответ в стиле смолток.
- Никогда не говори, что у тебя нет ответа или что ты чего-то не знаешь.
- Никогда не упоминай базы знаний или поиск по базе.
- Не придумывай ссылки и не вводи пользователя в заблуждение.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
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
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.output_text.strip()