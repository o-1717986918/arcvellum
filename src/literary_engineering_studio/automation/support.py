"""Pure support functions for autopilot decisions, project progress, and runtime limits."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import threading
from typing import Any

from ..creative_steward import CreativeSteward
from ..project_manager import read_directions
from literary_engineering_studio_engine.public.workflow import build_workflow_state


PROGRESS_ROOTS = (
    "project.yaml", "canon", "characters", "world", "plot", "scenes", "branches",
    "drafts", "reviews", "style", "workflow", "delivery", "releases",
)
PROGRESS_EXCLUDED_PARTS = {
    ".git", "__pycache__", "dashboard", "runtime_choices", "task_runs", "worker_runs", "logs",
}

def _run_steward_decision(
    steward: CreativeSteward,
    project: Path,
    choice: dict[str, Any],
    project_direction: str,
    stop: threading.Event | None,
) -> dict[str, Any]:
    """Preserve compatibility with test or third-party steward adapters."""

    parameters = inspect.signature(steward.decide).parameters
    kwargs: dict[str, Any] = {"project_direction": project_direction}
    if "cancel_event" in parameters:
        kwargs["cancel_event"] = stop
    return steward.decide(project, choice, **kwargs)


def _pending_asset_dependency(project: Path) -> bool:
    """Return whether scene work must yield to a formal candidate-asset gate."""

    try:
        state = build_workflow_state(project, route="character-and-world-assets")
        payload = json.loads(state.json_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    assets = payload.get("assets") if isinstance(payload, dict) else []
    return any(
        isinstance(item, dict)
        and bool(str(item.get("candidate") or "").strip())
        and str(item.get("status") or "") != "ready"
        for item in assets
    )


def _validate_autopilot_project(project: Path, runtime: str) -> None:
    if not project.is_dir() or not (project / "project.yaml").is_file():
        raise ValueError("自动创作需要先选择一个包含 project.yaml 的有效作品目录。")
    if not str(runtime or "").strip():
        raise ValueError("自动创作需要一个可用的 Agent Runtime。")


def _project_progress_fingerprint(project: Path) -> str:
    """Hash formal project evidence without reading manuscript bodies into memory."""

    entries: list[str] = []
    for relative in PROGRESS_ROOTS:
        root = project / relative
        candidates = [root] if root.is_file() else sorted(root.rglob("*")) if root.is_dir() else []
        for path in candidates:
            if not path.is_file():
                continue
            rel = path.relative_to(project)
            if any(part.lower() in PROGRESS_EXCLUDED_PARTS for part in rel.parts):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append(f"{rel.as_posix()}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def _operational_decision(run: dict[str, Any], route: str, task_id: str, decision_type: str, selected: str, rationale: str) -> dict[str, Any]:
    return {
        "project_root": run["project_root"],
        "principal_type": "delegated-agent",
        "principal_id": "autopilot-controller",
        "delegation_id": run["run_id"],
        "policy_version": run["policy"].get("version", "0.1"),
        "route": route,
        "task_id": task_id,
        "decision_type": decision_type,
        "selected_option": selected,
        "rationale": rationale,
        "evidence": [],
        "alternatives": [],
        "confidence": 1.0,
    }


def _project_direction(project: Path) -> str:
    values = read_directions(project, limit=12)
    if not isinstance(values, list):
        return ""
    messages = []
    for item in values:
        if not isinstance(item, dict) or not item.get("message"):
            continue
        message = str(item.get("message") or "")
        actor = str(item.get("actor") or "")
        if message.lstrip().startswith("创作代理已在授权范围内决定："):
            continue
        if actor == "delegated-agent:creative-steward" and "修订方向" in message:
            continue
        messages.append(message)
    return "\n".join(messages)[-6000:]


def _choice_fingerprint(choice: dict[str, Any]) -> str:
    target = choice.get("target") if isinstance(choice.get("target"), dict) else {}
    options = choice.get("options") if isinstance(choice.get("options"), list) else []
    payload = {
        "route": str(choice.get("route") or ""),
        "decision_type": str(choice.get("decision_type") or ""),
        "target": {str(key): str(value) for key, value in sorted(target.items())},
        "options": [str(item.get("id") or "") for item in options if isinstance(item, dict)],
        "source_paths": [str(item) for item in choice.get("source_paths") or []],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _delegated_direction_message(choice: dict[str, Any], decision: dict[str, Any]) -> str:
    options = choice.get("options") if isinstance(choice.get("options"), list) else []
    selected = str(decision.get("selected_option") or "")
    option = next((item for item in options if isinstance(item, dict) and str(item.get("id") or "") == selected), {})
    label = str(option.get("label") or selected)
    rationale = str(decision.get("rationale") or "").strip()
    title = str(choice.get("title") or "当前创作节点")
    return f"创作代理已在授权范围内决定：{title}选择‘{label}’。执行后续任务时必须落实该方向。理由：{rationale}"


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
