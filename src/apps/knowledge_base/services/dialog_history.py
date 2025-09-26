import json
from typing import Literal
from common.redis_client import get_redis

MessageRole = Literal["user", "assistant"]


class DialogHistory:
    def __init__(self, max_messages: int = 10) -> None:
        self.max_messages = max_messages

    def _key(self, chat_id: str) -> str:
        return f"dialog:{chat_id}"

    async def add(self, chat_id: str, role: MessageRole, content: str) -> None:
        redis = await get_redis()
        entry = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        await redis.rpush(self._key(chat_id), entry)
        await redis.ltrim(self._key(chat_id), -self.max_messages, -1)

    async def get(self, chat_id: str) -> list[dict]:
        redis = await get_redis()
        raw_entries = await redis.lrange(self._key(chat_id), 0, -1)
        out: list[dict] = []
        for raw in raw_entries:
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
        return out

    async def clear(self, chat_id: str) -> None:
        redis = await get_redis()
        await redis.delete(self._key(chat_id))