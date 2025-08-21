from __future__ import annotations

from bs4 import BeautifulSoup
from typing import Any, Mapping


ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "del", "strike",
    "code", "pre", "a", "tg-spoiler", "span", "blockquote", "tg-emoji",
}
ALLOWED_ATTRS = {
    "a": {"href"},
    "tg-emoji": {"emoji-id"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
}


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


def sanitize_telegram_html(text: str) -> str:
    """
    Удаляет неразрешённые Telegram-теги и атрибуты.
    """
    soup = BeautifulSoup(text, "html.parser")

    for tag in soup.find_all(True):
        tag_name = tag.name.lower()
        if tag_name not in ALLOWED_TAGS:
            tag.unwrap()
            continue

        allowed_attrs = ALLOWED_ATTRS.get(tag_name, set())
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed_attrs}

        if tag_name == "span" and tag.attrs.get("class") != ["tg-spoiler"]:
            tag.unwrap()

        if tag_name == "a":
            href = tag.attrs.get("href", "")
            if not href.startswith(("http://", "https://", "tg://")):
                tag.unwrap()

    return str(soup)
