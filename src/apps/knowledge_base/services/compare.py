from __future__ import annotations

from typing import Dict, List, Tuple


def _norm(v: str | None) -> str:
    """
    Возвращает нормализованное строковое значение для сравнения.
    """
    s = str(v or "").strip().lower()
    repl = {
        "да": "есть",
        "yes": "есть",
        "нет данных": "",
        "n/a": "",
        "na": "",
        "none": "",
        "no": "нет",
    }
    return repl.get(s, s)


def diff_information(
    items: List[Tuple[str, dict]],
    drop_equal: bool = True,
) -> Dict[str, Dict[str, str]]:
    """
    Возвращает карту ключ -> {model: value} только по отличающимся значениям.
    """
    if not items:
        return {}

    all_keys: set[str] = set()
    for _, info in items:
        all_keys.update((info or {}).keys())

    out: Dict[str, Dict[str, str]] = {}
    for key in sorted(all_keys):
        values_raw: Dict[str, str] = {m: str((info or {}).get(key, "")).strip() for m, info in items}
        values_norm = {_norm(values_raw[m]) for m in values_raw}
        if drop_equal and len({v for v in values_norm if v != ""}) <= 1:
            continue
        clean = {m: v for m, v in values_raw.items() if v}
        if not clean:
            continue
        out[key] = clean

    return out
