"""Scene candidate, review, and revision preflight gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..contracts import TaskPackage
from .common import PreflightIssue
from ..sandbox import SandboxManifest


def _validate_scene_review_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Reject a prose-like review JSON before it can reach the CLI promotion gate."""

    if task.current_state not in {"candidate-review", "agent-review-task"}:
        return
    review_rel = next(
        (
            relative
            for relative in task.expected_outputs
            if relative.endswith(".json")
            and "scene_review" in relative
            and not relative.endswith(".agent_completion.json")
        ),
        "",
    )
    if not review_rel:
        return
    review_path = sandbox.workspace / Path(review_rel)
    if not review_path.is_file():
        return
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return

    from literary_engineering_studio_engine.agent_schema import validate_payload

    schema_errors, _warnings = validate_payload(payload, "scene_review.v1")
    for error in schema_errors:
        field = str(error.get("path") or "schema")
        message = str(error.get("message") or "scene review schema validation failed")
        issues.append(
            PreflightIssue(
                "scene-review-schema-invalid",
                f"{review_rel}#{field}",
                message,
                "读取 CLI Protected Outputs 中的 scene review sidecar 和 scene_review.v1 schema；保留真实审查结论，仅补齐缺失字段、正确类型与固定 schema 值。",
            )
        )

    candidate_rel = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if not candidate_rel:
        candidate_rel = next(
            (
                relative
                for relative in task.source_paths
                if relative.replace("\\", "/").startswith("drafts/candidates/") and relative.endswith(".md")
            ),
            "",
        )
    candidate_path = sandbox.workspace / Path(candidate_rel)
    if candidate_rel and candidate_path.is_file():
        expected_digest = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
        if str(payload.get("candidate_sha256") or "") != expected_digest:
            issues.append(
                PreflightIssue(
                    "scene-review-candidate-digest-mismatch",
                    f"{review_rel}#candidate_sha256",
                    "candidate_sha256 未精确对应本任务候选正文。",
                    "从任务包的候选正文重新计算或复制精确 SHA-256；不得写示例值、旧值或自造摘要。",
                )
            )
        source_paths = payload.get("source_paths") if isinstance(payload.get("source_paths"), list) else []
        normalized_sources = {str(item).replace("\\", "/") for item in source_paths}
        if candidate_rel not in normalized_sources:
            issues.append(
                PreflightIssue(
                    "scene-review-candidate-source-missing",
                    f"{review_rel}#source_paths",
                    "source_paths 必须引用本任务的精确候选正文。",
                    f"在 source_paths 中保留 `{candidate_rel}`；不要引用其他候选、正式草稿或笼统目录。",
                )
            )


def _validate_scene_candidate_generation_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Run candidate-specific quality gates before a worker can request writeback.

    Candidate generation is an Agent-authored task.  Its provenance, new
    character declaration, punctuation/style lint, word budget, and reader
    contract must therefore be visible to the runner's repair loop instead of
    first failing after temporary files have been imported into the project.
    """
    supported_states = {"candidate-generation-provenance", "generation-agent-task", "candidate-revision", "static-revision"}
    if task.current_state not in supported_states:
        return
    if task.current_state in {"candidate-revision", "static-revision"} and not any(
        relative.endswith(".prompt.json") for relative in task.core_managed_outputs
    ):
        return
    candidate_rel = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if not candidate_rel:
        candidate_rel = next(
            (
                relative
                for relative in task.expected_outputs
                if relative.endswith(".md") and "agent_tasks" not in relative and "prompt" not in relative
            ),
            "",
        )
    candidate = sandbox.workspace / Path(candidate_rel)
    if not candidate_rel or not candidate.is_file():
        return

    from literary_engineering_studio_engine.anti_ai_style import style_lint_gate, style_lint_gate_message
    from literary_engineering_studio_engine.agent_schema import validate_payload
    from literary_engineering_studio_engine.asset_workshop import ASSET_SCHEMA_NAMES
    from literary_engineering_studio_engine.candidate_promotion import candidate_generation_gate
    from literary_engineering_studio_engine.creative_quality import load_creative_quality_profile
    from literary_engineering_studio_engine.draft_text import final_body_from_draft_path
    from literary_engineering_studio_engine.reader_experience import reader_experience_adherence_for_body
    from literary_engineering_studio_engine.word_budget import word_budget_adherence_for_body

    scene_assets = task.payload.get("scene_character_assets")
    if isinstance(scene_assets, list):
        for item in scene_assets:
            if not isinstance(item, dict):
                continue
            asset_rel = str(item.get("candidate_path") or "").replace("\\", "/").strip()
            if not asset_rel:
                continue
            asset_path = sandbox.workspace / Path(asset_rel)
            if not asset_path.is_file():
                continue
            try:
                asset_payload = json.loads(asset_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            errors, _warnings = validate_payload(asset_payload, ASSET_SCHEMA_NAMES["character"])
            if errors:
                issues.append(
                    PreflightIssue(
                        "scene-character-candidate-invalid",
                        asset_rel,
                        "角色候选未通过 character_profile.v1 schema：" + "; ".join(str(error) for error in errors[:5]),
                        "按该角色候选 sidecar 的 schema 合同补齐候选 JSON；不得把角色档案写入正式 characters/。",
                    )
                )

    scene_id = str(task.payload.get("scene_id") or task.scene_id or Path(candidate_rel).stem.split("-")[0])
    provenance = candidate_generation_gate(sandbox.workspace, scene_id, candidate)
    if provenance.get("status") != "pass":
        detail = str(provenance.get("message") or "candidate generation provenance is invalid")
        invalid = provenance.get("invalid")
        if isinstance(invalid, list) and invalid:
            detail += ": " + "; ".join(str(item) for item in invalid)
        issues.append(
            PreflightIssue(
                "candidate-provenance-invalid",
                candidate_rel,
                detail,
                "修正候选 manifest 的 provenance、canon 声明和 new_character_register；不能把 blocking_issues 留为非空，也不能伪造已有角色。",
            )
        )

    body = final_body_from_draft_path(candidate)
    if not body:
        return
    lint = style_lint_gate(body, profile=load_creative_quality_profile(sandbox.workspace), scope=scene_id)
    if lint.get("status") == "blocking":
        issues.append(
            PreflightIssue(
                "candidate-style-lint-blocking",
                candidate_rel,
                style_lint_gate_message(lint),
                "逐句重写命中的正文。不得只替换标点、把“不是……而是……”改成同义对照，或用另一种模板转折规避检测。",
            )
        )
    scene_path = sandbox.workspace / "scenes" / f"{scene_id}.yaml"
    budget = word_budget_adherence_for_body(
        sandbox.workspace,
        scene_path,
        body,
        materialization_scope="scene",
    )
    if budget.get("status") not in {"pass", "not_required"}:
        issues.append(
            PreflightIssue(
                "candidate-word-budget-invalid",
                candidate_rel,
                str(budget.get("message") or "candidate failed the scene word budget"),
                "在不灌水、不重复情绪描写的前提下扩写或压缩正文，使清洁正文达到当前场景的中文内容字符预算。",
            )
        )
    reader = reader_experience_adherence_for_body(sandbox.workspace, scene_path, body)
    if reader.get("status") not in {"pass", "not_required"}:
        issues.append(
            PreflightIssue(
                "candidate-reader-contract-invalid",
                candidate_rel,
                str(reader.get("message") or "candidate failed the reader-experience contract"),
                "重写正文以兑现本场读者问题、承诺和场景桥接；不要只改 manifest 描述。",
            )
        )


def _validate_scene_revision_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    if task.current_state not in {"candidate-revision", "static-revision"}:
        return

    candidate_rel = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if not candidate_rel:
        candidate_rel = next((item for item in task.expected_outputs if item.endswith("_revision.md") and "report" not in item), "")
    candidate = sandbox.workspace / Path(candidate_rel)
    manifest_rel = next((item for item in task.expected_outputs if item.endswith("_revision.json")), "")
    if not manifest_rel:
        return
    manifest_path = sandbox.workspace / Path(manifest_rel)
    if not manifest_path.is_file():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return
    for path, message, repair in _revision_preflight_errors(task, sandbox, candidate_rel, candidate, payload):
        issues.append(PreflightIssue("scene-revision-invalid", path, message, repair))


def _revision_preflight_errors(
    task: TaskPackage,
    sandbox: SandboxManifest,
    candidate_rel: str,
    candidate: Path,
    payload: dict[str, object],
) -> list[tuple[str, str, str]]:
    from literary_engineering_studio_engine.creative_quality import load_creative_quality_profile
    from literary_engineering_studio_engine.draft_text import final_body_from_draft_path
    from literary_engineering_studio_engine.literary.scene.promotion.revision_contract import (
        revision_manifest_errors,
        revision_source_requires_anti_evasion_rows,
    )

    previous = str(task.payload.get("candidate_sha256_before_revision") or "").strip().lower()
    source_rel = str(task.payload.get("revision_source") or "").replace("\\", "/").strip()
    source = sandbox.workspace / Path(source_rel)
    if not (source.is_file() and candidate.is_file()):
        return []
    errors = _revision_file_errors(source_rel, source, candidate_rel, candidate, previous)
    contract_errors = revision_manifest_errors(
        payload,
        scene_id=str(task.payload.get("scene_id") or task.scene_id or candidate.stem.replace("_revision", "")),
        source_rel=source_rel,
        source_sha256=previous,
        source_body=final_body_from_draft_path(source),
        candidate_rel=candidate_rel,
        candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
        candidate_body=final_body_from_draft_path(candidate),
        anti_evasion_rows_required=revision_source_requires_anti_evasion_rows(source,
            quality_profile=load_creative_quality_profile(sandbox.workspace),
            scene_id=str(task.payload.get("scene_id") or task.scene_id or ""),
        ),
    )
    manifest_rel = next((item for item in task.expected_outputs if item.endswith("_revision.json")), "")
    errors.extend(
        (manifest_rel, message, "按 revision prompt 的 exact-source 与 anti_evasion_rows 契约修正 manifest；不得伪造摘要或换皮修订。")
        for message in contract_errors
    )
    return errors


def _revision_file_errors(
    source_rel: str,
    source: Path,
    candidate_rel: str,
    candidate: Path,
    previous: str,
) -> list[tuple[str, str, str]]:
    errors: list[tuple[str, str, str]] = []
    if previous and hashlib.sha256(source.read_bytes()).hexdigest() != previous:
        errors.append((source_rel, "修订源文件已变化，当前任务包的源摘要已过期。", "重新领取 candidate-revision 任务，不能修订旧版本。"))
    if previous and hashlib.sha256(candidate.read_bytes()).hexdigest() == previous:
        errors.append((candidate_rel, "修订正文与被审查候选完全相同。", "对正文落实真实语义修改；不能只更新报告和 manifest。"))
    return errors
