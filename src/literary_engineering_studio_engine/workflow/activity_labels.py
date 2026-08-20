"""Human-readable labels and progress hints for workflow activity."""

from __future__ import annotations

from datetime import datetime, timezone
import re


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


def progress_steps(route: str, current_state: str, stage: str) -> list[dict[str, object]]:
    steps = _scene_steps() if route == "scene-development" else _standard_steps()
    index = _step_index(steps, current_state, stage)
    return [
        {"key": key, "label": label, "state": "done" if i < index else "active" if i == index else "todo"}
        for i, (key, label) in enumerate(steps)
    ]


def _scene_steps() -> list[tuple[str, str]]:
    return [
        ("context", "上下文"),
        ("roleplay", "角色推演"),
        ("branch", "分支"),
        ("composition", "编剧态"),
        ("generation", "正文"),
        ("review", "审查"),
        ("promotion", "晋升"),
        ("state", "状态/Canon"),
    ]


def _standard_steps() -> list[tuple[str, str]]:
    return [
        ("task-next", "派发"),
        ("task-open", "打开"),
        ("agent", "执行"),
        ("task-submit", "提交"),
        ("task-complete", "验收"),
        ("route-audit", "审计"),
    ]


def _step_index(steps: list[tuple[str, str]], current_state: str, stage: str) -> int:
    text = f"{current_state} {stage}".lower()
    for index, (key, _) in enumerate(steps):
        if key in text:
            return index
    fallbacks = {
        "issued": 0,
        "waiting_agent": min(2, len(steps) - 1),
        "waiting_gate": max(0, len(steps) - 2),
        "completed": len(steps) - 1,
    }
    return fallbacks.get(stage, 0)


def task_suggestion(stage: str, task: dict[str, object], last_event: dict[str, object] | None) -> str:
    if stage == "blocked":
        data = last_event.get("data") if isinstance(last_event, dict) and isinstance(last_event.get("data"), dict) else {}
        return str(data.get("message") or "CLI 门禁拦截了这一步。请按阻塞信息修复后重新提交验收。")
    suggestions = {
        "waiting_agent": "平台 Agent 应读取任务包和指定资料，完成预期产物后运行 task-submit。",
        "waiting_gate": "产物已提交，下一步应运行 task-complete，让 CLI 做正式验收。",
        "issued": "任务已经派发。下一步应运行 task-open，读取完整执行包。",
        "completed": "最近任务已经完成。刷新 workflow-dashboard 或领取下一项任务。",
    }
    return suggestions.get(stage, str(task.get("command") or "按正式状态机继续推进。"))


def task_purpose(task: dict[str, object]) -> str:
    route = str(task.get("route") or "")
    current_state = str(task.get("current_state") or "")
    target = str(task.get("scene_id") or task.get("target_id") or "")
    return headline(route, target, current_state, str(task.get("status") or "issued"))


def headline(route: str, target: str, current_state: str, stage: str) -> str:
    target_text = friendly_target(target)
    step_text = friendly_step(current_state)
    if stage == "blocked":
        return f"{route_label(route)}卡在{step_text}"
    if stage == "waiting_user":
        return f"{target_text or route_label(route)}等待你决定"
    if stage == "completed":
        return f"{target_text or route_label(route)}最近完成了{step_text}"
    if step_text:
        return f"{target_text or route_label(route)}正在推进{step_text}"
    return f"{route_label(route)}等待下一步"


def friendly_step(value: str) -> str:
    text = str(value or "").replace("-", " ").replace("_", " ").strip()
    mapping = {
        "context packet": "上下文包", "context trace": "上下文来源核验", "roleplay simulation": "角色推演",
        "roleplay agent task": "角色推演任务", "branch manifest": "分支清单", "branch simulation": "分支推演",
        "branch agent task": "分支研判任务", "branch selection": "分支选择", "composition": "编剧态",
        "composition json": "编剧态方案", "composition agent task": "编剧态任务", "scene word budget contract": "场景字数契约",
        "reader experience contract": "读者体验契约", "candidate generation provenance": "正文生成来源",
        "prose candidate": "正文候选", "generation agent task": "正文生成任务", "agent review": "正式审查",
        "agent review task": "正式审查任务", "candidate review": "正文审查", "promotion": "正文晋升",
        "promotion manifest": "晋升清单", "promoted draft": "正式草稿", "static review": "静态审查",
        "state evolve": "状态演化", "state patch json": "状态补丁", "state agent task": "人物状态演化任务",
        "canon writeback": "Canon 写回", "canon patch json": "Canon 补丁", "canon agent task": "世界观写回任务",
        "route audit": "路线审计", "word budget file": "字数预算", "budget agent task": "字数预算细化任务",
        "budget review": "预算审查", "scene inventory agent task": "场景库存规划任务",
        "chapter obligation agent task": "章节义务规划任务", "source manifest": "来源清单",
        "extraction agent task": "旧文反推任务", "extraction review": "旧文反推审查", "style profile": "文风画像",
        "style prompt task file": "文风提示词任务", "style prompt agent task": "文风提示词生成任务",
        "style prompt quality": "文风质量审查", "style eval readiness": "文风评估准备", "asset intake": "资产接收",
        "asset creation agent task": "资产创建任务", "asset review task file": "资产审查任务",
        "asset review agent task": "资产审查执行", "asset review pass": "资产审查通过", "asset approval": "资产审批",
        "asset promotion": "资产晋升", "canon lint file": "Canon 本地检查", "canon review task file": "Canon 审查任务",
        "canon review agent task": "Canon 审查执行", "canon review pass": "Canon 审查通过",
        "longform audit file": "长篇全局审计", "committee task file": "多视角审查任务",
        "committee agent task": "多视角审查执行", "committee pass": "多视角审查通过",
        "chapter workspace": "章节汇编", "export package": "导出包", "release approval": "发布审批", "publish release": "发布",
    }
    return mapping.get(text, text or "当前任务")


def friendly_target(value: str) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ").strip()
    text = re.sub(r"\bscene\b", "场景", text, flags=re.I)
    text = re.sub(r"\bchapter\b", "章节", text, flags=re.I)
    return re.sub(r"\blongform\b", "长篇规划", text, flags=re.I)


def event_summary(event_type: str, data: dict[str, object], task: dict[str, object]) -> str:
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
        return f"派发到 {friendly_step(str(data.get('current_state') or task.get('current_state') or '当前任务'))}。"
    return "工作流记录已更新。"


def stage_priority(stage: str) -> int:
    return {
        "blocked": 100, "waiting_user": 90, "waiting_agent": 80, "waiting_gate": 70,
        "issued": 60, "next_action": 40, "completed": 10, "ready": 0,
    }.get(stage, 0)


def elapsed_seconds(value: str) -> int:
    if not value:
        return 0
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()))
    except ValueError:
        return 0


def is_stale(value: str, seconds: int) -> bool:
    elapsed = elapsed_seconds(value)
    return elapsed > seconds if elapsed else False


def route_label(route: str) -> str:
    return ROUTE_LABELS.get(route, route or "项目整体")


def ready_task() -> dict[str, object]:
    return {
        "task_id": "", "route": "", "route_label": "项目整体", "target": "", "current_step": "ready",
        "stage": "ready", "stage_label": STAGE_LABELS["ready"], "waiting_for": "none", "risk": "done",
        "headline": "项目等待下一轮创作方向",
        "suggested_action": "当前没有可高亮的活跃任务。可以刷新总控，或让平台 Agent 领取下一项正式任务。",
        "last_event": "", "last_event_at": "", "elapsed_seconds": 0, "expected_outputs": [], "source_paths": [],
        "progress_steps": progress_steps("", "", "ready"),
    }
