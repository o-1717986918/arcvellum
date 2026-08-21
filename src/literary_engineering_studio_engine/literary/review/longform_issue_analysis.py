"""Deterministic literary and workflow findings for long-form audits."""

from __future__ import annotations

from pathlib import Path

from ...context_broker import context_trace_status
from ..scene.promotion.historical import validate_historical_promotion
from .longform_models import LongformIssue, LongformSceneRecord


RESOLVED_FORESHADOW_STATUSES = {
    "paid", "resolved", "closed", "done", "complete", "completed",
    "回收", "已回收", "完成", "已完成",
}


def audit_issues(
    root: Path,
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, str]],
    foreshadowing: list[dict[str, str]],
    chapter_files: list[Path],
    target_length: int,
    word_budget: dict[str, object],
) -> list[LongformIssue]:
    issues = _inventory_issues(scenes)
    issues.extend(_scene_issues(root, scenes, characters))
    issues.extend(_chapter_workspace_issues(scenes, chapter_files))
    issues.extend(_word_budget_issues(scenes, target_length, word_budget))
    issues.extend(_scale_progress_issues(scenes, target_length))
    issues.extend(_foreshadowing_issues(foreshadowing))
    return issues


def rhythm_curve_issues(curves: dict[str, dict[str, object]]) -> list[LongformIssue]:
    issues: list[LongformIssue] = []
    for chapter_id, curve in curves.items():
        for issue in curve.get("issues", []):
            if not isinstance(issue, dict):
                continue
            severity = "high" if issue.get("severity") == "blocking" else "medium"
            category = "narrative_rhythm_curve" if severity == "high" else "narrative_rhythm_attention"
            issues.append(LongformIssue(
                severity, category, chapter_id,
                str(issue.get("message") or "章节叙事节奏曲线需要复核。"),
                "回到场景编排，调整场景功能、推进速度或 entry/peak/exit 张力交接；不要只靠正文修辞制造假高潮。",
            ))
    return issues


def _inventory_issues(scenes: list[LongformSceneRecord]) -> list[LongformIssue]:
    issues: list[LongformIssue] = []
    if not scenes:
        issues.append(LongformIssue(
            "high", "scene_inventory", "scenes/",
            "未发现任何场景文件，无法进行长篇连续性审计。",
            "先用场景模板建立至少一个 scenes/{scene_id}.yaml。",
        ))
    scene_ids = [scene.scene_id for scene in scenes]
    for scene_id in sorted({item for item in scene_ids if scene_ids.count(item) > 1}):
        issues.append(LongformIssue(
            "high", "scene_identity", scene_id,
            "发现重复 scene_id，后续草稿、审查和图谱节点会互相覆盖。",
            "为每个场景分配唯一 scene_id。",
        ))
    return issues


def _scene_issues(
    root: Path,
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, object]],
) -> list[LongformIssue]:
    known = {item["character_id"] for item in characters}
    known |= {item["name"] for item in characters if item["name"]}
    known |= {
        str(alias)
        for item in characters
        for alias in (item.get("aliases") if isinstance(item.get("aliases"), list) else [])
        if str(alias).strip()
    }
    known |= {
        str(item.get("role_label") or "").strip()
        for item in characters
        if str(item.get("role_label") or "").strip()
    }
    issues: list[LongformIssue] = []
    for scene in scenes:
        issues.extend(_scene_contract_issues(scene, known))
        issues.extend(_scene_readiness_issues(scene))
        issues.extend(_context_issues(root, scene))
    return issues


def _scene_contract_issues(scene: LongformSceneRecord, known_names: set[str]) -> list[LongformIssue]:
    issues: list[LongformIssue] = []
    if scene.chapter_id == "unassigned":
        issues.append(LongformIssue("medium", "chapter_structure", scene.scene_id, "场景缺少 chapter_id。", "补齐 chapter_id，避免章节装配时误分组。"))
    if not scene.location:
        issues.append(LongformIssue("medium", "scene_schema", scene.scene_id, "场景缺少 location。", "补齐地点以支持连续性和图谱审计。"))
    if not scene.participants:
        issues.append(LongformIssue("medium", "scene_schema", scene.scene_id, "场景缺少 participants。", "补齐参与人物以支持人物弧审计。"))
    if not scene.scene_goal:
        issues.append(LongformIssue("medium", "scene_schema", scene.scene_id, "场景缺少 scene_goal。", "补齐场景目标，避免章节节奏失焦。"))
    if scene.narrative_rhythm_status in {"", "defaulted", "incomplete"}:
        issues.append(LongformIssue(
            "medium", "narrative_rhythm", scene.scene_id,
            f"叙事节奏/场景桥接契约未显式通过：{scene.narrative_rhythm_status or 'missing'}。",
            "补齐 scene_function、scene_turn、reader_effect、incoming_pressure 和 outgoing_hook，避免场景孤岛和平均速度叙事。",
        ))
    for participant in scene.participants:
        if known_names and participant not in known_names:
            issues.append(LongformIssue(
                "medium", "character_inventory", scene.scene_id,
                f"参与者 `{participant}` 没有匹配的人物档案。",
                "在 characters/ 中创建人物档案，或统一 participant 名称。",
            ))
    return issues


def _scene_readiness_issues(scene: LongformSceneRecord) -> list[LongformIssue]:
    issue = _readiness_issue(scene)
    return [issue] if issue else []


def _readiness_issue(scene: LongformSceneRecord) -> LongformIssue | None:
    definitions = {
        "needs_draft": ("draft_readiness", "场景缺少可审计正文草稿。", "运行 draft-scene 并补全正文草稿。"),
        "needs_flow_gates": ("flow_readiness", "场景缺少正式场景链路门禁，不能进入章节或长篇 ready。", "补齐 context、simulate-scene --agent、branch-simulate --agent、branch_selection.md 和 ready composition。"),
        "needs_review": ("review_readiness", "场景有正文但缺少审查报告。", "运行 review-scene。"),
        "needs_agent_review": ("review_readiness", "场景缺少平台 Agent 正式审查 JSON，不能进入 ready。", "运行 agent-review-scene 生成任务，由平台 agent 填写 scene_review.v1 JSON 和 Markdown 报告。"),
        "needs_revision": ("review_readiness", "场景存在 pass_with_notes、warnings、revision_actions、style_notes 或未解决文风偏差。", "运行 revise-scene 或记录正式 waiver 后重新进行静态/AgentReview。"),
        "blocked": ("review_readiness", f"场景审查未通过：{scene.review_conclusion or 'unknown'}。", "根据审查报告修订后重新 review-scene。"),
    }
    definition = definitions.get(scene.status)
    return LongformIssue("high", definition[0], scene.scene_id, definition[1], definition[2]) if definition else None


def _context_issues(root: Path, scene: LongformSceneRecord) -> list[LongformIssue]:
    historical = validate_historical_promotion(root, scene.scene_id)
    if historical.passed and historical.current:
        return []
    context_path = root / "memory" / "context_packets" / f"{scene.scene_id}.md"
    issues: list[LongformIssue] = []
    if not context_path.exists():
        issues.append(LongformIssue("medium", "memory_context", scene.scene_id, "缺少场景上下文包。", "运行 context 或 draft-scene --rebuild-context。"))
    trace_status = context_trace_status(root, scene.scene_id, context_path=context_path)
    if not trace_status.passed:
        issues.append(LongformIssue(
            "high", "memory_context", scene.scene_id,
            f"场景上下文来源证明无效：{trace_status.message}",
            "重跑 context 并检查 memory/context_packets/{scene_id}.trace.json。",
        ))
    return issues


def _chapter_workspace_issues(scenes: list[LongformSceneRecord], chapter_files: list[Path]) -> list[LongformIssue]:
    chapter_ids = sorted({scene.chapter_id for scene in scenes if scene.chapter_id != "unassigned"})
    available = {path.stem for path in chapter_files}
    return [
        LongformIssue("low", "chapter_workspace", chapter_id, "缺少章节工作台 JSON。", "运行 chapter-workspace 生成章节级状态对象。")
        for chapter_id in chapter_ids
        if chapter_id not in available
    ]


def _word_budget_issues(
    scenes: list[LongformSceneRecord],
    target_length: int,
    word_budget: dict[str, object],
) -> list[LongformIssue]:
    issues: list[LongformIssue] = []
    subject = "plot/word_budget/word_budget.json"
    if target_length >= 100000 and not word_budget:
        issues.append(LongformIssue(
            "medium", "word_budget", subject,
            "目标中文内容字符达到中长篇规模，但缺少长篇字数预算与剧情库存门禁。",
            "先运行 word-budget / longform-budget，并由平台 agent 根据任务侧车扩充预算化大纲候选。",
        ))
        return issues
    if not word_budget:
        return issues
    totals = word_budget.get("totals", {})
    totals = totals if isinstance(totals, dict) else {}
    planned_scenes = to_int(totals.get("scene_count"))
    if str(word_budget.get("status") or "") == "needs_expansion":
        issues.append(LongformIssue(
            "medium", "word_budget", subject,
            "预算报告显示现有大纲或场景库存不足，直接生成正文容易把长篇压缩成短篇摘要。",
            "让平台 agent 处理 word_budget.agent_tasks.md，写出预算化大纲候选并通过 word-budget review。",
        ))
    if planned_scenes and scenes and len(scenes) < planned_scenes * 0.5:
        issues.append(LongformIssue(
            "medium", "scene_inventory", "scenes/",
            f"预算需要约 {planned_scenes} 个场景，目前仅登记 {len(scenes)} 个场景，剧情库存明显不足。",
            "先扩充分卷、分章和场景列表，再进入批量正文生成。",
        ))
    binding = word_budget.get("scene_inventory_binding")
    binding = binding if isinstance(binding, dict) else {}
    actual_chars = to_int(
        binding.get("actual_draft_chinese_chars")
        or binding.get("actual_draft_chars")
    )
    missing_scenes = to_int(binding.get("missing_scene_count"))
    actual_scenes = to_int(binding.get("actual_scene_count"))
    target_issue = _target_length_issue(
        target_length=target_length,
        planned_scenes=planned_scenes,
        actual_scenes=actual_scenes,
        missing_scenes=missing_scenes,
        actual_chars=actual_chars,
    )
    if target_issue is not None:
        issues.append(target_issue)
    return issues


def _target_length_issue(
    *,
    target_length: int,
    planned_scenes: int,
    actual_scenes: int,
    missing_scenes: int,
    actual_chars: int,
) -> LongformIssue | None:
    inventory_complete = (
        target_length > 0
        and planned_scenes > 0
        and actual_scenes >= planned_scenes
        and missing_scenes == 0
    )
    if not inventory_complete or actual_chars >= target_length:
        return None
    return LongformIssue(
        "high", "target_length_shortfall", "drafts/scenes",
        f"全书正文为 {actual_chars} 个中文内容字符，低于明确目标 {target_length}，缺口 {target_length - actual_chars}。",
        "生成正式目标长度修订计划，把缺口分配到有叙事容量的场景；逐场走主 Agent 修订、独立复审、晋升和连续性闭环，禁止注水或用单场容差替代全书目标。",
    )


def _scale_progress_issues(scenes: list[LongformSceneRecord], target_length: int) -> list[LongformIssue]:
    draft_chars = sum(scene.draft_chars for scene in scenes)
    if target_length <= 0 or draft_chars >= target_length * 0.2:
        return []
    return [LongformIssue(
        "low", "scale_progress", "drafts",
        f"当前正文约 {draft_chars} 个中文内容字符，距离目标 {target_length} 个中文内容字符仍处于早期阶段。",
        "优先补齐场景草稿、章节工作台和连续性审查，再扩大生成规模。",
    )]


def _foreshadowing_issues(rows: list[dict[str, str]]) -> list[LongformIssue]:
    issues: list[LongformIssue] = []
    for row in rows:
        status = foreshadow_status(row)
        if status and status.lower() in RESOLVED_FORESHADOW_STATUSES:
            continue
        expected = row.get("expected_payoff") or row.get("expected_payoff_range") or ""
        actual = row.get("actual_payoff_scene") or row.get("payoff_scene") or ""
        if not expected and not actual:
            issues.append(LongformIssue(
                "medium", "foreshadowing_debt", row.get("foreshadow_id") or row.get("id") or "unknown",
                "伏笔缺少预期回收范围或实际回收场景。",
                "补齐 expected_payoff_range 或 actual_payoff_scene，避免伏笔债务失控。",
            ))
    return issues


def foreshadow_status(row: dict[str, str]) -> str:
    return row.get("status") or row.get("状态") or ""


def to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = ["audit_issues", "foreshadow_status", "rhythm_curve_issues", "to_int"]
