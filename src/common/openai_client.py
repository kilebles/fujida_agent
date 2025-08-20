import importlib.util
import httpx
from openai import AsyncOpenAI
from settings import config

_httpx_client: httpx.AsyncClient | None = None
openai_client: AsyncOpenAI | None = None


def _http2_available() -> bool:
    return importlib.util.find_spec("h2") is not None


def _build_limits() -> httpx.Limits:
    return httpx.Limits(max_connections=200, max_keepalive_connections=100, keepalive_expiry=60.0)


def _build_timeout() -> httpx.Timeout:
    return httpx.Timeout(timeout=40.0, connect=10.0, read=30.0, write=10.0, pool=10.0)


async def init_openai_client() -> None:
    global _httpx_client, openai_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(
            http2=_http2_available(),
            limits=_build_limits(),
            timeout=_build_timeout(),
        )
    if openai_client is None:
        openai_client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            http_client=_httpx_client,
            max_retries=4,
        )


async def ensure_openai_client() -> AsyncOpenAI:
    await init_openai_client()
    assert openai_client is not None
    return openai_client


async def close_openai_client() -> None:
    global _httpx_client, openai_client
    if openai_client is not None:
        openai_client = None
    if _httpx_client is not None:
        await _httpx_client.aclose()
        _httpx_client = None


async def warmup_openai() -> None:
    """
    Мягкий прогрев соединения без жёстких таймаутов.
    """
    await init_openai_client()
    try:
        client = await ensure_openai_client()
        await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=4,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "return JSON"}, {"role": "user", "content": "ping"}],
            timeout=6.0,
        )
    except Exception:
        pass
