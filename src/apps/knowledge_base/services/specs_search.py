from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_specs_search_cached: SpecsSearch | None = None


class SpecsSearch:
    """
    Загрузка JSON с устройствами Fujida из src/common/devices.json.
    """

    def __init__(self, json_path: Optional[Path] = None) -> None:
        if json_path is None:
            json_path = Path(__file__).resolve().parents[3] / "common" / "devices.json"

        self._json_path = json_path
        with open(json_path, encoding="utf-8") as f:
            self._devices: List[dict[str, Any]] = json.load(f)

    def all_devices_json(self) -> List[Dict[str, Any]]:
        """
        Возвращает JSON со всеми устройствами для промпта.
        """
        return self._devices


def get_specs_search_cached() -> Optional[SpecsSearch]:
    return _specs_search_cached


def set_specs_search_cached(svc: SpecsSearch | None) -> None:
    global _specs_search_cached
    _specs_search_cached = svc