from sqlalchemy import select, func, bindparam, text, Text, cast
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector as VectorType

from common.openai_client import openai_client
from utils.text import normalize
from db.models.devices import Device


EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_DIM = 1536


class VectorSearchService:
    """Векторный поиск устройств по pgvector."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _embed(self, query: str) -> list[float]:
        qn = normalize(query)
        r = await openai_client.embeddings.create(input=qn, model=EMBEDDING_MODEL)
        return r.data[0].embedding

    async def topk(
        self,
        query: str,
        top_k: int = 10,
        min_similarity: float | None = None,
        probes: int | None = None,
    ) -> list[str]:
        vec = await self._embed(query)
        qvec = bindparam("qvec", value=vec, type_=VectorType(VECTOR_DIM))

        if probes:
            try:
                await self.session.execute(text(f"SET LOCAL ivfflat.probes = {int(probes)}"))
            except Exception:
                pass

        stmt = (
            select(
                Device.model,
                (1 - func.cosine_distance(Device.embedding, qvec)).label("sim"),
            )
            .where(Device.embedding.is_not(None))
            .order_by(func.cosine_distance(Device.embedding, qvec))
            .limit(int(top_k))
        )
        res = await self.session.execute(stmt)
        rows = res.all()
        
        out: list[str] = []
        for model, sim in rows:
            if min_similarity is not None and sim is not None and float(sim) < float(min_similarity):
                continue
            out.append(model)
            
        return out
