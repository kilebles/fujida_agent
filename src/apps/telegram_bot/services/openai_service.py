from common.openai_client import openai_client


async def generate_response(message: str) -> str:
    """
    Генерирует ответ от OpenAI на основе переданного сообщения.
    """
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content
