"""Thin reuse layer for the core API read models and human-choice services."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable


# Core read models materialize dashboard files at stable project paths. The
# initial HTTP request and SSE projection can arrive together, so serialize
# those rebuilds to prevent a reader from observing a partially replaced JSON.
ENGINE_ACCESS_LOCK = threading.RLock()

def install_core_import_path(config: dict[str, Any]) -> Path:
    """Compatibility shim returning the location of the embedded engine."""

    del config
    module = importlib.import_module("literary_engineering_studio_engine")
    return Path(module.__file__).resolve().parent


def build_dashboard(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    with ENGINE_ACCESS_LOCK:
        result = _function(config, "workflow_dashboard", "build_workflow_dashboard")(project_root)
        payload = _read_json_with_retry(result.json_path)
    return {
        "ok": True,
        "project_root": str(project_root),
        "dashboard": payload,
        "summary": payload.get("summary", {}),
        "route_audits": payload.get("route_audits", []),
        "next_actions": payload.get("next_actions", []),
        "recent_events": payload.get("recent_events", []),
        "paths": {
            "markdown": _relative(result.markdown_path, project_root),
            "json": _relative(result.json_path, project_root),
            "html": _relative(result.html_path, project_root),
        },
        "rules": payload.get("rules", []),
    }


def _read_json_with_retry(path: Path, *, attempts: int = 4, delay_seconds: float = 0.025) -> dict[str, Any]:
    last_error: json.JSONDecodeError | None = None
    for attempt in range(attempts):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"expected JSON object: {path}")
            return payload
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error


def build_activity(config: dict[str, Any], project_root: Path, limit: int = 30) -> dict[str, Any]:
    with ENGINE_ACCESS_LOCK:
        payload = _function(config, "workflow_activity", "build_workflow_activity")(project_root, limit=limit)
    return {"ok": True, **payload}


def build_task_summary(config: dict[str, Any], project_root: Path, task_id: str) -> dict[str, Any]:
    payload = _function(config, "workflow_activity", "build_task_package_summary")(project_root, task_id)
    return {"ok": True, **payload}


def build_library(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    payload = _function(config, "project_library", "build_project_library")(project_root)
    return {"ok": True, **payload}


def current_choices(
    config: dict[str, Any],
    project_root: Path,
    *,
    route: str = "",
    dashboard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    builder = _function(config, "project_interaction", "build_current_human_choices")
    if route:
        payload = builder(project_root, route=route)
    else:
        with ENGINE_ACCESS_LOCK:
            payload = builder(project_root, dashboard_payload=dashboard)
    return {"ok": True, **payload}


def record_choice(config: dict[str, Any], project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    result = _function(config, "project_interaction", "record_human_choice")(project_root, payload)
    if not bool(payload.get("materialize", True)):
        return result

    choice = result.get("choice") if isinstance(result.get("choice"), dict) else {}
    decision_type = str(choice.get("decision_type") or payload.get("decision_type") or "")
    selected = str(choice.get("selected") or payload.get("selected") or "")
    actor = str(choice.get("actor") or payload.get("actor") or "user-ui")
    if decision_type in {
        "revision_direction",
        "word_budget_direction",
        "cross_asset_alignment",
        "general_project_choice",
    }:
        from .project_manager import record_direction

        direction = record_direction(project_root, _choice_direction_message(choice), actor=actor)
        result["materialized"] = str(direction.get("digest") or result.get("materialized") or "")
        result["effect"] = {
            "kind": "creative-direction",
            "summary": "已写入项目创作方向，下一份任务包会自动携带这项选择。",
            "path": result["materialized"],
        }
    elif decision_type == "style_mount":
        mounted = mount_style(config, project_root, str((project_root / "style").resolve()), selected)
        result["materialized"] = str(mounted.get("mount_manifest") or result.get("materialized") or "")
        result["effect"] = {
            "kind": "style-mounted",
            "summary": "已挂载正式文风；后续正文与审查任务会读取它。",
            "path": result["materialized"],
        }
    else:
        result["effect"] = {
            "kind": "formal-choice",
            "summary": "已记录正式选择，状态机将按对应门禁继续验证。",
            "path": str(result.get("materialized") or result.get("choice_path") or ""),
        }
    return result


def _choice_direction_message(choice: dict[str, Any]) -> str:
    """Render a compact, task-readable human decision for future task packages."""

    decision_type = str(choice.get("decision_type") or "general_project_choice")
    selected = str(choice.get("selected") or "")
    rationale = str(choice.get("rationale") or "用户通过 Studio 确认这一方向。")
    target = choice.get("target") if isinstance(choice.get("target"), dict) else {}
    target_text = ", ".join(f"{key}={value}" for key, value in target.items() if str(value).strip()) or "project"
    return (
        f"【用户正式选择 / {decision_type}】\n"
        f"目标：{target_text}\n"
        f"选择：{selected}\n"
        f"理由：{rationale}\n"
        "执行要求：后续任务必须把该选择作为创作与审查依据；它不取代 canon、review、promotion 或 release 门禁。"
    )


def save_display_field(config: dict[str, Any], project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return _function(config, "project_interaction", "save_display_field")(
        project_root,
        target_type=str(payload.get("target_type") or ""),
        target_id=str(payload.get("target_id") or ""),
        field=str(payload.get("field") or ""),
        value=payload.get("value"),
        actor=str(payload.get("actor") or "user"),
    )


def record_ui_note(config: dict[str, Any], project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return _function(config, "project_interaction", "record_ui_note")(
        project_root,
        target_type=str(payload.get("target_type") or ""),
        target_id=str(payload.get("target_id") or ""),
        note=str(payload.get("note") or ""),
        actor=str(payload.get("actor") or "user"),
    )


def style_library(config: dict[str, Any], style_library_root: str = "") -> dict[str, Any]:
    module = _module(config, "style_lab")
    root = Path(style_library_root).expanduser().resolve() if style_library_root else module.default_style_library_root()
    library = module.ensure_style_library(root)
    return {
        "ok": True,
        "style_library_root": str(library),
        "default_style_library_root": str(module.default_style_library_root()),
        "authors": module.list_author_projects(library),
        "style_skills": module.list_style_skills(library),
    }


def style_mounts(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    module = _module(config, "style_lab")
    return {
        "ok": True,
        "project_root": str(project_root),
        "active_style_skill": module.active_project_style(project_root),
    }


def mount_style(config: dict[str, Any], project_root: Path, style_library_root: str, style_id: str) -> dict[str, Any]:
    module = _module(config, "style_lab")
    result = module.mount_style_skill(
        project_root,
        library_root=Path(style_library_root).expanduser().resolve() if style_library_root else module.default_style_library_root(),
        style_id=style_id,
        allow_unreviewed=False,
    )
    return {
        "ok": True,
        "project_root": str(result.project_root),
        "style_id": result.style_id,
        "mount_dir": _relative(result.mount_dir, project_root),
        "mount_manifest": _relative(result.mount_manifest_path, project_root),
        "project_style": _relative(result.project_style_path, project_root),
        "active_style_skill": module.active_project_style(project_root),
    }


def _module(config: dict[str, Any], name: str):
    install_core_import_path(config)
    return importlib.import_module(f"literary_engineering_studio_engine.{name}")


def _function(config: dict[str, Any], module: str, name: str) -> Callable[..., Any]:
    return getattr(_module(config, module), name)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())
