"""Bounded Project Agent views over the existing cached project projections."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from .contracts import ProjectAgentDependencies


def dependencies_from_read_models(read_models: Any) -> ProjectAgentDependencies:
    def overview(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        dashboard = read_models.dashboard(root)
        return _fit_payload({
            "project_root": str(root),
            "focus": str(arguments.get("focus") or ""),
            "summary": dashboard.get("summary", {}),
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

    return ProjectAgentDependencies(overview, search, observe)


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
