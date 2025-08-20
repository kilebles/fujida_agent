from __future__ import annotations

from typing import Dict, List


def instructions_text() -> str:
    return (
        "Ты — дружелюбный и полезный помощник компании Fujida. "
        "Отвечай только по продукции Fujida и поддержке устройств. "
        "Используй только данные из контекста. Не выдумывай. "
        "Если информации недостаточно, так и скажи и предложи следующий шаг."
    )


def build_context_message(context: str) -> str:
    return (
        "Контекст — JSON-список объектов {model, description, information}.\n"
        f"{context}"
    )


def build_faq_answer_prompt(user_query: str, top_questions: List[str], top_answers: List[str]) -> str:
    """
    Формирует промпт по FAQ-контексту.
    """
    qa_pairs = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in zip(top_questions, top_answers))
    return (
        f"{instructions_text()}\n\n"
        f"Контекст FAQ:\n{qa_pairs}\n\n"
        f"Вопрос пользователя: {user_query}\n\n"
        "Дай финальный ответ пользователю:"
    )


def build_models_answer_prompt(user_query: str, found_models: List[Dict], information_diff: Dict) -> str:
    """
    Формирует промпт для ответов по моделям и сравнений.
    """
    names = [m.get("model", "") for m in found_models if m.get("model")]
    info_blocks: List[str] = []

    for m in found_models:
        name = m.get("model") or ""
        info = m.get("information") or {}
        candidates = m.get("candidates") or []
        block_parts: List[str] = []
        if info:
            lines = "\n".join(f"- {k}: {v}" for k, v in info.items())
            block_parts.append(f"{name}:\n{lines}")
        if candidates:
            cand_line = ", ".join(candidates)
            block_parts.append(f"Возможные кандидаты: {cand_line}")
        if block_parts:
            info_blocks.append("\n".join(block_parts))

    diff_lines: List[str] = []
    if information_diff:
        for k, v in information_diff.items():
            row = " | ".join(f"{model}: {val}" for model, val in v.items())
            diff_lines.append(f"- {k}: {row}")

    head = f"Модели: {', '.join(names)}" if names else ""
    info_part = "\n\n".join(info_blocks) if info_blocks else ""
    diff_part = "\n".join(diff_lines) if diff_lines else ""

    return (
        f"{instructions_text()}\n\n"
        f"{head}\n\n"
        f"Отличия по характеристикам:\n{diff_part}\n\n"
        f"Полные сведения, если доступны:\n{info_part}\n\n"
        f"Вопрос пользователя: {user_query}\n\n"
        "Если сравнение, перечисли только различающиеся параметры. Если одна модель, кратко опиши ключевые характеристики. Дай финальный ответ:"
    )


def build_specs_answer_prompt(user_query: str, context: str) -> str:
    """
    Формирует промпт для подбора по характеристикам.
    """
    return (
        f"{instructions_text()}\n\n"
        f"{build_context_message(context)}\n\n"
        f"Запрос пользователя: {user_query}\n\n"
        "Подбери подходящие модели и обоснуй выбор по указанным признакам. Дай финальный ответ:"
    )


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
        return build_specs_answer_prompt(
            user_query=user_query,
            context=payload.get("context") or "",
        )
    return build_faq_answer_prompt(user_query, [], [])
