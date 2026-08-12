"""Candidate, review, promotion, and static-review scene audit gates."""
from __future__ import annotations

from pathlib import Path
import re

from ...agent_tasks import agent_task_completion_status
from ...anti_ai_style import style_lint_gate_message
from ...candidate_promotion import candidate_generation_gate, candidate_review_gate
from ...new_character_register import new_character_register_issues
from ...narrative_rhythm import rhythm_review_status
from ...route_audit_common import _add_gate, _read_json, _read_text
from ...route_audit_evidence import (
    _agent_review_canon_writeback_ok,
    _word_budget_adherence_status,
)
from ..state_scene import current_scene_candidate


def add_scene_candidate_gates(gates: list[dict[str, str]], root: Path, scene_id: str) -> dict:
    """Project candidate creation, semantic review, and promotion evidence."""

    candidate_path = current_scene_candidate(root, scene_id)
    generation_task = candidate_path.with_suffix(".agent_tasks.md") if candidate_path is not None else None
    review_json = root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    review_task = review_json.with_suffix(".agent_tasks.md")
    candidate_gate = (
        candidate_review_gate(root, scene_id, candidate_path)
        if candidate_path is not None
        else {"status": "missing", "message": "no prose candidate found for exact-candidate review"}
    )
    generation_gate = (
        candidate_generation_gate(root, scene_id, candidate_path)
        if candidate_path is not None
        else {"status": "missing", "message": "no prose candidate found for generation provenance"}
    )

    _add_generation_gates(
        gates,
        root,
        scene_id,
        candidate_path,
        generation_task,
        candidate_gate,
        generation_gate,
    )
    review_payload = _add_review_gates(
        gates,
        root,
        scene_id,
        candidate_path,
        candidate_gate,
        review_json,
        review_task,
    )
    _add_promotion_gates(gates, root, scene_id)
    return review_payload


def _add_generation_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    candidate_path: Path | None,
    generation_task: Path | None,
    candidate_gate: dict,
    generation_gate: dict,
) -> None:
    _add_gate(
        gates,
        f"{scene_id}:prose-candidate",
        candidate_path is not None and candidate_path.exists(),
        "blocking",
        f"{scene_id} prose candidate exists",
        f"{scene_id} 缺少 drafts/candidates/{scene_id}-*.md；不能直接写 drafts/scenes 正式草稿。",
    )
    _add_gate(
        gates,
        f"{scene_id}:candidate-generation-provenance",
        generation_gate.get("status") == "pass",
        "blocking",
        f"{scene_id} candidate has formal CLI/platform-agent generation provenance",
        f"{scene_id} 候选稿缺少正式 generate-scene provenance：{generation_gate.get('message') or generation_gate.get('status') or 'missing'}。正式候选必须有 prompt manifest、.agent_tasks.md 和平台 Agent manifest 约束字段。",
    )
    if generation_task is not None:
        completion = agent_task_completion_status(generation_task, root=root)
        _add_gate(
            gates,
            f"{scene_id}:generation-agent-task-complete",
            completion.get("complete") is True,
            "blocking",
            f"{scene_id} generation platform-agent task completed",
            f"{scene_id} 的 generation sidecar 未完成：{completion.get('message')}",
        )
    lint_gate = candidate_gate.get("style_lint") if isinstance(candidate_gate, dict) else {}
    if candidate_path is not None:
        _add_gate(
            gates,
            f"{scene_id}:style-lint-clean",
            isinstance(lint_gate, dict) and lint_gate.get("status") != "blocking",
            "blocking",
            f"{scene_id} Style Lint Gate clean or notes-only",
            f"{scene_id} 候选稿未通过 Style Lint Gate：{style_lint_gate_message(lint_gate if isinstance(lint_gate, dict) else {})}。机械对照句式和 medium+ AI 腔风险必须先修订。",
        )
        budget_gate = candidate_gate.get("word_budget_adherence") if isinstance(candidate_gate, dict) else {}
        budget_status = str(budget_gate.get("status") or "").strip().lower() if isinstance(budget_gate, dict) else ""
        _add_gate(
            gates,
            f"{scene_id}:candidate-word-budget",
            budget_status in {"pass", "not_required"},
            "blocking",
            f"{scene_id} candidate cleaned body satisfies scene word budget",
            f"{scene_id} 候选稿未通过场景字数预算门禁：{budget_gate.get('message') if isinstance(budget_gate, dict) else 'missing'}。不要用非正文信息或灌水内容补字数。",
        )


def _add_review_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    candidate_path: Path | None,
    candidate_gate: dict,
    review_json: Path,
    review_task: Path,
) -> dict:
    _add_gate(
        gates,
        f"{scene_id}:agent-review-json",
        review_json.exists(),
        "blocking",
        f"{scene_id} platform Agent review JSON exists",
        f"{scene_id} 缺少 reviews/agent/{scene_id}_scene_review.json；运行 agent-review-scene --draft <candidate> 并由平台 Agent 填写 scene_review.v1。",
    )
    completion = agent_task_completion_status(review_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:agent-review-task-complete",
        completion.get("complete") is True,
        "blocking",
        f"{scene_id} platform Agent review task completed",
        f"{scene_id} 的 AgentReview sidecar 未完成：{completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:candidate-review-pass",
        candidate_gate.get("status") == "pass",
        "blocking",
        f"{scene_id} exact prose candidate review passed",
        f"{scene_id} 候选稿未通过 exact-candidate AgentReview：{candidate_gate.get('message') or candidate_gate.get('status') or 'missing'}。",
    )
    review_payload = _read_json(review_json)
    _add_review_evidence_gates(gates, root, scene_id, review_payload)
    _add_revision_evasion_gate(gates, root, scene_id, candidate_path)
    return review_payload


def _add_review_evidence_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    review_payload: dict,
) -> None:
    review_budget_status = _word_budget_adherence_status(review_payload)
    new_character_issues = (
        new_character_register_issues(review_payload, root, mode="review")
        if review_payload
        else ["new_character_register is missing"]
    )
    _add_gate(
        gates,
        f"{scene_id}:agent-review-word-budget",
        review_budget_status in {"pass", "not_required"},
        "blocking",
        f"{scene_id} AgentReview word budget gate passed",
        f"{scene_id} 的 AgentReview 缺少 clean pass 的 word_budget_adherence；当前状态：{review_budget_status or 'missing'}。",
    )
    _add_gate(
        gates,
        f"{scene_id}:agent-review-new-character-register",
        not new_character_issues,
        "blocking",
        f"{scene_id} AgentReview new-character register is resolved",
        f"{scene_id} 的 AgentReview 新角色登记未解决：{'; '.join(new_character_issues)}。",
    )
    review_rhythm_status = rhythm_review_status(review_payload)
    rhythm_value = review_payload.get("narrative_rhythm_adherence")
    review_rhythm = rhythm_value if isinstance(rhythm_value, dict) else {}
    _add_gate(
        gates,
        f"{scene_id}:agent-review-narrative-rhythm",
        review_rhythm_status in {"pass", "not_applicable"}
        and review_rhythm.get("rhythm_executed") is not False
        and review_rhythm.get("bridge_executed") is not False,
        "blocking",
        f"{scene_id} AgentReview narrative rhythm gate passed",
        f"{scene_id} 的 AgentReview 叙事节奏/场景桥接未 clean pass：{review_rhythm_status or 'missing'}。",
    )
    canon_review_ok, canon_review_message = _agent_review_canon_writeback_ok(review_payload)
    _add_gate(
        gates,
        f"{scene_id}:agent-review-canon-writeback",
        canon_review_ok,
        "blocking",
        f"{scene_id} AgentReview canon writeback declaration exists",
        f"{scene_id} 的 AgentReview 缺少可执行 canon 写回判断：{canon_review_message}。",
    )


def _add_revision_evasion_gate(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    candidate_path: Path | None,
) -> None:
    revision_manifest = _revision_manifest_path(root, scene_id, candidate_path)
    if candidate_path is not None and _is_revision_candidate(root, candidate_path):
        revision_payload = _read_json(revision_manifest)
        _add_gate(
            gates,
            f"{scene_id}:revision-evasion-clean",
            _revision_evasion_clean(revision_payload),
            "blocking",
            f"{scene_id} revision anti-evasion manifest is clean",
            f"{scene_id} 使用修订候选但缺少干净的反规避修订记录；需要 revise-scene manifest 写入 anti_evasion_protocol_applied=true，且 evasion_risks_unresolved 为空或 false。",
        )


def _add_promotion_gates(gates: list[dict[str, str]], root: Path, scene_id: str) -> None:
    promotion_json = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    promotion_payload = _read_json(promotion_json)
    promoted_draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    static_review = root / "reviews" / f"{scene_id}-review.md"
    static_review_conclusion = _static_review_conclusion(static_review)
    _add_gate(
        gates,
        f"{scene_id}:promotion-manifest",
        promotion_json.exists(),
        "blocking",
        f"{scene_id} promotion manifest exists",
        f"{scene_id} 缺少 drafts/promotions/{scene_id}_promotion.json；通过候选专属审查后运行 promote-candidate。",
    )
    _add_gate(
        gates,
        f"{scene_id}:promoted-draft",
        promoted_draft.exists(),
        "blocking",
        f"{scene_id} promoted draft exists",
        f"{scene_id} 缺少 drafts/scenes/{scene_id}.md；不能跳过 promote-candidate 直接进入章节装配。",
    )
    _add_gate(
        gates,
        f"{scene_id}:static-review-pass",
        static_review.exists() and static_review_conclusion == "pass",
        "blocking",
        f"{scene_id} local static review-scene passed",
        f"{scene_id} 缺少 clean 本地 review-scene；当前结论：{static_review_conclusion or 'missing'}。promote 后必须运行 review-scene 并处理 notes。",
    )
    if promotion_json.exists():
        promoted_candidate = str(promotion_payload.get("candidate") or "").strip()
        gate = (
            candidate_review_gate(root, scene_id, root / promoted_candidate)
            if promoted_candidate
            else {"status": "missing", "message": "promotion manifest has no candidate"}
        )
        _add_gate(
            gates,
            f"{scene_id}:promotion-candidate-review",
            gate.get("status") == "pass",
            "blocking",
            f"{scene_id} promoted candidate had a formal pre-promotion review",
            f"{scene_id} promotion 缺少正式候选审查门禁：{gate.get('message') or gate.get('status') or 'missing'}。",
        )


def _revision_manifest_path(root: Path, scene_id: str, candidate_path: Path | None) -> Path:
    if candidate_path is not None and _is_revision_candidate(root, candidate_path):
        return candidate_path.with_suffix(".json")
    return root / "drafts" / "revisions" / f"{scene_id}_revision.json"


def _is_revision_candidate(root: Path, candidate_path: Path) -> bool:
    try:
        rel = candidate_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(candidate_path)
    return rel.startswith("drafts/revisions/") or "_revision" in candidate_path.stem


def _revision_evasion_clean(payload: dict[str, object]) -> bool:
    if not payload or payload.get("anti_evasion_protocol_applied") is not True:
        return False
    unresolved = payload.get("evasion_risks_unresolved")
    if isinstance(unresolved, bool):
        return not unresolved
    if isinstance(unresolved, list):
        return len(unresolved) == 0
    if isinstance(unresolved, str):
        return unresolved.strip().lower() in {"", "false", "none", "no", "[]", "无"}
    return unresolved in (None, 0)


def _static_review_conclusion(path: Path) -> str:
    match = re.search(
        r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
        _read_text(path),
        re.IGNORECASE,
    )
    return match.group(1).strip().lower() if match else ""
