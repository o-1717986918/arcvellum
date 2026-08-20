"""Pure aggregation rules shared by dashboard queries and materialization."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


WORKFLOW_DASHBOARD_SCHEMA = "literary-engineering-workbench/workflow-dashboard/v0.1"


def build_dashboard_payload(
    root: Path,
    state_payload: dict[str, object],
    task_payload: dict[str, object],
    route_audits: list[dict[str, object]],
    events: list[dict[str, object]],
    *,
    route_state_path: str,
    task_status_path: str,
    frontend_html: str,
    frontend_json: str,
    frontend_mode: str,
) -> dict[str, object]:
    actions = next_actions(state_payload, route_audits)
    summary = dashboard_summary(state_payload, task_payload, route_audits, actions)
    return {
        "schema": WORKFLOW_DASHBOARD_SCHEMA,
        "generated_at": now(),
        "project_root": str(root),
        "summary": summary,
        "authority_hierarchy": authority_hierarchy(),
        "route_state": {"path": route_state_path, "summary": state_payload.get("summary", {})},
        "agent_task_status": {"path": task_status_path, "summary": task_payload.get("summary", {})},
        "route_audits": [route_audit_summary(root, audit) for audit in route_audits],
        "next_actions": actions,
        "recent_events": events[-25:],
        "frontend": {"html": frontend_html, "json": frontend_json, "mode": frontend_mode},
        "rules": [
            "This dashboard is read-only and must not be used to bypass task-next/task-open/task-submit/task-complete.",
            "The platform agent still performs creative and review judgment; this dashboard only aggregates formal route evidence.",
            "When a row is blocked, the blocking message is the next repair task.",
            "workflow-state is a navigation summary; route-audit is the formal pass/fail ledger.",
        ],
    }


def dashboard_summary(
    state_payload: dict[str, object],
    task_payload: dict[str, object],
    route_audits: list[dict[str, object]],
    next_actions: list[dict[str, object]],
) -> dict[str, object]:
    state_summary = state_payload.get("summary") if isinstance(state_payload.get("summary"), dict) else {}
    task_summary = task_payload.get("summary") if isinstance(task_payload.get("summary"), dict) else {}
    return {
        "route_count": len(route_audits),
        "ready_count": int(state_summary.get("ready_count") or 0),
        "state_blocked_count": int(state_summary.get("blocked_count") or 0),
        "next_action_count": len(next_actions),
        "sidecar_task_count": int(task_summary.get("task_count") or 0),
        "pending_task_count": int(task_summary.get("pending_count") or 0)
        + int(task_summary.get("partial_count") or 0)
        + int(task_summary.get("unknown_count") or 0),
        "missing_expected_count": int(task_summary.get("missing_expected_count") or 0),
        "blocking_count": sum(audit_int(audit, "blocking_count") for audit in route_audits),
        "warning_count": sum(audit_int(audit, "warning_count") for audit in route_audits),
    }


def route_audit_summary(root: Path, payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []
    route = str(summary.get("route") or "")
    blockers = [_blocking_gate(gate) for gate in gates if _is_blocking_gate(gate)]
    return {
        "route": route,
        "path": relative_path(root / "workflow" / "dashboard" / f"route_audit.{route or 'overall'}.json", root),
        "gate_count": int(summary.get("gate_count") or 0),
        "blocking_count": int(summary.get("blocking_count") or 0),
        "warning_count": int(summary.get("warning_count") or 0),
        "pending_task_count": int(summary.get("pending_task_count") or 0),
        "top_blocking_gates": blockers[:5],
    }


def _is_blocking_gate(gate: object) -> bool:
    return isinstance(gate, dict) and gate.get("severity") == "blocking" and gate.get("status") != "pass"


def _blocking_gate(gate: object) -> dict[str, str]:
    assert isinstance(gate, dict)
    return {"key": str(gate.get("key") or ""), "message": str(gate.get("message") or "")}


def next_actions(
    state_payload: dict[str, object],
    route_audits: list[dict[str, object]],
) -> list[dict[str, object]]:
    actions = _state_actions(state_payload)
    actions.extend(_longform_actions(state_payload))
    actions.extend(_audit_actions(route_audits))
    return _dedupe_actions(actions)[:50]


def _state_actions(state_payload: dict[str, object]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    routes = (
        ("scene-development", state_payload.get("scenes")),
        ("source-ingest", state_payload.get("source_ingests")),
        ("style-engineering", state_payload.get("styles")),
        ("character-and-world-assets", state_payload.get("assets")),
        ("review-and-audit", state_payload.get("audits")),
        ("export-and-release", state_payload.get("exports")),
    )
    for route, items in routes:
        if isinstance(items, list):
            actions.extend(_state_item_actions(route, items))
    return actions


def _state_item_actions(route: str, items: list[object]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        action = str(item.get("next_action") or "").strip()
        if action:
            actions.append(
                {
                    "route": route,
                    "target": _state_target(item),
                    "current_step": str(item.get("current_step") or ""),
                    "next_action": action,
                }
            )
    return actions


def _state_target(item: dict[str, object]) -> str:
    for key in ("scene_id", "target_id", "work_id", "candidate_id", "chapter_id"):
        value = str(item.get(key) or "")
        if value:
            return value
    return ""


def _longform_actions(state_payload: dict[str, object]) -> list[dict[str, object]]:
    longform = state_payload.get("longform") if isinstance(state_payload.get("longform"), dict) else {}
    if not longform.get("next_action"):
        return []
    return [
        {
            "route": "longform-planning",
            "target": "longform",
            "current_step": str(longform.get("current_step") or ""),
            "next_action": str(longform.get("next_action") or ""),
        }
    ]


def _audit_actions(route_audits: list[dict[str, object]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for audit in route_audits:
        summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
        route = str(summary.get("route") or "")
        gates = audit.get("gates") if isinstance(audit.get("gates"), list) else []
        for gate in gates:
            if _is_blocking_gate(gate):
                assert isinstance(gate, dict)
                actions.append(
                    {
                        "route": route,
                        "target": str(gate.get("key") or ""),
                        "current_step": "route-audit",
                        "next_action": str(gate.get("message") or ""),
                    }
                )
    return actions


def _dedupe_actions(actions: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for action in actions:
        key = (action["route"], action["target"], action["current_step"], action["next_action"])
        if key not in seen:
            seen.add(key)
            deduped.append(action)
    return deduped


def read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {
                "schema": "literary-engineering-workbench/workflow-event/v1",
                "event_type": "invalid",
                "task_id": "",
                "created_at": "",
                "data": {"raw": line},
            }
        if isinstance(payload, dict):
            events.append(payload)
    return events


def audit_int(payload: dict[str, object], key: str) -> int:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return int(summary.get(key) or 0)


def authority_hierarchy() -> list[dict[str, str]]:
    return [
        {"level": "task-next", "meaning": "唯一推荐入口：选择当前 route 的下一项正式任务。"},
        {"level": "task-open", "meaning": "执行包入口：平台 Agent 读取此包和 source artifacts 后再动手。"},
        {"level": "task-submit / task-complete", "meaning": "产物落地与完成标记，未完成不得前进。"},
        {"level": "route-audit", "meaning": "正式门禁证据：判断 route 是否真的通过。"},
        {"level": "workflow-dashboard", "meaning": "只读驾驶舱：方便观察，不推进状态。"},
        {"level": "workflow-state", "meaning": "导航摘要：提示当前步骤，不替代 route-audit。"},
        {"level": "low-level commands", "meaning": "内部执行命令：除 task package 指定外，不应由宿主 Agent 自行挑选。"},
    ]


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
