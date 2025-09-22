from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.openai_client import ensure_openai_client


_device_selector_cached: DeviceSelector | None = None


DEVICE_SELECTOR_PROMPT = """
    Ты анализируешь текст пользователя и определяешь, какие устройства Fujida он упомянул.

    У тебя есть список моделей с алиасами:
    {models_text}

    Твоя задача:
    1. Сравни текст пользователя с названиями моделей и алиасами.
    2. Верни список id моделей, которые точно упомянуты в тексте.
    3. Определи, сравнивает ли пользователь несколько моделей.
    Если есть слова вроде "или", "что лучше", "сравни", "разница" → это сравнение.

    Формат ответа строго JSON:
    {{
    "device_ids": ["..."],
    "is_comparing": true/false,
    "question_text": "{user_message}"
    }}
    """


class DeviceSelector:
    """
    Определяет, какие устройства Fujida упомянуты в тексте пользователя,
    """

    def __init__(self, json_path: Optional[Path] = None) -> None:
        if json_path is None:
            json_path = Path(__file__).resolve().parents[3] / "common" / "devices.json"

        self._json_path = json_path
        with open(json_path, encoding="utf-8") as f:
            self._devices: List[dict[str, Any]] = json.load(f)

    def _models_with_aliases(self) -> str:
        """
        Возвращает список моделей и алиасов в компактном виде.
        """
        lines = []
        for d in self._devices:
            aliases = ", ".join(d.get("алиасы", []))
            lines.append(f"id: {d['id']} | модель: {d['название_модели']} | алиасы: {aliases}")
        return "\n".join(lines)

    async def select(self, user_message: str) -> Dict[str, Any]:
        """
        Отправляет текст пользователя + список моделей в LLM,
        чтобы определить, какие модели упомянуты.
        Возвращает JSON: { device_ids, is_comparing, question_text }
        """
        models_text = self._models_with_aliases()

        prompt = DEVICE_SELECTOR_PROMPT.format(
            models_text=models_text,
            user_message=user_message,
        )

        client = await ensure_openai_client()
        resp = await client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
            max_output_tokens=600,
        )

        try:
            parsed = json.loads(resp.output_text)
        except json.JSONDecodeError:
            parsed = {
                "device_ids": [],
                "is_comparing": False,
                "question_text": user_message,
            }
        return parsed


def get_device_selector_cached() -> Optional[DeviceSelector]:
    return _device_selector_cached


def set_device_selector_cached(svc: DeviceSelector | None) -> None:
    global _device_selector_cached
    _device_selector_cached = svc