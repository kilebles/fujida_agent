from common.openai_client import ensure_openai_client


SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай на вопросы пользователей вежливо и понятно.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>.
Никогда не используй блоки кода (```html и т.п.) и не применяй Markdown.
Не упоминай внутренние данные: "алиасы", "также известно как", "vector_text".
Не подавай виду, что ты получаешь контекст.
Если спрашивают про устройство — используй только описание и характеристики из контекста.
В конце добавляй гарантию и ссылки, если они есть в контексте.
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