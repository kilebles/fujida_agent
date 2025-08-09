from sqlalchemy import select, func, cast
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from db.session import async_session_maker
from db.models.faq_entry import FAQEntry
from common.openai_client import openai_client
from apps.knowledge_base.prompt_template import build_knowledge_prompt


async def search_similar_faqs(
    embedding: list[float],
    session: AsyncSession,
    top_n: int = 5,
) -> list[FAQEntry]:
    stmt = (
        select(FAQEntry)
        .order_by(func.cosine_distance(FAQEntry.embedding, cast(embedding, Vector)))
        .limit(top_n)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def build_context(faqs: list[FAQEntry]) -> str:
    return "\n\n".join(f"Q: {faq.question}\nA: {faq.answer}" for faq in faqs)


async def generate_faq_response(user_message: str) -> str:
    """
    Генерирует ответ на основе базы знаний и сообщения.
    """
    embedding_response = await openai_client.embeddings.create(
        input=user_message,
        model="text-embedding-3-small",
    )
    query_embedding = embedding_response.data[0].embedding

    async with async_session_maker() as session:
        faqs = await search_similar_faqs(query_embedding, session)

    if not faqs:
        return "Не удалось найти подходящую информацию в базе знаний."

    context = await build_context(faqs)
    prompt = build_knowledge_prompt(context, user_message)

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
