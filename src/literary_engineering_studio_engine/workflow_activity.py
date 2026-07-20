"""Frontend read model for visible platform-agent task activity."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .project_interaction import build_current_human_choices
from .task_registry import SUPPORTED_ROUTES
from .workflow_dashboard import build_workflow_dashboard


WORKFLOW_ACTIVITY_SCHEMA = "literary-engineering-workbench/workflow-activity/v0.1"
TASK_PACKAGE_SCHEMA = "literary-engineering-workbench/task-package-summary/v0.1"

ROUTE_ORDER = [
    "scene-development",
    "longform-planning",
    "style-engineering",
    "character-and-world-assets",
    "review-and-audit",
    "export-and-release",
    "source-ingest",
]

ROUTE_LABELS = {
    "scene-development": "场景开发",
    "longform-planning": "长篇规划",
    "source-ingest": "旧文导入",
    "style-engineering": "文风工程",
    "character-and-world-assets": "人物与世界资产",
    "review-and-audit": "审查与审计",
    "export-and-release": "导出与发布",
}

STAGE_LABELS = {
    "blocked": "被门禁拦下",
    "waiting_user": "等待你决定",
    "waiting_agent": "等待平台 Agent 执行",
    "waiting_gate": "等待 CLI 验收",
    "issued": "任务已派发",
    "completed": "最近任务已完成",
    "next_action": "建议下一步",
    "ready": "等待下一轮方向",
}

EVENT_LABELS = {
    "task_issued": "状态机发出了一个新任务",
    "task_opened": "平台 Agent 打开了任务包",
    "task_submitted": "平台 Agent 提交了产物",
    "task_completed": "CLI 验收通过",
    "task_blocked": "CLI 拦下了这一步",
    "workflow_state_refreshed": "状态机刷新了路线状态",
    "workflow_advanced": "工作流状态已刷新",
}


def build_workflow_activity(project_root: Path, *, limit: int = 30) -> dict[str, object]:
    """Build a read-only activity cockpit from formal workflow evidence."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    dashboard_result = build_workflow_dashboard(root)
    dashboard = _read_json(dashboard_result.json_path)
    events = _read_events(root / "workflow" / "events" / "task_events.jsonl")
    tasks = _load_tasks(root)
    choices_payload = _safe_current_choices(root)
    choices = choices_payload.get("choices") if isinstance(choices_payload.get("choices"), list) else []
    active_task = _select_active_task(root, dashboard, tasks, events, choices)
    timeline = [_timeline_entry(root, event, tasks) for event in events[-max(1, limit) :]]
    route_lanes = _route_lanes(dashboard, active_task, tasks, choices)
    return {
        "schema": WORKFLOW_ACTIVITY_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "summary": {
            "active_stage": active_task.get("stage", "ready"),
            "active_route": active_task.get("route", ""),
            "waiting_for": active_task.get("waiting_for", "none"),
            "route_count": len(route_lanes),
            "waiting_choice_count": len(choices),
            "timeline_count": len(timeline),
        },
        "active_task": active_task,
        "route_lanes": route_lanes,
        "timeline": timeline,
        "waiting_choices": choices[:20],
        "dashboard": _rel(dashboard_result.json_path, root),
        "rules": [
            "This activity cockpit is read-only and must not be used as task completion proof.",
            "Only task-complete or route-audit pass can prove formal completion.",
            "Frontend highlights are derived from CLI task events, task files, human choices, and route gates.",
        ],
    }


def build_task_package_summary(project_root: Path, task_id: str) -> dict[str, object]:
    """Return a frontend-friendly task package summary."""

    root = project_root.resolve()
    task_id = _safe_task_id(task_id)
    task_path = root / "workflow" / "tasks" / f"{task_id}.task.json"
    if not task_path.exists():
        raise FileNotFoundError(f"task package not found: {task_id}")
    task = _read_json(task_path)
    markdown_path = root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md"
    markdown = markdown_path.read_text(encoding="utf-8", errors="ignore") if markdown_path.exists() else ""
    return {
        "schema": TASK_PACKAGE_SCHEMA,
        "project_root": str(root),
        "task_id": task_id,
        "task": _task_summary(root, task, task_path),
        "sections": {
            "purpose": _task_purpose(task),
            "required_reading": [str(item) for item in task.get("required_reading") or []],
            "source_paths": [str(item) for item in task.get("source_paths") or []],
            "expected_outputs": [str(item) for item in task.get("expected_outputs") or []],
            "hard_constraints": [str(item) for item in task.get("hard_constraints") or []],
            "validation_gates": [str(item) for item in task.get("validation_gates") or []],
            "forbidden_shortcuts": [str(item) for item in task.get("forbidden_shortcuts") or []],
            "command": str(task.get("command") or ""),
            "submission_command": str(task.get("submission_command") or ""),
            "completion_command": str(task.get("completion_command") or ""),
        },
        "raw_evidence": {
            "task_json": _rel(task_path, root),
            "task_markdown": _rel(markdown_path, root) if markdown_path.exists() else "",
            "markdown_excerpt": markdown[:6000],
        },
        "rules": [
            "Read this package as the current executable task instruction.",
            "Writing files manually is not enough; task-submit and task-complete must still succeed.",
        ],
    }


def _select_active_task(
    root: Path,
    dashboard: dict[str, object],
    tasks: dict[str, dict[str, object]],
    events: list[dict[str, object]],
    choices: list[object],
) -> dict[str, object]:
    candidates: list[tuple[int, str, dict[str, object]]] = []
    last_events = _last_event_by_task(events)
    for task_id, task in tasks.items():
        candidate = _active_from_task(root, task_id, task, last_events.get(task_id))
        candidates.append((_stage_priority(str(candidate.get("stage") or "")), str(candidate.get("last_event_at") or ""), candidate))
    for choice in choices:
        if isinstance(choice, dict):
            candidate = _active_from_choice(choice)
            candidates.append((_stage_priority("waiting_user"), str(candidate.get("last_event_at") or ""), candidate))
    for action in _dashboard_actions(dashboard):
        candidate = _active_from_action(action)
        stage = str(candidate.get("stage") or "next_action")
        candidates.append((_stage_priority(stage), str(candidate.get("last_event_at") or ""), candidate))
    if not candidates:
        return _ready_task()
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    active = candidates[0][2]
    if active.get("task_id") and active.get("task_path"):
        active["package_summary"] = _package_hint(root, str(active["task_id"]))
    return active


def _active_from_task(root: Path, task_id: str, task: dict[str, object], last_event: dict[str, object] | None) -> dict[str, object]:
    status = str(task.get("status") or "issued")
    event_type = str(last_event.get("event_type") or "") if last_event else ""
    if event_type == "task_blocked" or status == "blocked":
        stage = "blocked"
        waiting_for = "gate"
        risk = "blocking"
    elif status == "opened":
        stage = "waiting_agent"
        waiting_for = "agent"
        risk = "stale" if _is_stale(str(task.get("opened_at") or ""), 1800) else "normal"
    elif status == "submitted":
        stage = "waiting_gate"
        waiting_for = "gate"
        risk = "stale" if _is_stale(_submitted_at(root, task_id), 900) else "normal"
    elif status == "complete" or event_type == "task_completed":
        stage = "completed"
        waiting_for = "none"
        risk = "done"
    else:
        stage = "issued"
        waiting_for = "agent"
        risk = "normal"
    current_state = str(task.get("current_state") or "")
    route = str(task.get("route") or "")
    scene_id = str(task.get("scene_id") or "")
    task_path = root / "workflow" / "tasks" / f"{task_id}.task.json"
    markdown_path = root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md"
    return {
        "task_id": task_id,
        "route": route,
        "route_label": _route_label(route),
        "target": scene_id or str(task.get("target_id") or ""),
        "current_step": current_state,
        "task_type": str(task.get("task_type") or ""),
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "waiting_for": waiting_for,
        "risk": risk,
        "headline": _headline(route, scene_id, current_state, stage),
        "suggested_action": _task_suggestion(stage, task, last_event),
        "last_event": event_type or status,
        "last_event_at": str(last_event.get("created_at") or task.get("opened_at") or "") if last_event else str(task.get("opened_at") or ""),
        "elapsed_seconds": _elapsed_seconds(str(last_event.get("created_at") or task.get("opened_at") or "") if last_event else str(task.get("opened_at") or "")),
        "task_path": _rel(task_path, root),
        "task_markdown": _rel(markdown_path, root) if markdown_path.exists() else "",
        "expected_outputs": [str(item) for item in task.get("expected_outputs") or []],
        "source_paths": [str(item) for item in task.get("source_paths") or []],
        "progress_steps": _progress_steps(route, current_state, stage),
    }


def _active_from_choice(choice: dict[str, object]) -> dict[str, object]:
    target = choice.get("target") if isinstance(choice.get("target"), dict) else {}
    target_id = str(target.get("scene_id") or target.get("target_id") or "")
    route = str(choice.get("route") or "")
    return {
        "task_id": str(choice.get("task_id") or ""),
        "choice_id": str(choice.get("choice_id") or ""),
        "route": route,
        "route_label": _route_label(route),
        "target": target_id,
        "current_step": str(choice.get("task_step") or choice.get("decision_type") or ""),
        "stage": "waiting_user",
        "stage_label": STAGE_LABELS["waiting_user"],
        "waiting_for": "user",
        "risk": "attention",
        "headline": str(choice.get("title") or "有一个节点等待你决定"),
        "suggested_action": str(choice.get("summary") or "请在前端记录你的选择，平台 Agent 后续会读取这条证据。"),
        "last_event": "human_choice_waiting",
        "last_event_at": "",
        "elapsed_seconds": 0,
        "expected_outputs": [],
        "source_paths": [str(item) for item in choice.get("source_paths") or []],
        "progress_steps": _progress_steps(route, str(choice.get("task_step") or ""), "waiting_user"),
    }


def _active_from_action(action: dict[str, object]) -> dict[str, object]:
    route = str(action.get("route") or "")
    current_step = str(action.get("current_step") or "")
    blocked = current_step == "route-audit" or "blocking" in str(action.get("next_action") or "").lower()
    stage = "next_action"
    return {
        "task_id": "",
        "route": route,
        "route_label": _route_label(route),
        "target": str(action.get("target") or ""),
        "current_step": current_step,
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "waiting_for": "gate" if blocked else "agent",
        "risk": "blocking" if blocked else "normal",
        "headline": _headline(route, str(action.get("target") or ""), current_step, stage),
        "suggested_action": str(action.get("next_action") or "按正式状态机继续领取下一项任务。"),
        "last_event": "dashboard_next_action",
        "last_event_at": "",
        "elapsed_seconds": 0,
        "expected_outputs": [],
        "source_paths": [],
        "progress_steps": _progress_steps(route, current_step, stage),
    }


def _route_lanes(
    dashboard: dict[str, object],
    active_task: dict[str, object],
    tasks: dict[str, dict[str, object]],
    choices: list[object],
) -> list[dict[str, object]]:
    audits = dashboard.get("route_audits") if isinstance(dashboard.get("route_audits"), list) else []
    audit_by_route = {str(item.get("route") or ""): item for item in audits if isinstance(item, dict)}
    choices_by_route: dict[str, int] = {}
    for choice in choices:
        if isinstance(choice, dict):
            route = str(choice.get("route") or "")
            choices_by_route[route] = choices_by_route.get(route, 0) + 1
    active_by_route = _latest_open_task_by_route(tasks)
    routes = [route for route in ROUTE_ORDER if route in SUPPORTED_ROUTES]
    lanes = []
    for route in routes:
        audit = audit_by_route.get(route, {})
        blocking = int(audit.get("blocking_count") or 0)
        warning = int(audit.get("warning_count") or 0)
        pending = int(audit.get("pending_task_count") or 0)
        choice_count = choices_by_route.get(route, 0)
        top_gate = None
        gates = audit.get("top_blocking_gates") if isinstance(audit.get("top_blocking_gates"), list) else []
        if gates and isinstance(gates[0], dict):
            top_gate = str(gates[0].get("message") or "")
        if blocking:
            status = "blocked"
            message = top_gate or "这条路线有硬门禁没有通过。"
        elif choice_count:
            status = "waiting_user"
            message = "这条路线有节点需要你选择或审批。"
        elif pending:
            status = "pending"
            message = "这条路线还有平台 Agent 任务未完成。"
        elif warning:
            status = "warning"
            message = "这条路线可以继续，但有提醒需要留意。"
        else:
            status = "ready"
            message = "这条路线暂时没有硬阻塞。"
        active_route = str(active_task.get("route") or "") == route
        latest_task = active_by_route.get(route, {})
        lanes.append(
            {
                "route": route,
                "label": _route_label(route),
                "status": status,
                "active": active_route,
                "message": message,
                "blocking_count": blocking,
                "warning_count": warning,
                "pending_task_count": pending,
                "waiting_choice_count": choice_count,
                "current_step": latest_task.get("current_state", ""),
                "latest_task_id": latest_task.get("task_id", ""),
                "target": latest_task.get("scene_id", ""),
            }
        )
    return lanes


def _timeline_entry(root: Path, event: dict[str, object], tasks: dict[str, dict[str, object]]) -> dict[str, object]:
    task_id = str(event.get("task_id") or "")
    task = tasks.get(task_id, {})
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    route = str(data.get("route") or task.get("route") or "")
    target = str(data.get("scene_id") or task.get("scene_id") or "")
    event_type = str(event.get("event_type") or "")
    return {
        "event_type": event_type,
        "label": EVENT_LABELS.get(event_type, "项目事件"),
        "task_id": task_id,
        "route": route,
        "route_label": _route_label(route),
        "target": target,
        "created_at": str(event.get("created_at") or ""),
        "summary": _event_summary(event_type, data, task),
        "artifact_paths": _event_artifacts(root, data),
    }


def _load_tasks(root: Path) -> dict[str, dict[str, object]]:
    task_dir = root / "workflow" / "tasks"
    if not task_dir.exists():
        return {}
    tasks: dict[str, dict[str, object]] = {}
    for path in sorted(task_dir.glob("*.task.json")):
        payload = _read_json(path)
        task_id = str(payload.get("task_id") or path.name.removesuffix(".task.json"))
        if not task_id:
            continue
        payload["_path"] = _rel(path, root)
        tasks[task_id] = payload
    return tasks


def _task_summary(root: Path, task: dict[str, object], task_path: Path) -> dict[str, object]:
    task_id = str(task.get("task_id") or task_path.name.removesuffix(".task.json"))
    route = str(task.get("route") or "")
    current_state = str(task.get("current_state") or "")
    scene_id = str(task.get("scene_id") or "")
    return {
        "task_id": task_id,
        "route": route,
        "route_label": _route_label(route),
        "target": scene_id,
        "current_step": current_state,
        "task_type": str(task.get("task_type") or ""),
        "status": str(task.get("status") or ""),
        "headline": _headline(route, scene_id, current_state, str(task.get("status") or "issued")),
        "prompt_asset_id": str(task.get("prompt_asset_id") or ""),
        "task_json": _rel(task_path, root),
        "task_markdown": _rel(root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md", root),
    }


def _package_hint(root: Path, task_id: str) -> dict[str, object]:
    try:
        return build_task_package_summary(root, task_id)["task"]
    except (FileNotFoundError, ValueError):
        return {}


def _dashboard_actions(dashboard: dict[str, object]) -> list[dict[str, object]]:
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    return [item for item in actions if isinstance(item, dict)]


def _last_event_by_task(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for event in events:
        task_id = str(event.get("task_id") or "")
        if task_id:
            latest[task_id] = event
    return latest


def _latest_open_task_by_route(tasks: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for task_id, task in tasks.items():
        route = str(task.get("route") or "")
        if not route:
            continue
        current = result.get(route)
        if current is None or str(task.get("opened_at") or task.get("task_id") or task_id) >= str(current.get("opened_at") or current.get("task_id") or ""):
            copy = dict(task)
            copy["task_id"] = task_id
            result[route] = copy
    return result


def _safe_current_choices(root: Path) -> dict[str, object]:
    try:
        return build_current_human_choices(root)
    except (RuntimeError, ValueError, FileNotFoundError):
        return {"choices": [], "recent_choices": []}


def _progress_steps(route: str, current_state: str, stage: str) -> list[dict[str, object]]:
    if route == "scene-development":
        steps = [
            ("context", "上下文"),
            ("roleplay", "角色推演"),
            ("branch", "分支"),
            ("composition", "编剧态"),
            ("generation", "正文"),
            ("review", "审查"),
            ("promotion", "晋升"),
            ("state", "状态/Canon"),
        ]
    else:
        steps = [
            ("task-next", "派发"),
            ("task-open", "打开"),
            ("agent", "执行"),
            ("task-submit", "提交"),
            ("task-complete", "验收"),
            ("route-audit", "审计"),
        ]
    index = _step_index(steps, current_state, stage)
    return [
        {
            "key": key,
            "label": label,
            "state": "done" if i < index else "active" if i == index else "todo",
        }
        for i, (key, label) in enumerate(steps)
    ]


def _step_index(steps: list[tuple[str, str]], current_state: str, stage: str) -> int:
    text = f"{current_state} {stage}".lower()
    for i, (key, _) in enumerate(steps):
        if key in text:
            return i
    if stage == "issued":
        return 0
    if stage == "waiting_agent":
        return min(2, len(steps) - 1)
    if stage == "waiting_gate":
        return max(0, len(steps) - 2)
    if stage == "completed":
        return len(steps) - 1
    return 0


def _task_suggestion(stage: str, task: dict[str, object], last_event: dict[str, object] | None) -> str:
    if stage == "blocked":
        data = last_event.get("data") if isinstance(last_event, dict) and isinstance(last_event.get("data"), dict) else {}
        return str(data.get("message") or "CLI 门禁拦截了这一步。请按阻塞信息修复后重新提交验收。")
    if stage == "waiting_agent":
        return "平台 Agent 应读取任务包和指定资料，完成预期产物后运行 task-submit。"
    if stage == "waiting_gate":
        return "产物已提交，下一步应运行 task-complete，让 CLI 做正式验收。"
    if stage == "issued":
        return "任务已经派发。下一步应运行 task-open，读取完整执行包。"
    if stage == "completed":
        return "最近任务已经完成。刷新 workflow-dashboard 或领取下一项任务。"
    return str(task.get("command") or "按正式状态机继续推进。")


def _task_purpose(task: dict[str, object]) -> str:
    route = str(task.get("route") or "")
    current_state = str(task.get("current_state") or "")
    target = str(task.get("scene_id") or task.get("target_id") or "")
    return _headline(route, target, current_state, str(task.get("status") or "issued"))


def _headline(route: str, target: str, current_state: str, stage: str) -> str:
    target_text = _friendly_target(target)
    step_text = _friendly_step(current_state)
    if stage == "blocked":
        return f"{_route_label(route)}卡在{step_text}"
    if stage == "waiting_user":
        return f"{target_text or _route_label(route)}等待你决定"
    if stage == "completed":
        return f"{target_text or _route_label(route)}最近完成了{step_text}"
    if step_text:
        return f"{target_text or _route_label(route)}正在推进{step_text}"
    return f"{_route_label(route)}等待下一步"


def _friendly_step(value: str) -> str:
    text = str(value or "").replace("-", " ").replace("_", " ").strip()
    mapping = {
        "context packet": "上下文包",
        "context trace": "上下文来源核验",
        "roleplay simulation": "角色推演",
        "roleplay agent task": "角色推演任务",
        "branch manifest": "分支清单",
        "branch simulation": "分支推演",
        "branch agent task": "分支研判任务",
        "branch selection": "分支选择",
        "composition": "编剧态",
        "composition json": "编剧态方案",
        "composition agent task": "编剧态任务",
        "scene word budget contract": "场景字数契约",
        "reader experience contract": "读者体验契约",
        "candidate generation provenance": "正文生成来源",
        "prose candidate": "正文候选",
        "generation agent task": "正文生成任务",
        "agent review": "正式审查",
        "agent review task": "正式审查任务",
        "candidate review": "正文审查",
        "promotion": "正文晋升",
        "promotion manifest": "晋升清单",
        "promoted draft": "正式草稿",
        "static review": "静态审查",
        "state evolve": "状态演化",
        "state patch json": "状态补丁",
        "state agent task": "人物状态演化任务",
        "canon writeback": "Canon 写回",
        "canon patch json": "Canon 补丁",
        "canon agent task": "世界观写回任务",
        "route audit": "路线审计",
        "word budget file": "字数预算",
        "budget agent task": "字数预算细化任务",
        "budget review": "预算审查",
        "scene inventory agent task": "场景库存规划任务",
        "chapter obligation agent task": "章节义务规划任务",
        "source manifest": "来源清单",
        "extraction agent task": "旧文反推任务",
        "extraction review": "旧文反推审查",
        "style profile": "文风画像",
        "style prompt task file": "文风提示词任务",
        "style prompt agent task": "文风提示词生成任务",
        "style prompt quality": "文风质量审查",
        "style eval readiness": "文风评估准备",
        "asset intake": "资产接收",
        "asset creation agent task": "资产创建任务",
        "asset review task file": "资产审查任务",
        "asset review agent task": "资产审查执行",
        "asset review pass": "资产审查通过",
        "asset approval": "资产审批",
        "asset promotion": "资产晋升",
        "canon lint file": "Canon 本地检查",
        "canon review task file": "Canon 审查任务",
        "canon review agent task": "Canon 审查执行",
        "canon review pass": "Canon 审查通过",
        "longform audit file": "长篇全局审计",
        "committee task file": "多视角审查任务",
        "committee agent task": "多视角审查执行",
        "committee pass": "多视角审查通过",
        "chapter workspace": "章节汇编",
        "export package": "导出包",
        "release approval": "发布审批",
        "publish release": "发布",
    }
    return mapping.get(text, text or "当前任务")


def _friendly_target(value: str) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ").strip()
    text = re.sub(r"\bscene\b", "场景", text, flags=re.I)
    text = re.sub(r"\bchapter\b", "章节", text, flags=re.I)
    text = re.sub(r"\blongform\b", "长篇规划", text, flags=re.I)
    return text


def _event_summary(event_type: str, data: dict[str, object], task: dict[str, object]) -> str:
    if event_type == "task_blocked":
        return str(data.get("message") or "任务验收没有通过。")
    if event_type == "task_submitted":
        artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), list) else []
        return f"提交了 {len(artifacts)} 个产物。"
    if event_type == "task_completed":
        return "任务完成标记已经写入。"
    if event_type == "task_opened":
        return "任务包已经被打开，平台 Agent 应按包内约束执行。"
    if event_type == "task_issued":
        return f"派发到 {_friendly_step(str(data.get('current_state') or task.get('current_state') or '当前任务'))}。"
    return "工作流记录已更新。"


def _event_artifacts(root: Path, data: dict[str, object]) -> list[str]:
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), list) else []
    completion = str(data.get("completion") or "")
    state = str(data.get("state") or "")
    result = [str(item) for item in artifacts if str(item).strip()]
    for item in [completion, state]:
        if item:
            result.append(item)
    return [_rel(root / item, root) if not Path(item).is_absolute() else item for item in result[:12]]


def _stage_priority(stage: str) -> int:
    return {
        "blocked": 100,
        "waiting_user": 90,
        "waiting_agent": 80,
        "waiting_gate": 70,
        "issued": 60,
        "next_action": 40,
        "completed": 10,
        "ready": 0,
    }.get(stage, 0)


def _submitted_at(root: Path, task_id: str) -> str:
    path = root / "workflow" / "tasks" / f"{task_id}.submission.json"
    payload = _read_json(path)
    return str(payload.get("submitted_at") or "")


def _is_stale(value: str, seconds: int) -> bool:
    elapsed = _elapsed_seconds(value)
    return elapsed > seconds if elapsed else False


def _elapsed_seconds(value: str) -> int:
    if not value:
        return 0
    try:
        text = value.replace("Z", "+00:00")
        created = datetime.fromisoformat(text)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()))
    except ValueError:
        return 0


def _ready_task() -> dict[str, object]:
    return {
        "task_id": "",
        "route": "",
        "route_label": "项目整体",
        "target": "",
        "current_step": "ready",
        "stage": "ready",
        "stage_label": STAGE_LABELS["ready"],
        "waiting_for": "none",
        "risk": "done",
        "headline": "项目等待下一轮创作方向",
        "suggested_action": "当前没有可高亮的活跃任务。可以刷新总控，或让平台 Agent 领取下一项正式任务。",
        "last_event": "",
        "last_event_at": "",
        "elapsed_seconds": 0,
        "expected_outputs": [],
        "source_paths": [],
        "progress_steps": _progress_steps("", "", "ready"),
    }


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {"event_type": "invalid", "task_id": "", "created_at": "", "data": {"raw": line}}
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_task_id(value: str) -> str:
    task_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.\-\u4e00-\u9fff]{1,200}", task_id) or ".." in task_id:
        raise ValueError("invalid task_id")
    return task_id


def _route_label(route: str) -> str:
    return ROUTE_LABELS.get(route, route or "项目整体")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
