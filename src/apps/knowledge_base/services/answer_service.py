from common.openai_client import ensure_openai_client


class AnswerService:
    def __init__(self, model: str = "gpt-4o") -> None:
        self._model = model

    async def generate(self, user_message: str, context: str) -> str:
        prompt = f"""
            Пользователь спросил: "{user_message}"

            Вот релевантные данные из базы знаний:
            {context}

            Сформулируй понятный и полезный ответ для пользователя.
            - Не придумывай информацию, которой нет в контексте.
            - Не сокращай информацию об устройствах.
            - Если нужно сравнение, укажи ключевые отличия простым языком.
            """
        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=[{"role": "user", "content": prompt}],
        )
        return resp.output_text