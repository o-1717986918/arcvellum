"""Bounded Project Agent views over the existing cached project projections."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from .contracts import ProjectAgentDependencies
from .scope import registered_work_rows, work_id_for_root, work_reference
from .story_brief import build_story_brief


def dependencies_from_read_models(
    read_models: Any,
    *,
    choices: Any | None = None,
    quality: Any | None = None,
    rhythm: Any | None = None,
    style_mounts: Any | None = None,
    archive_candidates: Any | None = None,
    project_catalog: Any | None = None,
) -> ProjectAgentDependencies:
    def catalog(_root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if project_catalog is None:
            raise RuntimeError("Project Agent work catalog is unavailable")
        payload = project_catalog()
        rows = registered_work_rows(payload)
        query = str(arguments.get("query") or "").strip().casefold()
        items = [work_reference(item) for item in rows]
        if query:
            items = [
                item for item in items
                if query in " ".join(str(item.get(key) or "") for key in ("title", "genre", "premise")).casefold()
            ]
        current = str(payload.get("current_project") or "").strip()
        return _fit_payload({
            "count": len(items),
            "current_work_id": work_id_for_root(current) if current else "",
            "works": items[:50],
        })

    def resolve(anchor: Path, arguments: Mapping[str, Any]) -> Path:
        requested = str(arguments.get("work_id") or "").strip()
        if project_catalog is None:
            return anchor
        payload = project_catalog()
        rows = registered_work_rows(payload)
        by_id = {
            work_id_for_root(str(item.get("path") or "")): Path(str(item.get("path") or "")).expanduser().resolve()
            for item in rows
            if str(item.get("path") or "").strip()
        }
        if requested:
            if requested not in by_id:
                raise ValueError("unknown or unregistered Project Agent work_id")
            return by_id[requested]
        resolved_anchor = anchor.expanduser().resolve()
        if (resolved_anchor / "project.yaml").is_file() and work_id_for_root(resolved_anchor) in by_id:
            return resolved_anchor
        raise ValueError("Project Agent needs a work_id because this conversation is not bound to a registered work")

    def overview(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        dashboard = read_models.dashboard(root)
        library = read_models.library(root)
        reader = read_models.reader(root)
        return _fit_payload({
            "work_id": work_id_for_root(root),
            "focus": str(arguments.get("focus") or ""),
            "summary": dashboard.get("summary", {}),
            "story_brief": build_story_brief(library, reader),
            "next_actions": _items(dashboard.get("next_actions"), 12),
            "route_audits": _items(dashboard.get("route_audits"), 12),
            "progress": read_models.progress(root),
        })

    def search(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("project_search requires a query")
        limit = _limit(arguments.get("limit"), fallback=12, maximum=30)
        sources = {
            "library": read_models.library(root),
            "reader": read_models.reader(root),
        }
        hits: list[dict[str, str]] = []
        for source, payload in sources.items():
            _search_value(payload, query.casefold(), source, source, hits, limit)
            if len(hits) >= limit:
                break
        return _fit_payload({"query": query, "count": len(hits), "hits": hits})

    def observe(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace = read_models.workspace(root)
        status = workspace.get("autopilot_status")
        observability = workspace.get("agent_observability")
        dashboard = workspace.get("dashboard")
        return _fit_payload({
            "focus": str(arguments.get("focus") or ""),
            "autopilot": _mapping(status),
            "agents": _mapping(observability),
            "recent_events": _items(_mapping(dashboard).get("recent_events"), 24),
        })

    def controls(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        section = str(arguments.get("section") or "all").strip().lower()
        allowed = {"all", "decisions", "quality", "rhythm", "style", "archive", "delivery"}
        if section not in allowed:
            raise ValueError(f"unsupported project control section: {section}")
        payload: dict[str, Any] = {"section": section}
        if section in {"all", "decisions"} and choices is not None:
            payload["decisions"] = choices(root)
        if section in {"all", "quality"} and quality is not None:
            payload["quality"] = quality(root)
        if section in {"all", "rhythm"} and rhythm is not None:
            payload["rhythm"] = rhythm(root)
        if section in {"all", "style"} and style_mounts is not None:
            payload["style"] = style_mounts(root)
        if section in {"all", "archive"} and archive_candidates is not None:
            payload["archive"] = {"candidates": list(archive_candidates(root))[:50]}
        if section in {"all", "delivery"}:
            payload["delivery"] = read_models.delivery(root)
        return _fit_payload(payload)

    def diagnose(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace = read_models.workspace(root)
        dashboard = _mapping(workspace.get("dashboard")) or read_models.dashboard(root)
        autopilot = _mapping(workspace.get("autopilot_status"))
        run = _mapping(autopilot.get("run"))
        agent_status = _mapping(workspace.get("agent_observability"))
        decision_payload = choices(root) if choices is not None else {}
        decisions = _items(_mapping(decision_payload).get("choices"), 12)
        classification, recoverable, recommendation = _diagnosis(run, decisions, agent_status)
        return _fit_payload({
            "work_id": work_id_for_root(root),
            "focus": str(arguments.get("focus") or ""),
            "classification": classification,
            "recoverable": recoverable,
            "recommended_tool": recommendation,
            "run": run,
            "pending_decisions": decisions,
            "next_actions": _items(dashboard.get("next_actions"), 12),
            "route_audits": _items(dashboard.get("route_audits"), 12),
            "agents": agent_status,
        })

    return ProjectAgentDependencies(
        overview,
        search,
        observe,
        controls,
        catalog if project_catalog is not None else None,
        diagnose,
        resolve if project_catalog is not None else None,
    )


def _diagnosis(
    run: Mapping[str, Any],
    decisions: list[Any],
    agents: Mapping[str, Any],
) -> tuple[str, bool, str]:
    if decisions:
        return "decision_required", False, "project_decision_resolve"
    status = str(run.get("status") or "").strip().lower()
    if status == "running":
        if str(agents.get("status") or "").strip().lower() == "stalled":
            return "stalled", True, "project_goal_manage"
        return "running", False, "creation_observe"
    if status == "complete":
        return "complete", False, "project_controls"
    if status in {"paused", "blocked", "runtime_failed", "cancelled", "stopped"}:
        return "recoverable_stop", True, "project_goal_manage"
    return "not_started", True, "project_goal_manage"


def _search_value(
    value: Any,
    query: str,
    source: str,
    path: str,
    hits: list[dict[str, str]],
    limit: int,
) -> None:
    if len(hits) >= limit:
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _search_value(item, query, source, f"{path}.{key}", hits, limit)
            if len(hits) >= limit:
                return
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _search_value(item, query, source, f"{path}[{index}]", hits, limit)
            if len(hits) >= limit:
                return
    elif isinstance(value, str) and query in value.casefold():
        hits.append({"source": source, "path": path, "text": value[:800]})


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _items(value: Any, limit: int) -> list[Any]:
    return list(value[:limit]) if isinstance(value, list) else []


def _limit(value: Any, *, fallback: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(1, min(maximum, parsed))


def _fit_payload(value: dict[str, Any], *, byte_limit: int = 56 * 1024) -> dict[str, Any]:
    serialized = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(serialized.encode("utf-8")) <= byte_limit:
        return value
    preview = serialized.encode("utf-8")[: byte_limit - 2048].decode("utf-8", errors="ignore")
    return {
        "truncated": True,
        "available_keys": list(value)[:40],
        "preview": preview,
        "message": "结果已按 Project Agent 工具预算截断；请缩小查询范围。",
    }


__all__ = ["dependencies_from_read_models"]
