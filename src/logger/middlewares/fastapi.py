from typing import Callable, Awaitable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send

from settings import config
from logger import get_logger
from logger.context import request_id_var, gen_request_id

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]):
        rid = request.headers.get(config.REQUEST_ID_HEADER) or gen_request_id()
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers[config.REQUEST_ID_HEADER] = rid
            return response
        finally:
            request_id_var.reset(token)


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method")
        path = scope.get("path")
        logger.info("HTTP %s %s", method, path)
        await self.app(scope, receive, send)
