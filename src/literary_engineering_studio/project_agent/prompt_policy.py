"""Prompt policy for project-level conversations and delegated goals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, render_prompt_template

from .delegated_goal import goal_snapshot


def creator_persona_guidance(
    config: dict[str, Any], resolver: Callable[[str, Path | None], str] | None, root: Path,
) -> str:
    application = config.get("application")
    settings = application.get("scene_creator_v2") if isinstance(application, dict) else None
    if not isinstance(settings, dict) or settings.get("enabled") is not True or not (root / "project.yaml").is_file():
        return ""
    if resolver is None:
        raise RuntimeError("scene creator v2 needs a top-agent prompt resolver")
    guidance = resolver("project_agent.creator_persona.v2", root)
    if not guidance.strip() or "[PENDING_PROMPT_DESIGN:" in guidance:
        raise RuntimeError("scene creator v2 persona prompt design is incomplete")
    return guidance


def turn_prompt(message: str, session: dict[str, Any]) -> str:
    history: list[str] = []
    for item in list(session.get("messages") or [])[-12:]:
        payload = item.get("payload") if isinstance(item, dict) and isinstance(item.get("payload"), dict) else {}
        text = str(payload.get("text") or "").strip()
        if text:
            speaker = "用户" if item.get("role") == "user" else "ArcVellum"
            history.append(f"{speaker}：{text[:1500]}")
    recent = "\n".join(history) or "（这是本次会话的第一条消息。）"
    return render_prompt_template("project_agent.turn.protocol", (
        recent,
        message,
    ))


def system_prompt(
    persona: dict[str, str], *, write_enabled: bool = False, literary_guidance: str = "",
    creator_persona_guidance: str = "",
) -> str:
    name = str(persona.get("name") or "严谨总编")
    direction = literary_guidance.strip() or prompt_layer_spec("project_agent.creative_direction").default_text
    template = "project_agent.system.write.protocol" if write_enabled else "project_agent.system.read.protocol"
    base = render_prompt_template(template, (name, str(persona.get("prompt") or "").strip(), direction))
    return base + ("\n\n" + creator_persona_guidance if creator_persona_guidance else "")


def delegated_goal_followup_prompt(
    user_message: str,
    interim_answer: str,
    run: dict[str, Any],
) -> str:
    snapshot = goal_snapshot(run)
    return render_prompt_template("project_agent.goal_followup.protocol", (
        user_message,
        interim_answer or '（无）',
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
    ))


def delegated_scene_checkpoint_prompt(user_message: str, run: dict[str, Any], work_id: str = "") -> str:
    snapshot = goal_snapshot(run)
    return render_prompt_template("project_agent.scene_checkpoint.protocol", (
        user_message,
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
        work_id or '沿用当前会话作品',
    ))


__all__ = ["creator_persona_guidance", "delegated_goal_followup_prompt",
           "delegated_scene_checkpoint_prompt", "system_prompt", "turn_prompt"]
