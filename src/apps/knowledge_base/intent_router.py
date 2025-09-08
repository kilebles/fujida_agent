from common.openai_client import ensure_openai_client


class IntentRouter:
    async def classify(self, user_message: str) -> str:
        """
        Возвращает intent: 'FAQ', 'Device', 'Other'
        """
        prompt = f"""
            Ты классифицируешь вопросы пользователей о продукции Fujida.

            Категории:
            - FAQ (вопрос о гарантиях, обновлениях, поддержке)
            - Device (характеристики, сравнение моделей, поиск устройства)
            - Other (не связано с продуктами)

            Обрати внимание: у устройств есть разные написания названий.
            Примеры: "про макс", "дуос", "око", "окко", "блисс", "хара", "слим", "хит", "магна", "эра".

            Если сообщение похоже на название или сокращение устройства Fujida — это всегда <Device>.

            Вопрос: "{user_message}"
            Ответ: только одно слово: FAQ, Device или Other.
            """
        client = await ensure_openai_client()
        resp = await client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
        )
        return resp.output_text.strip()