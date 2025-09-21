from __future__ import annotations

import json
import re
from typing import Union

from common.openai_client import ensure_openai_client
from logger.config import get_logger

logger = get_logger(__name__)

FAQ_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай естественно и дружелюбно, от первого лица ("я", "мы"), кратко и по делу.
Используй только факты из контекста, не ссылайся на "контекст", "базу знаний" и т.п.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>. Никогда не используй блоки кода (```).
"""

DEVICE_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Говори как живой человек: вежливо, уверенно, от первого лица ("я", "мы"), без канцелярита.
ЗАПРЕЩЕНО употреблять фразы вроде: "судя по предоставленной информации", "в контексте", "согласно данным" и т.п.
Опирайся только на данные из контекста. Не выдумывай характеристики и ссылки.

Строгие правила:
- Алиасы используй только для сопоставления модели. В ответе алиасы НЕ перечисляй.
- Показывай ТОЛЬКО те модели, которые пользователь явно назвал (включая их алиасы/варианты написания).
- Если совпадение модели неочевидно — приведи ближайший вариант и вежливо попроси уточнить точную модель.
- Если пользователь спросил про одну модель — не перечисляй все остальное.
- В конце ответа добавь гарантию и ссылки (если есть в данных):
  • "Гарантия: N лет/год."
  • Ссылки отдавай как HTML: <a href="...">Страница модели</a>, <a href="...">Обновления</a>.
- Разрешённые теги: <b>, <i>, <u>, <pre>, <a>. Никогда не используй блоки кода (```).
"""

OTHER_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай по-человечески, от первого лица, дружелюбно.
Если вопрос не про технику Fujida — дай краткий смолток-ответ и предложи обратиться по технике при необходимости.
Разрешённые теги: <b>, <i>, <u>, <pre>, <a>. Никогда не используй блоки кода (```).
"""

FALLBACK_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай вежливо, от первого лица. Не говори, что чего-то не знаешь.
Не выдумывай ссылки. Разрешённые теги: <b>, <i>, <u>, <pre>, <a>. Без блоков кода (```).
"""

FALLBACK_PROMPT = """
Сообщение пользователя: "{user_message}"

Правила ответа:
- Не используй смайлики.
- Если это приветствие, прощание или смолток — ответь дружелюбно.
- Если сообщение похоже на название модели — вежливо попроси уточнить модель.
- Если вопрос совсем не по теме — дай короткий дружеский ответ.
"""

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_CODE_FENCE_RE = re.compile(r"```.+?```", flags=re.DOTALL)

def _markdown_links_to_html(text: str) -> str:
    """
    Преобразует Markdown-ссылки в HTML <a href="...">…</a>
    """
    def repl(m: re.Match) -> str:
        label = m.group(1).strip()
        url = m.group(2).strip()
        return f'<a href="{url}">{label}</a>'
    return _MD_LINK_RE.sub(repl, text)

def _strip_code_fences(text: str) -> str:
    """
    На всякий случай убираем тройные бэктики с содержимым.
    """
    return _CODE_FENCE_RE.sub("", text)

def _clean_meta_phrases(text: str) -> str:
    """
    Мягкая чистка возможных служебных оговорок (если вдруг проскочат).
    Не агрессивная, чтобы не портить нормальные предложения.
    """
    bad_bits = [
        "судя по предоставленной информации",
        "согласно предоставленным данным",
        "в контексте",
        "согласно контексту",
        "согласно данным",
        "на основе предоставленных данных",
    ]
    out = text
    for b in bad_bits:
        out = re.sub(rf"\b{re.escape(b)}\b[:,\s]*", "", out, flags=re.IGNORECASE)
    return out


def _postprocess_answer(text: str) -> str:
    text = _strip_code_fences(text)
    text = _markdown_links_to_html(text)
    text = _clean_meta_phrases(text)
    return text.strip()


class AnswerService:
    def __init__(self, model: str = "gpt-4o") -> None:
        self._model = model

    async def generate(self, user_message: str, context: Union[str, dict, list], intent: str) -> str:
        """
        Сгенерировать ответ c учётом интента и контекста (строка или JSON).
        Гарантируем HTML-ссылки и "человеческий" тон.
        """
        if intent == "FAQ":
            system_prompt = FAQ_SYSTEM_PROMPT
        elif intent == "Device":
            system_prompt = DEVICE_SYSTEM_PROMPT
        else:
            system_prompt = OTHER_SYSTEM_PROMPT

        if isinstance(context, (dict, list)):
            context_str = json.dumps(context, ensure_ascii=False)
        else:
            context_str = str(context or "")

        prompt = f"""
Пользователь спросил: "{user_message}"

Как отвечать:
- Говори от первого лица, естественно и уверенно.
- Не упоминай, что ты смотришь на "контекст", "базу" и т.п.
- Используй только факты из переданных данных. Ничего не выдумывай.
- Если речь о моделях — показывай только явно упомянутые пользователем (учитывая алиасы).
- Если совпадение неочевидно — приведи ближайший вариант и вежливо попроси уточнить модель.
- В конце, если есть, добавь гарантию и ссылки: HTML вида <a href="...">Страница модели</a>, <a href="...">Обновления</a>.

Данные для ответа (не меняй и не дополняй):
{context_str}

Сформируй полезный ответ пользователю.
""".strip()

        logger.debug("AnswerService.generate prompt=%s", prompt)
        logger.debug("AnswerService.generate context_preview=%s", context_str[:1500])

        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.output_text.strip()
        return _postprocess_answer(raw)

    async def fallback(self, user_message: str) -> str:
        prompt = FALLBACK_PROMPT.format(user_message=user_message)
        logger.debug("AnswerService.fallback prompt=%s", prompt)

        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.output_text.strip()
        return _postprocess_answer(raw)