"""Conservative dry-run diagnostics for scene review contracts."""

from __future__ import annotations

from typing import Any

from ...anti_ai_style import lint_ai_style
from ...draft_text import final_body_from_workbench_text
from ...new_character_register import empty_new_character_register


def dry_scene_review(
    scene_id: str,
    draft_text: str,
    source_paths: list[str],
    word_budget_adherence: dict[str, object],
    reader_adherence: dict[str, object],
    quality_profile: dict[str, object],
    candidate_sha256: str,
) -> dict[str, object]:
    state = _diagnostic_state(
        scene_id,
        draft_text,
        source_paths,
        word_budget_adherence,
        reader_adherence,
        quality_profile,
    )
    blocking_lint = state["blocking_lint"]
    style_source = str(state["style_source"])
    has_body = bool(state["has_body"])
    return {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": scene_id,
        "candidate_sha256": candidate_sha256,
        "conclusion": state["conclusion"],
        "summary": "dry-run scene reviewer preserved the review contract and source trace.",
        "blocking_issues": [],
        "warnings": state["warnings"],
        "revision_actions": _revision_actions(blocking_lint),
        "character_logic": [_character_logic()],
        "canon_risks": [],
        "style_notes": _style_notes(state["lint_issues"]),
        "style_adherence": _style_adherence(style_source, has_body),
        "word_budget_adherence": {
            **word_budget_adherence,
            "narrative_load_satisfied": state["budget_status"] in {"pass", "not_required"},
        },
        "reader_experience_adherence": {
            **reader_adherence,
            "reader_promise_satisfied": state["reader_status"] in {"pass", "not_required"},
            "semantic_review_required": reader_adherence.get("requires_platform_agent_semantic_review", True),
        },
        "narrative_rhythm_adherence": _rhythm_adherence(has_body),
        "canon_writeback": _canon_writeback(),
        "new_character_register": empty_new_character_register(),
        "revision_integrity": _revision_integrity(blocking_lint),
        "source_paths": source_paths,
        "agent_confidence": "dry-run",
        "next_gate": "schema_validation_then_human_review",
    }


def _diagnostic_state(
    scene_id: str,
    draft_text: str,
    source_paths: list[str],
    word_budget: dict[str, object],
    reader: dict[str, object],
    profile: dict[str, object],
) -> dict[str, Any]:
    body = final_body_from_workbench_text(draft_text) or draft_text
    has_body = bool(body.strip()) and "<!-- 在这里写入场景正文。 -->" not in body
    lint_issues = lint_ai_style(body, profile=profile, scope=scene_id) if has_body else []
    blocking_lint = [issue for issue in lint_issues if issue.severity not in {"low"}]
    budget_status = str(word_budget.get("status") or "").strip().lower()
    reader_status = str(reader.get("status") or "").strip().lower()
    warnings = _warnings(has_body, blocking_lint, budget_status, reader_status, word_budget, reader)
    blocked = _is_blocked(has_body, blocking_lint, budget_status, reader_status)
    return {
        "has_body": has_body,
        "lint_issues": lint_issues,
        "blocking_lint": blocking_lint,
        "budget_status": budget_status,
        "reader_status": reader_status,
        "style_source": style_source_label(source_paths),
        "warnings": warnings,
        "conclusion": "revise_required" if blocked else "pass_with_notes",
    }


def _warnings(
    has_body: bool,
    issues: list[Any],
    budget_status: str,
    reader_status: str,
    word_budget: dict[str, object],
    reader: dict[str, object],
) -> list[str]:
    warnings = [] if has_body else ["场景草稿缺少可审查正文，需先补正文或提升生成候选。"]
    warnings.extend(f"Style lint: {issue.rule} - {issue.message}" for issue in issues)
    if budget_status not in {"pass", "not_required"}:
        warnings.append(f"Word budget gate: {word_budget.get('message')}")
    if reader_status not in {"pass", "not_required"}:
        warnings.append(f"Reader experience gate: {reader.get('message')}")
    return warnings


def _is_blocked(has_body: bool, issues: list[Any], budget_status: str, reader_status: str) -> bool:
    return (
        not has_body
        or bool(issues)
        or budget_status not in {"pass", "not_required"}
        or reader_status not in {"pass", "not_required"}
    )


def _revision_actions(issues: list[Any]) -> list[str]:
    return ["保留人工确认点；不要把候选事实直接写入 canon。"] + [
        f"按确定性 Style Lint 逐句复核 `{issue.sample}`，修订 {issue.rule}，不得用脚本直接删改造成语义反转。"
        for issue in issues
        if issue.sample
    ]


def _character_logic() -> dict[str, str]:
    return {
        "character": "all",
        "assessment": "检查人物 BDI、背景故事隐性动因和当前状态是否共同支持行动。",
    }


def _style_notes(issues: list[Any]) -> list[str]:
    return [
        "后续真实模型审查应核对 style_prompt.md 是否影响句法、叙述距离和意象调度。",
        *[f"确定性 Style Lint 检出 {issue.rule}: {issue.sample}" for issue in issues],
    ]


def _style_adherence(style_source: str, has_body: bool) -> dict[str, object]:
    status = "pass_with_notes" if style_source and has_body else ("revise_required" if style_source else "not_applicable")
    actions = ["真实平台审查需确认挂载文风已经影响叙述距离、句法节奏、意象系统、对白语气和标点停顿。"] if style_source else []
    return {
        "status": status,
        "style_profile": style_source or "n/a",
        "evidence": ["dry-run 仅保持审查契约；真实平台 agent 需要引用正文证据。"] if style_source else [],
        "deviations": [],
        "revision_actions": actions,
    }


def _rhythm_adherence(has_body: bool) -> dict[str, object]:
    return {
        "status": "pass_with_notes" if has_body else "revise_required",
        "rhythm_executed": has_body,
        "bridge_executed": has_body,
        "flatness_risks": ["dry-run cannot semantically judge rhythm; platform agent must verify scene turn and bridge."],
        "revision_actions": [],
    }


def _canon_writeback() -> dict[str, str]:
    return {"status": "unknown", "canon_change": "unknown", "no_canon_change_reason": "", "candidate_patch": ""}


def _revision_integrity(issues: list[Any]) -> dict[str, object]:
    evasion = [
        f"{issue.rule}: {issue.sample}"
        for issue in issues
        if issue.rule in {"mechanical-contrast-frame", "contrast-evasion-frame"}
    ]
    return {
        "status": "pass" if not issues else "revise_required",
        "anti_evasion_checked": True,
        "evasion_risks": evasion,
        "evasion_risks_unresolved": evasion.copy(),
        "retained_transitions": [],
        "burden_of_proof": [],
        "message": "dry-run deterministic review; platform agent must perform semantic revision-integrity review.",
    }


def style_source_label(source_paths: list[str]) -> str:
    for value in source_paths:
        normalized = value.replace("\\", "/")
        if normalized.startswith("style/") and any(
            marker in normalized
            for marker in ("active_style_skill.json", "style_prompt.md", "prompt.md", "style-profile.md")
        ):
            return normalized
    return ""


__all__ = ["dry_scene_review"]
