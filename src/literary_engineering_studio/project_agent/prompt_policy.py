"""Prompt policy for project-level conversations and delegated goals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, render_prompt_template, render_prompt_text

from .delegated_goal import goal_snapshot
from .scope import work_id_for_root
from ..application.creative_configuration import effective_creative_config


def creator_persona_guidance(
    config: dict[str, Any], resolver: Callable[[str, Path | None], str] | None, root: Path,
) -> str:
    application = effective_creative_config(config, root).get("application")
    settings = application.get("scene_creator_v2") if isinstance(application, dict) else None
    if not isinstance(settings, dict) or settings.get("enabled") is not True or not (root / "project.yaml").is_file():
        return ""
    if resolver is None:
        raise RuntimeError("scene creator v2 needs a top-agent prompt resolver")
    guidance = resolver("project_agent.creator_persona.v2", root)
    if not guidance.strip() or "[PENDING_PROMPT_DESIGN:" in guidance:
        raise RuntimeError("scene creator v2 persona prompt design is incomplete")
    return guidance


def natural_prompts_enabled(config: dict[str, Any]) -> bool:
    settings = config.get("application", {}).get("scene_creator_v2", {})
    return isinstance(settings, dict) and settings.get("enabled") is True


def project_prompt_id(layer_id: str, natural: bool) -> str:
    return layer_id.replace("project_agent.", "project_agent.v2.", 1) if natural else layer_id


def project_prompt_options(config: dict[str, Any], resolver, root: Path) -> dict[str, Any]:
    scope = root if (root / "project.yaml").is_file() else None
    reader = (lambda layer_id: resolver(layer_id, scope)) if resolver else None
    return {"natural": natural_prompts_enabled(effective_creative_config(config, root)), "prompt_reader": reader}


def _render_project(layer_id: str, values: tuple[object, ...], natural: bool, prompt_reader=None) -> str:
    if natural:
        identifier = project_prompt_id(layer_id, True)
        text = prompt_reader(identifier) if prompt_reader else prompt_layer_spec(identifier).default_text
        return render_prompt_text(text, values)
    return render_prompt_template(layer_id, values)


def turn_prompt(message: str, session: dict[str, Any], *, natural: bool = False, prompt_reader=None) -> str:
    history: list[str] = []
    for item in list(session.get("messages") or [])[-12:]:
        payload = item.get("payload") if isinstance(item, dict) and isinstance(item.get("payload"), dict) else {}
        text = str(payload.get("text") or "").strip()
        if text:
            speaker = "用户" if item.get("role") == "user" else "ArcVellum"
            history.append(f"{speaker}：{text[:1500]}")
    anchor=Path(str(session.get("project_root") or ""))
    if session.get("project_root") and (anchor / "project.yaml").is_file():
        message = "本会话绑定作品 work_id=" + work_id_for_root(anchor) + "。未明确切换作品时，所有工具使用这一 work_id。\n\n" + message
    recent = "\n".join(history) or "（这是本次会话的第一条消息。）"
    return _render_project("project_agent.turn.protocol", (
        recent,
        message,
    ), natural, prompt_reader)


def system_prompt(
    persona: dict[str, str], *, write_enabled: bool = False, literary_guidance: str = "",
    creator_persona_guidance: str = "",
    natural: bool = False,
    prompt_reader=None,
) -> str:
    name = str(persona.get("name") or "严谨总编")
    identifier = project_prompt_id("project_agent.creative_direction", natural)
    direction = literary_guidance.strip() or (prompt_reader(identifier) if prompt_reader
        else prompt_layer_spec(identifier).default_text)
    template = "project_agent.system.write.protocol" if write_enabled else "project_agent.system.read.protocol"
    base = _render_project(template, (name, str(persona.get("prompt") or "").strip(), direction), natural, prompt_reader)
    status_guidance = (
        '需要核对运行状态时，先调用 project_overview(focus="status") 获取状态摘要；'
        '按摘要指向的工具读取完整决策、档案、正文或控制项，避免为同一问题反复全量读取概况、运行观察和诊断。'
        '状态摘要不能替代文学判断所需的原文、审查证据或正式 Gate。'
    )
    return base + "\n\n" + status_guidance + ("\n\n" + creator_persona_guidance if creator_persona_guidance else "")


def delegated_goal_followup_prompt(
    user_message: str,
    interim_answer: str,
    run: dict[str, Any],
    *, natural: bool = False, prompt_reader=None,
) -> str:
    snapshot = goal_snapshot(run)
    return _render_project("project_agent.goal_followup.protocol", (
        user_message,
        interim_answer or '（无）',
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
    ), natural, prompt_reader)


def delegated_scene_checkpoint_prompt(user_message: str, run: dict[str, Any], work_id: str = "", *, natural: bool = False, prompt_reader=None) -> str:
    snapshot = goal_snapshot(run)
    return _render_project("project_agent.scene_checkpoint.protocol", (
        user_message,
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
        work_id or '沿用当前会话作品',
    ), natural, prompt_reader)


__all__ = ["creator_persona_guidance", "delegated_goal_followup_prompt",
           "delegated_scene_checkpoint_prompt", "system_prompt", "turn_prompt"]
