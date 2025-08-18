import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
chat_id_var: ContextVar[int | None] = ContextVar("chat_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)


def gen_request_id() -> str:
    return uuid.uuid4().hex
