import pathlib
import re
import sys

import pytest_asyncio

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def _normalize_simple(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-zа-я0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@pytest_asyncio.fixture
async def alias_service(monkeypatch):
    from apps.knowledge_base.services import alias_search as mod

    class FakeRepo:
        def __init__(self, session):
            ...

        async def list_alias_pairs(self):
            return []

        async def list_device_titles(self):
            return [
                (1, "Fujida Karma"),
                (2, "Fujida Karma Pro"),
                (3, "Fujida Karma Bliss"),
                (4, "Fujida Karma Bliss Max WiFi"),
                (5, "Fujida Karma Pro Max Duo WiFi"),
                (6, "Fujida Karma Pro Max AI WiFi"),
            ]

    monkeypatch.setattr(mod, "DeviceRepo", FakeRepo)
    monkeypatch.setattr(mod, "normalize", _normalize_simple)

    service = mod.AliasSearchService()
    await service.warmup(session=None)
    return service
