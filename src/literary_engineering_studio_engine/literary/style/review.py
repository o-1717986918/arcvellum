"""Digest-bound independent semantic review for formal style sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from ...agent_tasks import agent_task_completion_status, write_agent_tasks
from ...atomic_io import atomic_write_text
from ...task_paths import relative_path, task_id
from .session import load_style_session


STYLE_REVIEW_SCHEMA = "arcvellum/style-semantic-review/v1"
STYLE_REVIEW_DIMENSIONS = (
    "evidence_integrity",
    "prompt_executability",
    "style_mechanism_fidelity",
    "evaluation_validity",
    "originality_boundary",
    "literary_usability",
)
STYLE_REVIEW_VERDICTS = {"pending", "pass", "revise", "block"}
STYLE_REVIEW_AGENT_FIELDS = {
    "verdict",
    "summary",
    "findings",
    "required_changes",
    "effectiveness_assessment",
    "copy_risk_assessment",
    "evidence_limitations",
}
STYLE_REVIEW_MACHINE_FIELDS = {
    "schema",
    "status",
    "profile_id",
    "evidence",
    "prompt_writer_session_id",
    "evaluation_writer_session_id",
    "reviewer_session_id",
    "checked_dimensions",
    "review_report_path",
    "review_report_sha256",
    "created_at",
}


@dataclass(frozen=True)
class StyleReviewPaths:
    review_json: Path
    review_markdown: Path
    task: Path
    completion: Path


@dataclass(frozen=True)
class StyleReviewState:
    stage: str
    message: str
    errors: tuple[str, ...] = ()


def style_review_paths(profile_dir: Path) -> StyleReviewPaths:
    evaluation = profile_dir / "evaluation_results" / "formal"
    task = evaluation / "style_semantic_review.agent_tasks.md"
    return StyleReviewPaths(
        evaluation / "style_semantic_review.json",
        evaluation / "style_semantic_review.md",
        task,
        evaluation / "style_semantic_review.agent_completion.json",
    )


def prepare_style_semantic_review(
    project_root: Path,
    profile_dir: Path,
    *,
    target_id: str,
) -> StyleReviewPaths:
    """Prepare a reviewer task without exposing raw holdout text."""

    root = project_root.resolve()
    profile = _inside(root, profile_dir)
    evidence, evidence_errors = style_review_evidence(root, profile)
    if evidence_errors:
        raise ValueError("style review evidence is not ready: " + "; ".join(evidence_errors))
    paths = style_review_paths(profile)
    paths.review_json.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_object(paths.review_json)
    current = (
        existing.get("schema") == STYLE_REVIEW_SCHEMA
        and existing.get("evidence") == evidence
        and str(existing.get("profile_id") or "") == target_id
    )
    if not current:
        atomic_write_text(
            paths.review_json,
            json.dumps(_review_skeleton(target_id, evidence), ensure_ascii=False, indent=2) + "\n",
        )
        atomic_write_text(paths.review_markdown, _review_markdown_skeleton(target_id))
    elif not paths.review_markdown.is_file():
        atomic_write_text(paths.review_markdown, _review_markdown_skeleton(target_id))

    digest_lines = "\n".join(
        f"- `{key}`: `{value}`"
        for key, value in sorted(evidence.items())
        if key.endswith("_sha256")
    )
    write_agent_tasks(
        paths.task,
        title="文风工程独立语义审查",
        root=root,
        source_paths=style_review_safe_sources(root, profile, paths),
        tasks=[
            (
                "独立审查文风提示词有效性",
                _review_instruction(root, paths, digest_lines),
            )
        ],
        notes=[
            "本任务不得读取原始 holdout 正文；只审查确定性评分、摘要绑定和可执行文风机制。",
            "Reviewer 必须独立于提示词 Writer 和评测候选 Writer；身份由 Studio Worker 绑定。",
            "只输出结论和可核验证据，不输出隐藏思维链、逐步推理草稿或内部 deliberation。",
        ],
    )
    return paths


def inspect_style_semantic_review(
    project_root: Path,
    profile_dir: Path,
    *,
    target_id: str,
) -> StyleReviewState:
    root = project_root.resolve()
    profile = profile_dir.resolve()
    paths = style_review_paths(profile)
    if not paths.task.is_file() or not paths.review_json.is_file() or not paths.review_markdown.is_file():
        return StyleReviewState("prepare", "independent style review task is missing")

    payload = _read_object(paths.review_json)
    evidence, evidence_errors = style_review_evidence(root, profile)
    if evidence_errors:
        return StyleReviewState("prepare", "upstream style evidence is incomplete", tuple(evidence_errors))
    if payload.get("evidence") != evidence or str(payload.get("profile_id") or "") != target_id:
        return StyleReviewState("prepare", "independent style review is stale for current evidence")

    completion = agent_task_completion_status(paths.task, root=root)
    if completion.get("complete") is not True:
        return StyleReviewState("agent", str(completion.get("message") or "style review pending"))

    errors = style_semantic_review_errors(root, profile, target_id=target_id, require_pass=False)
    if errors:
        return StyleReviewState("revision", "style review contract is invalid", tuple(errors))
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict != "pass":
        return StyleReviewState("revision", f"independent style review verdict is {verdict}")
    return StyleReviewState("ready", "independent style review passes exact evidence")


def style_semantic_review_errors(
    project_root: Path,
    profile_dir: Path,
    *,
    target_id: str,
    require_pass: bool,
) -> list[str]:
    root = project_root.resolve()
    profile = profile_dir.resolve()
    paths = style_review_paths(profile)
    payload = _read_object(paths.review_json)
    errors: list[str] = []
    if payload.get("schema") != STYLE_REVIEW_SCHEMA:
        errors.append("style semantic review schema is invalid")
        return errors
    evidence, evidence_errors = style_review_evidence(root, profile)
    errors.extend(evidence_errors)
    if payload.get("evidence") != evidence:
        errors.append("style semantic review is stale for current evidence digests")
    errors.extend(_review_shape_errors(payload, target_id))
    errors.extend(_review_report_errors(root, paths, payload))
    errors.extend(_review_completion_errors(root, paths))
    errors.extend(_review_verdict_errors(payload, require_pass=require_pass))
    return errors


def _review_report_errors(
    root: Path,
    paths: StyleReviewPaths,
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    report_sha = _sha256(paths.review_markdown) if paths.review_markdown.is_file() else ""
    if str(payload.get("review_report_path") or "") != relative_path(paths.review_markdown, root):
        errors.append("style semantic review report path is invalid")
    if not report_sha or str(payload.get("review_report_sha256") or "") != report_sha:
        errors.append("style semantic review report digest is stale")
    return errors


def _review_completion_errors(root: Path, paths: StyleReviewPaths) -> list[str]:
    completion = agent_task_completion_status(paths.task, root=root)
    if completion.get("complete") is not True:
        return [f"style semantic review sidecar is incomplete: {completion.get('message')}"]
    return []


def _review_verdict_errors(payload: dict[str, Any], *, require_pass: bool) -> list[str]:
    errors: list[str] = []
    verdict = str(payload.get("verdict") or "").strip().lower()
    if require_pass and verdict != "pass":
        errors.append(f"style semantic review is not a pass: {verdict or 'missing'}")
    if verdict == "pass" and payload.get("required_changes"):
        errors.append("passing style semantic review cannot retain required_changes")
    return errors


def style_review_machine_values(
    project_root: Path,
    profile_dir: Path,
    *,
    target_id: str,
    reviewer_session_id: str,
) -> dict[str, object]:
    root = project_root.resolve()
    profile = profile_dir.resolve()
    paths = style_review_paths(profile)
    evidence, _errors = style_review_evidence(root, profile)
    prompt_manifest = _read_object(profile / "style_prompt.agent.json")
    evaluation_manifest = _read_object(
        profile / "evaluation_results" / "formal" / "platform_agent_candidate.prompt.json"
    )
    return {
        "schema": STYLE_REVIEW_SCHEMA,
        "profile_id": target_id,
        "evidence": evidence,
        "prompt_writer_session_id": str(prompt_manifest.get("writer_session_id") or "")
        or _writer_identity(target_id, "style-prompt-agent-task"),
        "evaluation_writer_session_id": str(evaluation_manifest.get("writer_session_id") or "")
        or _writer_identity(target_id, "style-eval-agent-task"),
        "reviewer_session_id": reviewer_session_id,
        "checked_dimensions": list(STYLE_REVIEW_DIMENSIONS),
        "review_report_path": relative_path(paths.review_markdown, root),
        "review_report_sha256": _sha256(paths.review_markdown) if paths.review_markdown.is_file() else "",
    }


def style_review_evidence(
    project_root: Path,
    profile_dir: Path,
) -> tuple[dict[str, str], list[str]]:
    root = project_root.resolve()
    profile = profile_dir.resolve()
    evaluation = profile / "evaluation_results" / "formal"
    artifacts = {
        "session": profile / "style_session.json",
        "profile": profile / "style-profile.md",
        "metrics": profile / "style_metrics.json",
        "prompt": profile / "style_prompt.md",
        "prompt_manifest": profile / "style_prompt.agent.json",
        "candidate": evaluation / "platform_agent_candidate.md",
        "evaluation_manifest": evaluation / "platform_agent_candidate.prompt.json",
        "score": evaluation / "style_eval_current.json",
        "score_report": evaluation / "style_eval_current.md",
    }
    errors: list[str] = []
    evidence: dict[str, str] = {}
    for name, path in artifacts.items():
        if name == "session" and not path.is_file():
            continue
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"style review evidence missing: {relative_path(path, root)}")
            continue
        evidence[f"{name}_path"] = relative_path(path, root)
        evidence[f"{name}_sha256"] = _sha256(path)
    evidence["source_set_sha256"] = _source_set_sha256(profile)
    errors.extend(_score_binding_errors(profile))
    errors.extend(style_eval_generation_digest_errors(root, profile))
    return evidence, errors


def style_eval_generation_digest_errors(project_root: Path, profile_dir: Path) -> list[str]:
    """Require exact generation digests for formal sessions, with legacy tolerance."""

    if not load_style_session(profile_dir):
        return []
    root = project_root.resolve()
    evaluation = profile_dir / "evaluation_results" / "formal"
    manifest = _read_object(evaluation / "platform_agent_candidate.prompt.json")
    paths = {
        "style_prompt_sha256": profile_dir / "style_prompt.md",
        "candidate_sha256": evaluation / "platform_agent_candidate.md",
        "input_sha256": root / "project.yaml",
    }
    errors: list[str] = []
    for field, path in paths.items():
        if not path.is_file() or str(manifest.get(field) or "") != _sha256(path):
            errors.append(f"formal style evaluation manifest has stale {field}")
    score = _read_object(evaluation / "style_eval_current.json")
    reference_sha = str(score.get("reference_sha256") or "")
    if not reference_sha or str(manifest.get("reference_sha256") or "") != reference_sha:
        errors.append("formal style evaluation manifest has stale reference_sha256")
    if not str(manifest.get("writer_session_id") or "").strip():
        errors.append("formal style evaluation manifest lacks writer_session_id")
    return errors


def style_review_safe_sources(
    root: Path,
    profile_dir: Path,
    paths: StyleReviewPaths | None = None,
) -> list[Path]:
    review_paths = paths or style_review_paths(profile_dir)
    candidates = [
        profile_dir / "style_session.json",
        profile_dir / "style-profile.md",
        profile_dir / "style_metrics.json",
        profile_dir / "style_prompt.md",
        profile_dir / "style_prompt.agent.json",
        profile_dir / "evaluation_results/formal/platform_agent_candidate.md",
        profile_dir / "evaluation_results/formal/platform_agent_candidate.prompt.json",
        profile_dir / "evaluation_results/formal/style_eval_current.json",
        profile_dir / "evaluation_results/formal/style_eval_current.md",
        review_paths.review_json,
        review_paths.review_markdown,
        review_paths.task,
    ]
    return [path for path in candidates if path.is_file()]


def _review_shape_errors(payload: dict[str, Any], target_id: str) -> list[str]:
    return [
        *_review_contract_field_errors(payload, target_id),
        *_review_content_errors(payload),
        *_review_identity_errors(payload),
    ]


def _review_contract_field_errors(payload: dict[str, Any], target_id: str) -> list[str]:
    errors: list[str] = []
    allowed = STYLE_REVIEW_AGENT_FIELDS | STYLE_REVIEW_MACHINE_FIELDS
    unknown = sorted(set(payload) - allowed)
    if unknown:
        errors.append("style semantic review contains undeclared fields: " + ", ".join(unknown))
    if str(payload.get("profile_id") or "") != target_id:
        errors.append("style semantic review profile_id is invalid")
    status = str(payload.get("status") or "").strip().lower()
    if status != "complete":
        errors.append("style semantic review status must be complete")
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict not in STYLE_REVIEW_VERDICTS - {"pending"}:
        errors.append("style semantic review verdict must be pass, revise, or block")
    if payload.get("checked_dimensions") != list(STYLE_REVIEW_DIMENSIONS):
        errors.append("style semantic review checked_dimensions are incomplete")
    return errors


def _review_content_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("summary", "effectiveness_assessment", "copy_risk_assessment"):
        if not str(payload.get(field) or "").strip():
            errors.append(f"style semantic review missing {field}")
    for field in ("findings", "required_changes", "evidence_limitations"):
        if not isinstance(payload.get(field), list):
            errors.append(f"style semantic review {field} must be a list")
    return errors


def _review_identity_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prompt_writer = str(payload.get("prompt_writer_session_id") or "")
    evaluation_writer = str(payload.get("evaluation_writer_session_id") or "")
    reviewer = str(payload.get("reviewer_session_id") or "")
    if not prompt_writer or not evaluation_writer or not reviewer:
        errors.append("style semantic review requires writer and reviewer session identities")
    elif reviewer in {prompt_writer, evaluation_writer}:
        errors.append("style semantic reviewer session must differ from both writer sessions")
    return errors


def _score_binding_errors(profile_dir: Path) -> list[str]:
    evaluation = profile_dir / "evaluation_results" / "formal"
    score = _read_object(evaluation / "style_eval_current.json")
    candidate = evaluation / "platform_agent_candidate.md"
    errors: list[str] = []
    if score.get("schema") != "literary-engineering-workbench/style-eval/v0.1":
        errors.append("style review requires a valid deterministic score")
    if not candidate.is_file() or str(score.get("candidate_sha256") or "") != _sha256(candidate):
        errors.append("style deterministic score is stale for the evaluation candidate")
    try:
        overall = float(score.get("overall_score") or 0)
    except (TypeError, ValueError):
        overall = 0.0
    risk = str(score.get("risk_level") or "").strip().lower()
    if overall < 45 or risk in {"high_copy_risk", "low_similarity"}:
        errors.append(f"style deterministic score is not accepted: score={overall}; risk={risk or 'missing'}")
    return errors


def _review_skeleton(target_id: str, evidence: dict[str, str]) -> dict[str, object]:
    return {
        "schema": STYLE_REVIEW_SCHEMA,
        "status": "pending_agent_judgment",
        "profile_id": target_id,
        "evidence": evidence,
        "prompt_writer_session_id": _writer_identity(target_id, "style-prompt-agent-task"),
        "evaluation_writer_session_id": _writer_identity(target_id, "style-eval-agent-task"),
        "reviewer_session_id": "",
        "verdict": "pending",
        "summary": "",
        "checked_dimensions": list(STYLE_REVIEW_DIMENSIONS),
        "findings": [],
        "required_changes": [],
        "effectiveness_assessment": "",
        "copy_risk_assessment": "",
        "evidence_limitations": [],
        "review_report_path": "",
        "review_report_sha256": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _review_instruction(root: Path, paths: StyleReviewPaths, digest_lines: str) -> str:
    review_json = relative_path(paths.review_json, root)
    review_md = relative_path(paths.review_markdown, root)
    return (
        f"读取安全证据和 `{review_json}` 的固定结构，独立审查候选文风提示词是否可执行、"
        "是否真实复现叙事机制、确定性评测是否支持结论、原创性边界是否可靠，并填写 "
        f"`{review_json}` 与 `{review_md}`。\n\n"
        "verdict 只能是 pass/revise/block。有必须修改的事项时必须 revise 或 block，不能 pass_with_notes。"
        "不得修改 evidence、session id、checked_dimensions、report path/digest 或其他机器字段；"
        "Studio Worker 会在预检时绑定这些值。不要读取、复述或猜测 holdout 原文，不要输出思维链。\n\n"
        "当前机器摘要：\n" + (digest_lines or "- 无")
    )


def _review_markdown_skeleton(target_id: str) -> str:
    return (
        "# 文风工程独立语义审查\n\n"
        f"- Profile：`{target_id}`\n"
        "- 结论：`pending`\n\n"
        "## 审查摘要\n\n待独立 Reviewer 填写。\n\n"
        "## 有效性与文学可用性\n\n待填写。\n\n"
        "## 原创性边界\n\n待填写。\n\n"
        "## 问题与必要修改\n\n- 待填写。\n"
    )


def _source_set_sha256(profile_dir: Path) -> str:
    session = load_style_session(profile_dir)
    if session:
        payload = {
            "request_digest": session.get("request_digest"),
            "training_sources": session.get("training_sources"),
            "holdout_sources": session.get("holdout_sources"),
        }
        return hashlib.sha256(_canonical_json(payload)).hexdigest()
    manifest = profile_dir / "corpus_manifest.yaml"
    return _sha256(manifest) if manifest.is_file() else ""


def _writer_identity(target_id: str, state: str) -> str:
    return f"studio:writer:{task_id('style-engineering', target_id, state)}"


def _inside(root: Path, value: Path) -> Path:
    path = value if value.is_absolute() else root / value
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("style profile directory must be inside the work project")
    return resolved


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
