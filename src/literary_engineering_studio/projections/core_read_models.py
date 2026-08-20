"""Thin reuse layer for the core API read models and human-choice services."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable

from literary_engineering_studio_engine.public.workflow import project_workflow_dashboard

from ..application.choice_effects import apply_choice_effect


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
    del config
    with ENGINE_ACCESS_LOCK:
        payload = project_workflow_dashboard(project_root)
    frontend = payload.get("frontend") if isinstance(payload.get("frontend"), dict) else {}
    return {
        "ok": True,
        "project_root": str(project_root),
        "dashboard": payload,
        "summary": payload.get("summary", {}),
        "route_audits": payload.get("route_audits", []),
        "next_actions": payload.get("next_actions", []),
        "recent_events": payload.get("recent_events", []),
        "paths": {
            "markdown": "workflow/dashboard/workflow_dashboard.md",
            "json": str(frontend.get("json") or "workflow/dashboard/workflow_dashboard.json"),
            "html": str(frontend.get("html") or "workflow/dashboard/workflow_dashboard.html"),
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


def build_narrative_evidence(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    payload = _function(config, "project_library", "build_narrative_evidence")(project_root)
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


def record_choice(
    config: dict[str, Any],
    project_root: Path,
    payload: dict[str, Any],
    *,
    style_mount_service: Any | None = None,
) -> dict[str, Any]:
    before = current_choices(config, project_root)
    result = _function(config, "project_interaction", "record_human_choice")(project_root, payload)
    choice = result.get("choice") if isinstance(result.get("choice"), dict) else {}
    if result.get("duplicate") and choice.get("consumed") is True:
        return _choice_receipt(config, project_root, result, before)
    if not bool(payload.get("materialize", True)):
        return _choice_receipt(config, project_root, result, before)

    apply_choice_effect(
        project_root,
        payload,
        choice,
        result,
        style_mount_service=style_mount_service,
    )
    materialized = str(result.get("materialized") or "")
    finalized = _function(config, "project_interaction", "finalize_human_choice")(
        project_root,
        str(choice.get("choice_id") or payload.get("choice_id") or ""),
        materialized=materialized,
        effect=result.get("effect") if isinstance(result.get("effect"), dict) else {},
        consumed=bool(materialized),
    )
    result["choice"] = finalized
    return _choice_receipt(config, project_root, result, before)


def _choice_receipt(
    config: dict[str, Any],
    project_root: Path,
    result: dict[str, Any],
    before: dict[str, Any],
) -> dict[str, Any]:
    choice = result.get("choice") if isinstance(result.get("choice"), dict) else {}
    after = current_choices(config, project_root)
    before_ids = [
        str(item.get("choice_id") or "")
        for item in before.get("choices", [])
        if isinstance(item, dict)
    ]
    after_ids = [
        str(item.get("choice_id") or "")
        for item in after.get("choices", [])
        if isinstance(item, dict)
    ]
    choice_id = str(choice.get("choice_id") or "")
    selected = str(choice.get("selected") or "")
    receipt_id = "receipt." + hashlib.sha256(f"{choice_id}:{selected}".encode("utf-8")).hexdigest()[:24]
    consumed = bool(choice.get("consumed")) and choice_id not in after_ids
    return {
        **result,
        "schema": "arcvellum/human-choice-receipt/v0.2",
        "receipt_id": receipt_id,
        "choice_id": choice_id,
        "selected": selected,
        "recorded": bool(choice),
        "materialized": str(result.get("materialized") or choice.get("materialized") or ""),
        "materialized_ok": bool(result.get("materialized") or choice.get("materialized")),
        "consumed": consumed,
        "state_before": {"pending_choice_ids": before_ids},
        "state_after": {"pending_choice_ids": after_ids},
    }


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
