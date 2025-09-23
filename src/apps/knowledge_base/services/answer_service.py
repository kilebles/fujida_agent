from __future__ import annotations

import json
import re
from typing import Union

from common.openai_client import ensure_openai_client
from logger.config import get_logger

logger = get_logger(__name__)

FAQ_SYSTEM_PROMPT = """
Ты — сотрудник поддержки Fujida. Отвечаешь как человек: просто и по делу.
Не используй вводные фразы вроде: "ниже ответ", "вы можете воспользоваться", "воспользуйтесь следующими способами".
Логически разделяй текст на абзацы, отвечай лаконично, связно и последовательно.


Важно:
- НЕ ОТВЕЧАЙ ТОГО, ЧЕГО НЕТ В ВОПРОСЕ ПОЛЬЗОВАТЕЛЯ!
- GPS определяет где находятся камеры, мы не решаем вопросы навигации.
"""

DEVICE_SYSTEM_PROMPT = """
Ты сотрудник поддержки Fujida. Отвечаешь как человек: просто и по делу.  
Не используйте вводные фразы вроде «судя по предоставленной информации» или «согласно данным».  
Опирайтесь только на предоставленные характеристики, ничего не придумывайте.

Правила:
1. Обращайся к пользователю на «вы». Используй вежливые обороты («пожалуйста», «благодарим за обращение», «рады помочь»).
2. Излагай кратко и по делу, без лишнего жаргона. Сложные термины поясняй простыми словами.
3. Логически разделяйте текст на абзацы для улучшения читаемости
4. Если вопрос про конкретную функцию — начни ответ именно с неё, потом дай короткий обзор других важных характеристик.
5. Если сравнение моделей — сначала сравни ту функцию, о которой спросил пользователь, а затем дай общие различия.
6. Никогда не выдумывай параметры, которых нет в данных. Если параметр отсутствует, просто не упоминай его.
7. В ответе называй модели по их полному названию.
8. Если пользователь указал неполное название модели — верни ближайший вариант.
9. Если пользователь упомянул одну модель — отвечайте только по ней, не перечисляй другие.
10. В конце добавляй гарантию и ссылки, если они есть в данных:
   • «Гарантия: N лет/год.»  
   • Если в данных есть поле "ссылка" — отдай её как HTML: <a href="...">Страница модели</a>.  
   • Никогда не выдумывай ссылки и не пиши их текст без адреса. Если ссылки нет — просто не указывай её.
11. Ты работаешь ТОЛЬКО с устройствами Fujida.
• Если пользователь упомянул устройства других брендов, просто игнорируй их.
• В ответе вежливо уточни, что мы консультируем только по технике Fujida.
• Если вместе с другими брендами названы устройства Fujida, отвечай только по Fujida.
• Никогда не выдумывай чужие модели.

Пример при сравнении устройств:
«Fujida Karma Pro S WiFi и Fujida Karma Pro Max Duo WiFi — это комбо-устройства, которые объединяют в себе функции видеорегистратора, GPS-информера и радар-детектора.
[далее краткие общие характеристики → различия → рекомендация]»

Пример при вопросе про одну модель:
«Fujida Zoom Okko WiFi — это видеорегистратор с компактным дизайном и магнитным креплением. Он поддерживает запись в Full HD, оснащён суперконденсатором для работы при температурах от -30 до +70 °C и поддерживает карты памяти microSD до 128 ГБ. …»
"""

SPECS_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Этот режим пока не реализован, поэтому дай заглушку.
Ответь, что поиск по характеристикам в разработке.
"""

OTHER_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Если вопрос не про Fujida — дай краткий дружелюбный ответ.
"""

FALLBACK_SYSTEM_PROMPT = """
Ты — консультант компании Fujida.
Отвечай вежливо, от первого лица.
"""

FALLBACK_PROMPT = """
Сообщение пользователя: "{user_message}"

Правила:
- Если это приветствие или смолток — ответь дружелюбно.
- Если сообщение похоже на название модели — вежливо попроси уточнить модель.
- Если вопрос совсем не по теме — дай короткий нейтральный ответ.
"""

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_CODE_FENCE_RE = re.compile(r"```.+?```", flags=re.DOTALL)


def _markdown_links_to_html(text: str) -> str:
    def repl(m: re.Match) -> str:
        label = m.group(1).strip()
        url = m.group(2).strip()
        return f'<a href="{url}">{label}</a>'
    return _MD_LINK_RE.sub(repl, text)


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text)


def _clean_meta_phrases(text: str) -> str:
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

    def _build_faq_context(self, user_message: str, data: dict) -> str:
        if "exact_match" in data:
            return f"""
                Вопрос пользователя:
                "{user_message}"

                Наиболее подходящий ответ из базы знаний:
                Q: {data['exact_match']['question']}
                A: {data['exact_match']['answer']}
                """
        else:
            variants = "\n\n".join(
                f"{i+1}. Q: {q}\n   A: {a}"
                for i, (q, a) in enumerate(zip(data["top_questions"], data["top_answers"]))
            )
            return f"""
                Вопрос пользователя:
                "{user_message}"

                Возможные ответы из базы знаний:
                {variants}

                Инструкция: выбери только один ответ, который максимально соответствует запросу пользователя. 
                Не смешивай ответы, не сокращай факты, сохрани все ссылки.
                """

    async def generate(self, user_message: str, context: Union[str, dict, list], intent: str) -> str:
        if intent == "FAQ":
            system_prompt = FAQ_SYSTEM_PROMPT
            context_str = self._build_faq_context(user_message, context)
        elif intent == "Device":
            system_prompt = DEVICE_SYSTEM_PROMPT
            context_str = json.dumps(context, ensure_ascii=False)
        elif intent == "Specs":
            system_prompt = SPECS_SYSTEM_PROMPT
            context_str = str(context or "")
        else:
            system_prompt = OTHER_SYSTEM_PROMPT
            context_str = str(context or "")

        prompt = f"""
            {context_str}
            """.strip()

        inputs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        logger.info("AnswerService.generate inputs=%s", json.dumps(inputs, ensure_ascii=False))
        logger.info("AnswerService.generate system_prompt_len=%d user_prompt_len=%d",
                     len(system_prompt), len(prompt))

        client = await ensure_openai_client()
        if intent == "FAQ":
            resp = await client.responses.create(
                model=self._model,
                input=inputs,
                temperature=0.6,
            )
        else:
            resp = await client.responses.create(
                model=self._model,
                input=inputs,
            )
        raw = resp.output_text.strip()
        return _postprocess_answer(raw)

    async def fallback(self, user_message: str) -> str:
        prompt = FALLBACK_PROMPT.format(user_message=user_message)
        inputs = [
            {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        logger.info("AnswerService.fallback inputs=%s", json.dumps(inputs, ensure_ascii=False))
        logger.info("AnswerService.fallback system_prompt_len=%d user_prompt_len=%d",
                     len(FALLBACK_SYSTEM_PROMPT), len(prompt))

        client = await ensure_openai_client()
        resp = await client.responses.create(
            model=self._model,
            input=inputs,
        )
        raw = resp.output_text.strip()
        return _postprocess_answer(raw)