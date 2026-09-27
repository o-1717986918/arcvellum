"""Evidence-bound natural conversation prompt for the project advisor."""

from __future__ import annotations

import json
from typing import Any

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, render_prompt_template

from .contracts import METADATA_END, METADATA_MARKER


def advisor_prompt(
    question: str,
    history: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
    *,
    session_summary: str = "",
    pinned_preferences: list[str] | None = None,
    persona: dict[str, str] | None = None,
    literary_guidance: str = "",
) -> str:
    recent = conversation_history(history)
    current = json.dumps(public_context(context or {}), ensure_ascii=False)
    selected = persona or {
        "persona_id": "chief-editor",
        "name": "严谨总编",
        "version": "1.0.0",
        "prompt": "以严谨总编的方式自然交流，优先关注长篇结构、人物因果和可执行的取舍。",
    }
    return render_prompt_template("advisor.conversation.protocol", (
        selected.get('name', '严谨总编'),
        selected.get('persona_id', 'chief-editor'),
        selected.get('version', '1.0.0'),
        selected.get('prompt', ''),
        current,
        session_summary or '无',
        json.dumps(pinned_preferences or [], ensure_ascii=False),
        recent,
        METADATA_MARKER,
        METADATA_END,
        question,
        literary_guidance.strip() or prompt_layer_spec("advisor.identity").default_text,
    ))


def conversation_history(history: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in history[-16:]:
        role = str(item.get("role") or "")
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if role == "user":
            value = str(payload.get("question") or "").strip()
            if value:
                lines.append(f"用户：{value}")
        elif role == "advisor":
            value = str(payload.get("message") or payload.get("answer") or "").strip()
            if value:
                lines.append(f"顾问：{value}")
    return "\n".join(lines) or "（这是本次会话的第一条消息。）"


def public_context(context: dict[str, Any]) -> dict[str, str]:
    allowed = ("view", "selected_item", "user_intent")
    return {
        key: str(context.get(key) or "")[:300]
        for key in allowed
        if str(context.get(key) or "").strip()
    }


__all__ = ["advisor_prompt"]
