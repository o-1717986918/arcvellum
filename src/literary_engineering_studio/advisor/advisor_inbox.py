"""Deterministic, deduplicated proactive advisor notices."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
import re
from typing import Any

from ..projections.core_read_models import build_dashboard, current_choices
from ..jobs import JobStore
from ..projections.reader import build_reader_manifest
from ..application.failures import failure_identity, present_failure


INBOX_SCHEMA = "arcvellum/advisor-inbox/v1"
MODES = {"off", "blocking", "standard", "active"}


def refresh_advisor_inbox(
    config: dict[str, Any],
    store: JobStore,
    project_root: Path,
    *,
    dashboard_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    settings = inbox_settings(_data_root(config), root)
    mode = str(settings.get("mode") or "standard")
    if mode == "off":
        return inbox_snapshot(store, root, settings=settings)
    _refresh_choice_notices(config, store, root, dashboard_payload)
    dashboard = _inbox_dashboard(config, root, dashboard_payload)
    _refresh_route_notices(store, root, dashboard, mode)
    _refresh_autopilot_notice(store, root)
    if mode in {"standard", "active"}:
        _refresh_reader_notice(store, root)
    return inbox_snapshot(store, root, settings=settings)


def _refresh_choice_notices(
    config: dict[str, Any],
    store: JobStore,
    root: Path,
    dashboard_payload: dict[str, Any] | None,
) -> None:
    try:
        choices = current_choices(config, root, dashboard=dashboard_payload)
    except Exception:
        choices = {"items": []}
    choice_items = choices.get("items") or choices.get("choices") or []
    for item in choice_items[:8] if isinstance(choice_items, list) else []:
        if not isinstance(item, dict):
            continue
        choice_id = str(item.get("choice_id") or item.get("id") or _digest(item))
        store.upsert_advisor_inbox(
            str(root),
            dedupe_key=f"choice:{choice_id}",
            kind="human_choice",
            severity="decision",
            title=str(item.get("title") or "一个创作方向需要你决定"),
            message=str(item.get("summary") or item.get("description") or "作品已经走到需要你选择方向的节点。"),
            action={"type": "open_view", "target": "overview", "label": "查看选择"},
        )


def _inbox_dashboard(
    config: dict[str, Any],
    root: Path,
    dashboard_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        return dashboard_payload if isinstance(dashboard_payload, dict) else build_dashboard(config, root)
    except Exception:
        return {"route_audits": []}


def _refresh_route_notices(
    store: JobStore,
    root: Path,
    dashboard: dict[str, Any],
    mode: str,
) -> None:
    audits = dashboard.get("route_audits") if isinstance(dashboard.get("route_audits"), list) else []
    blocked = [item for item in audits if isinstance(item, dict) and int(item.get("blocking_count") or 0) > 0]
    for audit in blocked[:2]:
        _upsert_blocking_notice(store, root, audit)

    if mode == "active":
        next_actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
        next_action = next((item for item in next_actions if isinstance(item, dict)), None)
        if next_action:
            route = str(next_action.get("route") or "auto")
            target = str(next_action.get("target") or "")
            action_text = _friendly_action(str(next_action.get("next_action") or "下一项创作工作已经可以开始。"))
            store.upsert_advisor_inbox(
                str(root),
                dedupe_key=f"next-action:{route}:{target}:{_digest(action_text)}",
                kind="next_action_ready",
                severity="notice",
                title="下一步已经准备好",
                message=action_text,
                action={"type": "open_view", "target": "overview", "label": "查看下一步"},
            )


def _refresh_autopilot_notice(store: JobStore, root: Path) -> None:
    run = store.latest_autopilot_run(str(root))
    if run and str(run.get("status") or "") in {"paused", "blocked", "failed"}:
        _upsert_autopilot_notice(store, root, run)


def _refresh_reader_notice(store: JobStore, root: Path) -> None:
    try:
        manifest = build_reader_manifest(root)
    except Exception:
        manifest = {"units": []}
    units = manifest.get("units") if isinstance(manifest.get("units"), list) else []
    if not units:
        return
    newest = units[-1]
    store.upsert_advisor_inbox(
        str(root),
        dedupe_key=f"reader:{newest.get('unit_id')}:{newest.get('content_hash')}",
        kind="prose_promoted",
        severity="success",
        title="新正文已经进入阅读长卷",
        message=f"《{newest.get('title') or '最新一节'}》已经通过正式门禁，可以边读边继续创作。",
        action={"type": "open_view", "target": "reader", "label": "开始阅读"},
    )


def inbox_snapshot(
    store: JobStore,
    project_root: Path,
    *,
    settings: dict[str, Any] | None = None,
    limit: int = 80,
) -> dict[str, Any]:
    stored_items = store.advisor_inbox(str(project_root.resolve()), limit=limit)
    normalized_items = [
        {**item, "message": _friendly_action(str(item.get("message") or ""))}
        for item in stored_items
    ]
    items = _dedupe_snapshot(normalized_items)
    active_settings = settings or {}
    quiet = _is_quiet(active_settings)
    unread = sum(1 for item in items if item.get("unread"))
    return {
        "ok": True,
        "schema": INBOX_SCHEMA,
        "project_root": str(project_root.resolve()),
        "settings": active_settings,
        "unread_count": unread,
        "notification_count": 0 if quiet else unread,
        "quiet_active": quiet,
        "items": items,
    }


def inbox_settings(data_root: Path, project_root: Path) -> dict[str, Any]:
    state = _load_settings(data_root)
    projects = state.get("projects") if isinstance(state.get("projects"), dict) else {}
    value = projects.get(str(project_root.resolve())) if isinstance(projects.get(str(project_root.resolve())), dict) else {}
    return {
        "mode": str(value.get("mode") or state.get("default_mode") or "standard"),
        "quiet_start": str(value.get("quiet_start") or "22:30"),
        "quiet_end": str(value.get("quiet_end") or "08:00"),
    }


def save_inbox_settings(data_root: Path, project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "standard")
    if mode not in MODES:
        raise ValueError("顾问提醒强度必须是 off、blocking、standard 或 active。")
    quiet_start = _time_value(str(payload.get("quiet_start") or "22:30"))
    quiet_end = _time_value(str(payload.get("quiet_end") or "08:00"))
    state = _load_settings(data_root)
    projects = state.setdefault("projects", {})
    projects[str(project_root.resolve())] = {"mode": mode, "quiet_start": quiet_start, "quiet_end": quiet_end}
    path = _settings_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["schema"] = "arcvellum/advisor-notification-settings/v1"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inbox_settings(data_root, project_root)


def _data_root(config: dict[str, Any]) -> Path:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    return Path(str(application.get("data_root") or Path.home() / ".literary-engineering-studio")).expanduser().resolve()


def _settings_path(data_root: Path) -> Path:
    return data_root.expanduser().resolve() / "advisor" / "notifications.json"


def _load_settings(data_root: Path) -> dict[str, Any]:
    path = _settings_path(data_root)
    if not path.is_file():
        return {"default_mode": "standard", "projects": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"default_mode": "standard", "projects": {}}
    return value if isinstance(value, dict) else {"default_mode": "standard", "projects": {}}


def _time_value(value: str) -> str:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("免打扰时间必须使用 HH:MM。")
    return value


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _friendly_action(value: str) -> str:
    lowered = value.lower()
    labels = (
        ("chapter-workspace", "汇总本章场景，确认章节正文与字数完成度。"),
        ("asset-create", "先准备人物或世界设定候选，再完成正式审查。"),
        ("agent-create", "先准备人物或世界设定候选，再完成正式审查。"),
        ("word-budget", "先完成全书到场景的字数预算。"),
        ("longform-audit", "检查全书字数、情节库存与兑现进度。"),
        ("route-audit", "这条创作路线还有必要步骤没有完成。"),
        ("context", "整理下一场所需的人物、设定和前情。"),
        ("simulate-scene", "下一场已经可以进入角色推演。"),
        ("branch-simulate", "下一场已经可以比较剧情分支。"),
        ("compose-scene", "下一场已经可以形成写作方案。"),
        ("generate-scene", "下一场已经可以进入正文创作。"),
        ("agent-review-scene", "新正文已经可以进入正式审读。"),
        ("promote", "通过审查的正文正在等待进入正式长卷。"),
        ("state-evolve", "场景后果已经可以写回人物状态。"),
    )
    for token, label in labels:
        if token in lowered:
            return label
    if "--" in value or lowered.startswith("lew ") or lowered.startswith("run ") or ".agent_tasks" in lowered:
        return "下一项创作工作已经准备好。"
    return value


def _upsert_blocking_notice(store: JobStore, root: Path, audit: dict[str, Any]) -> None:
    gates = audit.get("top_blocking_gates") if isinstance(audit.get("top_blocking_gates"), list) else []
    gate = gates[0] if gates and isinstance(gates[0], dict) else {}
    raw_message = str(gate.get("message") or "这条创作路线还有必要步骤没有完成。")
    route = str(audit.get("route") or "auto")
    gate_id = str(
        gate.get("gate_id")
        or gate.get("gate")
        or gate.get("id")
        or failure_identity(raw_message, route=route)
    )
    store.upsert_advisor_inbox(
        str(root),
        dedupe_key=f"blocking:{route}:{gate_id}",
        kind="workflow_blocked",
        severity="blocking",
        title="创作流程在等待补齐",
        message=_friendly_action(raw_message),
        action={"type": "open_view", "target": "overview", "label": "查看阻塞"},
    )


def _upsert_autopilot_notice(store: JobStore, root: Path, run: dict[str, Any]) -> None:
    run_id = str(run.get("run_id") or "")
    status = str(run.get("status") or "")
    reason = str(run.get("stop_reason") or run.get("last_error") or "连续创作已经停下，正在等你确认下一步。")
    failure = present_failure(
        str(run.get("last_error") or reason),
        stop_reason=str(run.get("stop_reason") or ""),
        status=status,
    )
    store.upsert_advisor_inbox(
        str(root),
        dedupe_key=f"autopilot:{run_id}:{failure.code if failure else status}",
        kind="autopilot",
        severity="blocking" if status in {"blocked", "failed"} else "notice",
        title=(failure.title if failure else "连续创作已暂停" if status == "paused" else "连续创作需要处理"),
        message=(failure.summary if failure else _friendly_action(reason)),
        action={"type": "open_view", "target": "overview", "label": "查看进度"},
    )


def _dedupe_snapshot(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hide historical duplicates created by pre-v0.99 wording-based keys."""

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("dedupe_key") or item.get("item_id") or "")
        parts = key.split(":")
        if item.get("kind") == "workflow_blocked" and len(parts) >= 2:
            identity = f"workflow_blocked:{parts[1]}"
        elif item.get("kind") == "autopilot" and len(parts) >= 2:
            identity = f"autopilot:{parts[1]}"
        else:
            identity = key
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(item)
    return deduped


def _is_quiet(settings: dict[str, Any]) -> bool:
    if not settings:
        return False
    now = datetime.now().strftime("%H:%M")
    start = str(settings.get("quiet_start") or "22:30")
    end = str(settings.get("quiet_end") or "08:00")
    return start <= now < end if start < end else now >= start or now < end
