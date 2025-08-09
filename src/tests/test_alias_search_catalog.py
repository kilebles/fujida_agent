import json
import pathlib
from typing import Iterable

import pytest
import pytest_asyncio


def _project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def _devices_path() -> pathlib.Path:
    return _project_root() / "src" / "common" / "devices.json"


def _load_models() -> list[str]:
    data = json.loads(_devices_path().read_text(encoding="utf-8"))
    out: list[str] = []
    for item in data:
        m = item.get("model")
        if m:
            out.append(m)
    return out


@pytest_asyncio.fixture
async def catalog_alias_service(monkeypatch):
    """Греет сервис на основе каталога из devices.json без БД."""
    from apps.knowledge_base.services import alias_search as mod

    models = _load_models()

    class FakeRepo:
        def __init__(self, session):
            ...

        async def list_alias_pairs(self) -> Iterable[tuple[str, int]]:
            return []

        async def list_device_titles(self) -> Iterable[tuple[int, str]]:
            return [(i + 1, m) for i, m in enumerate(models)]

    monkeypatch.setattr(mod, "DeviceRepo", FakeRepo)
    service = mod.AliasSearchService()
    await service.warmup(session=None)
    return service, models


@pytest.mark.parametrize("take", [50])
def test_every_model_exact_name_is_top1(catalog_alias_service, take):
    """Каждая модель из каталога по точному названию должна быть Top-1."""
    service, models = catalog_alias_service
    subset = models[:take]
    for m in subset:
        res = service.find_models(m)
        assert res and res[0] == m


@pytest.mark.parametrize(
    ("query", "expected_prefix"),
    [
        ("карма блис", "Fujida Karma Bliss"),
        ("карма про макс", "Fujida Karma Pro Max"),
        ("карма про макс вайфай", "Fujida Karma Pro Max"),
        ("karma bliss max", "Fujida Karma Bliss Max"),
        ("karma one", "Fujida Karma One"),
        ("karma slim", "Fujida Karma Slim"),
        ("карма блик дуо вайфай", "Fujida Karma Blik Duo WiFi"),
        ("zoom blik s duo wifi", "Fujida Zoom Blik S Duo WiFi"),
        ("зум хит с дуо вайфай", "Fujida Zoom Hit S Duo WiFi"),
        ("zoom hit s wifi", "Fujida Zoom Hit S WiFi"),
        ("zoom smart se duo wifi", "Fujida Zoom Smart SE Duo WiFi"),
        ("zoom smart s wifi", "Fujida Zoom Smart S WiFi"),
        ("zoom smart", "Fujida Zoom Smart"),
        ("zoom okko wifi", "Fujida Zoom Okko WiFi"),
        ("карма про", "Fujida Karma Pro"),
        ("карма", "Fujida Karma"),
    ],
)
def test_realistic_queries_prefix_match(catalog_alias_service, query, expected_prefix):
    """Живые фразы должны приводить к ожидаемой серии/варианту."""
    service, models = catalog_alias_service
    if not any(m.startswith(expected_prefix) for m in models):
        pytest.skip(f"В каталоге нет модели с префиксом '{expected_prefix}'")
    res = service.find_models(query)
    assert res and res[0].startswith(expected_prefix)


@pytest.mark.parametrize(
    ("query", "exp_a_prefix", "exp_b_prefix"),
    [
        ("карма блис или карма про", "Fujida Karma Bliss", "Fujida Karma Pro"),
        ("karma pro max vs karma bliss", "Fujida Karma Pro Max", "Fujida Karma Bliss"),
        ("zoom blik s duo wifi / zoom hit s wifi", "Fujida Zoom Blik S Duo WiFi", "Fujida Zoom Hit S WiFi"),
    ],
)
def test_disjunction_top1_per_side(catalog_alias_service, query, exp_a_prefix, exp_b_prefix):
    """В запросах-сравнениях должен быть лучший кандидат для каждой части."""
    service, models = catalog_alias_service
    for pref in (exp_a_prefix, exp_b_prefix):
        if not any(m.startswith(pref) for m in models):
            pytest.skip(f"В каталоге нет модели с префиксом '{pref}'")
    res = service.find_models(query)
    assert len(res) >= 2
    assert res[0].startswith(exp_a_prefix)
    assert res[1].startswith(exp_b_prefix)
