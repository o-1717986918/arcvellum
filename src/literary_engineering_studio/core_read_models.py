"""Thin reuse layer for the core API read models and human-choice services."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable

def install_core_import_path(config: dict[str, Any]) -> Path:
    """Compatibility shim returning the location of the embedded engine."""

    del config
    module = importlib.import_module("literary_engineering_studio_engine")
    return Path(module.__file__).resolve().parent


def build_dashboard(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    result = _function(config, "workflow_dashboard", "build_workflow_dashboard")(project_root)
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
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


def build_activity(config: dict[str, Any], project_root: Path, limit: int = 30) -> dict[str, Any]:
    payload = _function(config, "workflow_activity", "build_workflow_activity")(project_root, limit=limit)
    return {"ok": True, **payload}


def build_task_summary(config: dict[str, Any], project_root: Path, task_id: str) -> dict[str, Any]:
    payload = _function(config, "workflow_activity", "build_task_package_summary")(project_root, task_id)
    return {"ok": True, **payload}


def build_library(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    payload = _function(config, "project_library", "build_project_library")(project_root)
    return {"ok": True, **payload}


def current_choices(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    payload = _function(config, "project_interaction", "build_current_human_choices")(project_root)
    return {"ok": True, **payload}


def record_choice(config: dict[str, Any], project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return _function(config, "project_interaction", "record_human_choice")(project_root, payload)


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
