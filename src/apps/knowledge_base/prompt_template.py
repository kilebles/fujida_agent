from __future__ import annotations

import json
from typing import Dict, List, Any


def instructions_text() -> str:
    return (
        "Ты — помощник компании Fujida. "
        "Отвечай естественно от первого лица, будто лично помогаешь клиенту. "
        "Не представляйся отдельно (не начинай с «Я — представитель Fujida» или «Моя рекомендация как эксперт»). "
        "Используй только сведения из предоставленных данных, не выдумывай факты. "
        "Если вопрос не про продукцию/поддержку Fujida — мягко объясни, что я могу помочь только по Fujida. "
        "Не упоминай слово «контекст» и не говори «в описании». "
        "Просто рассказывай напрямую про характеристики и особенности моделей."
    )


def build_context_message(context: str) -> str:
    """
    Оборачивает JSON-контекст для передачи в промпт.
    """
    return (
        "Вот сведения о моделях в формате JSON {model, description, information}.\n"
        f"{context}"
    )


def _format_info_block(name: str, info: Dict[str, Any] | None, candidates: List[str] | None) -> str:
    """
    Возвращает текстовый блок с подробностями по модели.
    """
    parts: List[str] = []
    if info:
        lines = "\n".join(f"- {k}: {v}" for k, v in info.items())
        parts.append(f"{name}:\n{lines}")
    if candidates:
        cand_line = ", ".join(candidates)
        parts.append(f"Возможные кандидаты: {cand_line}")
    return "\n".join(parts)


def build_faq_answer_prompt(user_query: str, top_questions: List[str], top_answers: List[str]) -> str:
    """
    Формирует промпт по FAQ-контексту.
    """
    qa_pairs = "\n\n".join(
        f"Q: {q}\nA: {a}" for q, a in zip(top_questions or [], top_answers or [])
    )
    return (
        f"{instructions_text()}\n\n"
        f"FAQ:\n{qa_pairs}\n\n"
        f"Вопрос пользователя: {user_query}\n\n"
        "Сформируй ответ по существу, опираясь на FAQ. "
        "Отвечай от своего лица, как сотрудник Fujida. "
        "Не пиши лишнюю информацию и не задавай наводящие вопросы, если они не требуются."
    )


def build_models_answer_prompt(
    user_query: str,
    found_models: List[Dict],
    information_diff: Dict[str, Dict[str, Any]],
) -> str:
    """
    Формирует промпт для ответов по конкретным моделям и их сравнению.
    """
    names = [m.get("model", "") for m in found_models if m.get("model")]

    info_blocks: List[str] = []
    for m in found_models:
        name = m.get("model") or ""
        info = m.get("information") or {}
        candidates = m.get("candidates") or []
        block = _format_info_block(name, info, candidates)
        if block:
            info_blocks.append(block)

    diff_lines: List[str] = []
    for k, v in (information_diff or {}).items():
        row = " | ".join(f"{model}: {val}" for model, val in v.items())
        diff_lines.append(f"- {k}: {row}")

    head = f"Модели: {', '.join(names)}" if names else ""
    info_part = "\n\n".join(info_blocks) if info_blocks else ""
    diff_part = "\n".join(diff_lines) if diff_lines else ""

    return (
        f"{instructions_text()}\n\n"
        f"{head}\n\n"
        f"Различия по характеристикам:\n{diff_part}\n\n"
        f"Сведения о моделях:\n{info_part}\n\n"
        f"Вопрос пользователя: {user_query}\n\n"
        "Отвечай чётко по запросу. "
        "Если нужно сравнить модели — перечисли различия и сделай вывод, для кого подходит каждая модель. "
        "Если речь об одной модели — кратко расскажи ключевые характеристики. "
        "Если нет данных по характеристикам — отметь это и предложи варианты из списка кандидатов. "
        "Не упоминай слово «контекст» и не ссылайся на описания — просто рассказывай от себя."
    )


def build_specs_answer_prompt(user_query: str, context: str | List | Dict) -> str:
    """
    Формирует промпт для подбора по характеристикам.
    """
    context_str = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False)
    return (
        f"{instructions_text()}\n\n"
        f"{build_context_message(context_str)}\n\n"
        f"Запрос пользователя: {user_query}\n\n"
        "Подбери подходящие модели и обоснуй выбор по их характеристикам. "
        "Дай рекомендацию от своего лица, как эксперт Fujida. "
        "Не упоминай слово «контекст» и не говори «по описанию»."
    )


def _build_context_from_found_models(found_models: List[Dict]) -> List[Dict[str, Any]]:
    """
    Преобразует found_models в контекст [{model, description, information}].
    """
    context: List[Dict[str, Any]] = []
    for m in found_models or []:
        context.append(
            {
                "model": m.get("model") or "",
                "description": m.get("description") or "",
                "information": m.get("information") or {},
            }
        )
    return context


def build_prompt_for_router_payload(payload: Dict) -> str:
    """
    Возвращает готовый промпт в зависимости от route: by_faq, by_name, by_specs.
    """
    route = (payload.get("route") or "").strip().lower()
    user_query = payload.get("user_query") or ""

    if route == "by_faq":
        return build_faq_answer_prompt(
            user_query=user_query,
            top_questions=payload.get("top_questions") or [],
            top_answers=payload.get("top_answers") or [],
        )

    if route == "by_name":
        return build_models_answer_prompt(
            user_query=user_query,
            found_models=payload.get("found_models") or [],
            information_diff=payload.get("information_diff") or {},
        )

    if route == "by_specs":
        raw_context = payload.get("context")
        if not raw_context:
            derived = _build_context_from_found_models(payload.get("found_models") or [])
            if not derived and payload.get("models"):
                derived = [{"model": m, "description": "", "information": {}} for m in payload["models"]]
            raw_context = derived
        return build_specs_answer_prompt(user_query=user_query, context=raw_context)

    return build_faq_answer_prompt(user_query, [], [])
