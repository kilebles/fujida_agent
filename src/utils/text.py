from __future__ import annotations

from typing import Any, Mapping

def normalize(text: str) -> str:
    """
    Приводит строку к единому виду
    """
    x = text.lower().strip()
    x = x.replace("-", " ").replace("_", " ")
    x = " ".join(x.split())
    return x


def strip_empty_fields(obj: Any) -> Any:
    """
    Удаляет пустые списки, словари, None и пустые строки.
    """
    if isinstance(obj, Mapping):
        out = {k: strip_empty_fields(v) for k, v in obj.items()}
        return {k: v for k, v in out.items() if v not in (None, [], {}, "")}
    if isinstance(obj, list):
        out = [strip_empty_fields(x) for x in obj]
        return [x for x in out if x not in (None, [], {}, "")]
    return obj

