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
Пользователь спросил: "{user_message}"

Сформулируй вежливый и естественный ответ:
- Если вопрос хотя бы немного связан с техникой Fujida, ответь кратко и добавь, что на этот вопрос лучше сможет ответить поддержка Fujida.
- Если вопрос совсем не по теме (например про погоду, животных, политику и т.п.), дай лёгкий ответ в стиле small talk.
- Если вопрос похож на название модели, то попроси уточнить, или сразу обратиться в поддержку.
- Никогда не говори, что у тебя нет ответа или что ты чего-то не знаешь, или ты что то не нашел.
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