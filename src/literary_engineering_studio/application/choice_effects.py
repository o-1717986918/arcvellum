"""Studio-owned effects for durable Engine human-choice records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_manager import record_direction


DIRECTION_DECISIONS = {
    "revision_direction",
    "word_budget_direction",
    "cross_asset_alignment",
    "general_project_choice",
}


def apply_choice_effect(
    project_root: Path,
    payload: dict[str, Any],
    choice: dict[str, Any],
    result: dict[str, Any],
    *,
    style_mount_service: Any | None,
) -> None:
    decision_type = str(
        choice.get("decision_type")
        or payload.get("decision_type")
        or ""
    )
    actor = str(choice.get("actor") or payload.get("actor") or "user-ui")
    if decision_type in DIRECTION_DECISIONS:
        direction = record_direction(
            project_root,
            choice_direction_message(choice),
            actor=actor,
        )
        result["materialized"] = str(
            direction.get("digest") or result.get("materialized") or ""
        )
        result["effect"] = {
            "kind": "creative-direction",
            "summary": "已写入项目创作方向，下一份任务包会自动携带这项选择。",
            "path": result["materialized"],
        }
        return
    if decision_type == "style_mount":
        _apply_style_mount(
            project_root,
            choice,
            result,
            style_mount_service=style_mount_service,
        )
        return
    result["effect"] = {
        "kind": "formal-choice",
        "summary": "已记录正式选择，状态机将按对应门禁继续验证。",
        "path": str(
            result.get("materialized")
            or result.get("choice_path")
            or ""
        ),
    }


def choice_direction_message(choice: dict[str, Any]) -> str:
    decision_type = str(
        choice.get("decision_type") or "general_project_choice"
    )
    selected = str(choice.get("selected") or "")
    rationale = str(
        choice.get("rationale") or "用户通过 Studio 确认这一方向。"
    )
    target = (
        choice.get("target")
        if isinstance(choice.get("target"), dict)
        else {}
    )
    target_text = ", ".join(
        f"{key}={value}"
        for key, value in target.items()
        if str(value).strip()
    ) or "project"
    return (
        f"【用户正式选择 / {decision_type}】\n"
        f"目标：{target_text}\n"
        f"选择：{selected}\n"
        f"理由：{rationale}\n"
        "执行要求：后续任务必须把该选择作为创作与审查依据；"
        "它不取代 canon、review、promotion 或 release 门禁。"
    )


def _apply_style_mount(
    project_root: Path,
    choice: dict[str, Any],
    result: dict[str, Any],
    *,
    style_mount_service: Any | None,
) -> None:
    if style_mount_service is None:
        raise RuntimeError(
            "controlled style mount service is required for style decisions"
        )
    mounted = style_mount_service.mount_choice(project_root, choice)
    result["style_mount"] = mounted
    result["materialized"] = str(
        mounted.get("active_manifest")
        or result.get("materialized")
        or ""
    )
    result["effect"] = {
        "kind": "style-mounted",
        "summary": (
            "已原子挂载不可变文风版本；后续正文与审查任务"
            "将读取同一版本身份。"
        ),
        "path": result["materialized"],
        "style_id": str(mounted.get("style_id") or ""),
        "version_id": str(mounted.get("version_id") or ""),
        "content_hash": str(mounted.get("content_hash") or ""),
    }
