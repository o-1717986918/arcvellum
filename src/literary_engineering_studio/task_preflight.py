"""Deterministic sandbox checks run before formal project writeback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .contracts import TaskPackage
from .sandbox import SandboxManifest, sandbox_change_issues


COMPLETION_SCHEMA = "literary-engineering-workbench/agent-task-completion/v1"
REVIEW_CONCLUSION = re.compile(
    r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
    re.IGNORECASE,
)
REVIEW_CONCLUSION_VARIANT = re.compile(
    r"(?mi)^(?:#{1,6}\s*)?-?\s*(?:审查)?结论[：:]\s*(?:\*\*)?`?"
    r"(pass|revise_required|reject)`?(?:\*\*)?\s*$"
)


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    path: str
    message: str
    repair: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PreflightResult:
    passed: bool
    issues: tuple[PreflightIssue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "issue_count": len(self.issues), "issues": [item.as_dict() for item in self.issues]}

    def repair_prompt(self, attempt: int, maximum: int) -> str:
        rows = "\n".join(
            f"{index}. [{item.code}] `{item.path}`：{item.message}\n   修复要求：{item.repair}"
            for index, item in enumerate(self.issues, start=1)
        )
        return f"""# Studio Preflight Repair {attempt}/{maximum}

你刚完成的沙箱产物未通过确定性预检。只修复下列明确问题，不改变已经成立的创作判断，也不要为了显示 pass 而伪造审查结论。

{rows}

仍然只能修改 Allowed Outputs。修复后逐项重新读取目标文件并核对精确格式，然后结束；Studio 会再次运行预检。
"""


def canonicalize_task_outputs(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Normalize semantically identical machine markers without changing a review verdict."""

    changes = _canonicalize_scene_candidate_manifest(task, sandbox)
    changes.extend(_canonicalize_scene_review_metadata(task, sandbox))
    gates = " ".join(str(item) for item in task.payload.get("validation_gates") or []).lower()
    if "conclusion is pass" not in gates and "结论" not in gates:
        return changes
    for relative in task.expected_outputs:
        if not relative.endswith(".md") or "review" not in relative.lower() or "agent_tasks" in relative.lower():
            continue
        path = sandbox.workspace / Path(relative)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if REVIEW_CONCLUSION.search(text):
            continue
        matches = list(REVIEW_CONCLUSION_VARIANT.finditer(text))
        if len(matches) != 1:
            continue
        verdict = matches[0].group(1).lower()
        normalized = text[: matches[0].start()] + f"- 结论： {verdict}" + text[matches[0].end() :]
        path.write_text(normalized, encoding="utf-8")
        changes.append({"path": relative, "verdict": verdict})
    return changes


def _canonicalize_scene_review_metadata(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Fill deterministic identity fields for a scene review without changing its judgement.

    A review Agent supplies the verdict and evidence.  The candidate digest,
    scene id, schema discriminator, and source list are task-owned facts.  By
    restoring those facts before validation, the repair loop can focus on
    genuinely missing review evidence instead of wasting a model turn on a
    copied hash or a guessed schema label.
    """

    if task.current_state not in {"candidate-review", "agent-review-task"}:
        return []
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
    review_path = sandbox.workspace / Path(review_rel)
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
    if not review_path.is_file() or not candidate_path.is_file():
        return []
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(payload, dict) or not str(payload.get("conclusion") or "").strip() or not str(payload.get("summary") or "").strip():
        return []

    expected = {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": str(task.payload.get("scene_id") or task.scene_id or "").strip(),
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "source_paths": [str(item).replace("\\", "/") for item in task.source_paths],
    }
    changed: list[str] = []
    for field, value in expected.items():
        if payload.get(field) == value:
            continue
        payload[field] = value
        changed.append(field)
    if not changed:
        return []
    review_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [{"path": review_rel, "field": field, "reason": "normalized deterministic scene-review metadata"} for field in changed]


def _canonicalize_scene_candidate_manifest(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Fill system-owned candidate metadata that an Agent must not improvise.

    The prose and its creative decisions remain Agent-authored.  Stable paths,
    the prompt fingerprint, and the registration of already-emitted candidate
    character assets are deterministic task facts, so normalizing them prevents
    avoidable JSON-shape failures without weakening the downstream review gate.
    """

    if task.current_state not in {"candidate-generation-provenance", "generation-agent-task", "candidate-revision", "static-revision"}:
        return []
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
    if not candidate_rel:
        return []
    manifest_rel = candidate_rel[:-3] + ".json" if candidate_rel.endswith(".md") else candidate_rel + ".json"
    manifest_path = sandbox.workspace / Path(manifest_rel)
    if not manifest_path.is_file():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(payload, dict):
        return []

    changes: list[dict[str, str]] = []
    required_assets = task.payload.get("scene_character_assets")
    if not isinstance(payload.get("new_character_register"), dict):
        introduced = []
        ready = True
        if isinstance(required_assets, list):
            for item in required_assets:
                if not isinstance(item, dict):
                    continue
                candidate_path = str(item.get("candidate_path") or "").replace("\\", "/").strip()
                if candidate_path and not (sandbox.workspace / Path(candidate_path)).is_file():
                    ready = False
                introduced.append(
                    {
                        "name": str(item.get("name") or item.get("candidate_id") or "").strip(),
                        "character_id": str(item.get("candidate_id") or "").strip(),
                        "scene_function": "declared scene participant",
                        "persistence": "named",
                        "already_in_characters": False,
                        "formal_character_path": str(item.get("formal_character_path") or "").strip(),
                        "candidate_path": candidate_path,
                        "review_path": "",
                        "approval_run_id": "",
                        "promotion_manifest": "",
                        "waiver_reason": "",
                    }
                )
        payload["new_character_register"] = {
            "schema": "literary-engineering-workbench/new-character-register/v0.1",
            "status": "candidates_ready" if introduced and ready else ("needs_candidate" if introduced else "none"),
            "introduced": introduced,
            "ephemeral_waivers": [],
            "blocking_issues": [] if ready else ["declared scene character candidate is missing"],
        }
        changes.append({"path": manifest_rel, "field": "new_character_register", "reason": "normalized deterministic scene-character contract"})

    prompt_rel = candidate_rel[:-3] + ".prompt.json" if candidate_rel.endswith(".md") else candidate_rel + ".prompt.json"
    prompt_path = sandbox.workspace / Path(prompt_rel)
    if prompt_path.is_file():
        try:
            prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            prompt = {}
        standards = prompt.get("generation_standards") if isinstance(prompt, dict) and isinstance(prompt.get("generation_standards"), dict) else {}
        digest = str(standards.get("creative_quality_profile_digest") or "").strip()
        if digest and not str(payload.get("creative_quality_profile_digest") or "").strip():
            payload["creative_quality_profile_digest"] = digest
            changes.append({"path": manifest_rel, "field": "creative_quality_profile_digest", "reason": "copied from protected prompt manifest"})
        if "reader_experience_contract" not in payload and isinstance(standards.get("reader_experience_contract"), dict):
            payload["reader_experience_contract"] = standards["reader_experience_contract"]
            changes.append({"path": manifest_rel, "field": "reader_experience_contract", "reason": "copied from protected prompt manifest"})
        if "narrative_rhythm_contract" not in payload and isinstance(standards.get("narrative_rhythm_contract"), dict):
            payload["narrative_rhythm_contract"] = standards["narrative_rhythm_contract"]
            changes.append({"path": manifest_rel, "field": "narrative_rhythm_contract", "reason": "copied from protected prompt manifest"})

    if changes:
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes


def validate_task_outputs(task: TaskPackage, sandbox: SandboxManifest) -> PreflightResult:
    issues: list[PreflightIssue] = []
    for message in sandbox_change_issues(sandbox):
        issues.append(PreflightIssue("unexpected-change", "workspace", message, "撤销所有不属于 Allowed Outputs 的修改。"))

    for relative in task.expected_outputs:
        path = sandbox.workspace / Path(relative)
        if not path.exists():
            issues.append(PreflightIssue("missing-output", relative, "预期产物不存在。", "创建该产物并按 Output Contract 填写完整内容。"))
            continue
        if path.is_file() and path.stat().st_size == 0:
            issues.append(PreflightIssue("empty-output", relative, "预期产物为空。", "写入任务要求的完整内容。"))
            continue
        if path.is_file() and path.suffix.lower() == ".json":
            _validate_json(relative, path, issues)

    _validate_completion_markers(task, sandbox, issues)
    _validate_review_conclusions(task, sandbox, issues)
    _validate_asset_candidate(task, sandbox, issues)
    _validate_asset_review_contract(task, sandbox, issues)
    _validate_project_review_contract(task, sandbox, issues)
    _validate_scene_review_contract(task, sandbox, issues)
    _validate_scene_candidate_generation_contract(task, sandbox, issues)
    _validate_scene_revision_contract(task, sandbox, issues)
    _validate_source_extraction_revision(task, sandbox, issues)
    return PreflightResult(not issues, tuple(issues))


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


def _validate_json(relative: str, path: Path, issues: list[PreflightIssue]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        issues.append(PreflightIssue("invalid-json", relative, f"JSON 无法解析：{exc}", "修正 JSON 语法；不要使用 Markdown 代码围栏。"))
        return
    if not isinstance(payload, (dict, list)):
        issues.append(PreflightIssue("invalid-json-root", relative, "JSON 根节点必须是对象或数组。", "按任务合同改为结构化 JSON。"))


def _validate_asset_candidate(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Run the core asset schema before a candidate can reach writeback."""

    gates = " ".join(str(item) for item in task.payload.get("validation_gates") or []).lower()
    if task.payload.get("task_type") != "platform-agent-asset-creation" and "candidate schema validates" not in gates:
        return
    candidate = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if not candidate:
        candidate = next(
            (
                relative
                for relative in task.expected_outputs
                if relative.endswith(".json") and not relative.endswith(".agent_completion.json")
            ),
            "",
        )
    if not candidate:
        return
    path = sandbox.workspace / Path(candidate)
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return

    from literary_engineering_studio_engine.agent_schema import validate_payload
    from literary_engineering_studio_engine.asset_workshop import ASSET_SCHEMA_NAMES

    asset_type = str(task.payload.get("asset_type") or payload.get("asset_type") or "").strip()
    schema_name = ASSET_SCHEMA_NAMES.get(asset_type, "")
    if not schema_name:
        issues.append(
            PreflightIssue(
                "unknown-asset-schema",
                candidate,
                f"无法确定资产类型 `{asset_type or 'missing'}` 对应的 schema。",
                "读取任务包中的 asset_type 和 Source Artifacts，按声明的资产类型重写候选 JSON。",
            )
        )
        return
    schema_errors, _warnings = validate_payload(payload, schema_name)
    for item in schema_errors:
        field = str(item.get("path") or "schema")
        message = str(item.get("message") or "schema validation failed")
        issues.append(
            PreflightIssue(
                "asset-schema-invalid",
                f"{candidate}#{field}",
                message,
                f"按 `{schema_name}` 修复字段 `{field}`；字段必须位于 JSON 根对象且类型、固定值与 schema 完全一致。",
            )
        )
    metadata_contract = {
        "candidate_id": str,
        "risks": list,
        "source_paths": list,
        "promotion_notes": str,
    }
    for field, expected_type in metadata_contract.items():
        value = payload.get(field)
        valid = isinstance(value, expected_type) and (expected_type is not str or bool(value.strip()))
        if valid:
            continue
        expected_label = "字符串" if expected_type is str else "数组"
        issues.append(
            PreflightIssue(
                "asset-metadata-invalid",
                f"{candidate}#{field}",
                f"字段 `{field}` 必须是非空{expected_label}。",
                f"把 `{field}` 改为{expected_label}；不要用对象替代 schema 要求的字符串。",
            )
        )


def _validate_completion_markers(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    for relative in task.expected_outputs:
        if not relative.endswith(".agent_completion.json"):
            continue
        path = sandbox.workspace / Path(relative)
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        completion_base = relative[: -len(".agent_completion.json")]
        expected_task = completion_base + (".md" if completion_base.endswith(".agent_tasks") else ".agent_tasks.md")
        errors: list[str] = []
        revision_reset = task.current_state in {"asset-review-pass", "asset-approval-revision", "canon-review-pass", "committee-pass"}
        if not isinstance(payload, dict):
            errors.append("根节点不是对象")
        else:
            if payload.get("schema") != COMPLETION_SCHEMA:
                errors.append(f"schema 必须是 {COMPLETION_SCHEMA}")
            status = str(payload.get("status") or "").lower()
            if revision_reset:
                if status != "recheck_required":
                    errors.append("资产修订后的审查完成标记 status 必须为 recheck_required")
                if payload.get("expected_artifacts_checked") is not False:
                    errors.append("资产修订后的 expected_artifacts_checked 必须为 false，等待独立复审")
            else:
                if status not in {"complete", "completed", "done", "handled", "pass"}:
                    errors.append("status 必须表示 complete")
                if payload.get("expected_artifacts_checked") is not True:
                    errors.append("expected_artifacts_checked 必须为 true")
            if str(payload.get("source_task") or "").replace("\\", "/") != expected_task:
                errors.append(f"source_task 必须精确为 {expected_task}")
        if errors:
            issues.append(
                PreflightIssue(
                    "invalid-completion-evidence",
                    relative,
                    "；".join(errors),
                    (
                        "将旧审查完成证据重置为 recheck_required，并保持 expected_artifacts_checked=false，等待新的独立审查。"
                        if revision_reset
                        else "按完成标记 schema 修复字段；确认其他产物后再保留 complete 状态。"
                    ),
                )
            )


def _validate_asset_review_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    task_type = str(task.payload.get("task_type") or "")
    if task_type not in {"platform-agent-asset-review", "platform-agent-revision"}:
        return
    review_rel = next(
        (
            relative
            for relative in task.expected_outputs
            if relative.replace("\\", "/").startswith("reviews/assets/")
            and relative.endswith("_review.json")
        ),
        "",
    )
    if not review_rel:
        return
    path = sandbox.workspace / Path(review_rel)
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return

    def add(field: str, message: str, repair: str) -> None:
        issues.append(PreflightIssue("asset-review-invalid", f"{review_rel}#{field}", message, repair))

    expected_schema = "literary-engineering-workbench/candidate-asset-review/v0.1"
    if payload.get("schema") != expected_schema:
        add("schema", f"schema 必须精确为 `{expected_schema}`。", "改正 schema 固定值，不要自造版本。")
    for field in ("candidate", "candidate_id", "asset_type"):
        if not isinstance(payload.get(field), str) or not str(payload.get(field) or "").strip():
            add(field, f"字段 `{field}` 必须是非空字符串。", f"从任务包与候选文件中填写精确的 `{field}`。")
    for field in ("blocking_issues", "warnings", "revision_actions", "promotion_risks"):
        if not isinstance(payload.get(field), list):
            add(field, f"字段 `{field}` 必须是数组。", f"将 `{field}` 写为数组；没有内容时使用 []。")

    status = str(payload.get("status") or "").strip().lower()
    if task.current_state in {"asset-review-pass", "asset-approval-revision"}:
        if status != "recheck_required":
            add(
                "status",
                "修订任务不得自行把旧审查改成 pass；status 必须是 recheck_required。",
                "把 status 改为 recheck_required，并让下一轮独立审查重新裁决。",
            )
        applied = payload.get("applied_revision_actions")
        if not isinstance(applied, list) or not applied:
            add(
                "applied_revision_actions",
                "必须逐项记录已经落实的修订动作。",
                "把原 review 的每条阻塞项和 revision_action 对应到具体修改证据。",
            )
        revision_round = payload.get("revision_round")
        if not isinstance(revision_round, int) or isinstance(revision_round, bool) or revision_round < 1:
            add("revision_round", "revision_round 必须是 >= 1 的整数。", "记录当前正式修订轮次。")
        return

    allowed = {"pass", "failed", "revise_required"}
    if status not in allowed:
        add("status", f"审查 status 必须是 {sorted(allowed)} 之一。", "按真实审查结论选择状态，不要伪造 pass。")
        return
    blocking = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
    revisions = payload.get("revision_actions") if isinstance(payload.get("revision_actions"), list) else []
    candidate = str(payload.get("candidate") or task.payload.get("candidate") or "").replace("\\", "/").strip()
    for index, action in enumerate(revisions):
        if not isinstance(action, dict):
            add(f"revision_actions[{index}]", "修订动作必须是对象。", "写出 target、action/description 和可验证条件。")
            continue
        target = str(action.get("target") or candidate).replace("\\", "/").strip()
        target_file = target.split("#", 1)[0]
        if candidate and target_file != candidate:
            add(
                f"revision_actions[{index}].target",
                f"资产审查不得用跨任务目标 `{target}` 阻塞当前候选 `{candidate}`。",
                "把跨任务依赖移入 warnings 或 promotion_risks；revision_actions 只保留能在当前候选文件内完成的修改。",
            )
    if status == "pass" and (blocking or revisions):
        add("status", "pass 不能同时保留 blocking_issues 或 revision_actions。", "保留问题并改为 revise_required，或真实解决后由新一轮审查裁决。")
    if status in {"failed", "revise_required"} and not blocking and not revisions:
        add("revision_actions", "非通过结论必须给出至少一条可执行问题或修订动作。", "写出具体、可验证、可复审的修改要求。")


def _validate_project_review_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    state = task.current_state
    if state not in {"canon-review-agent-task", "canon-review-pass", "committee-agent-task", "committee-pass"}:
        return
    committee = state.startswith("committee")
    relative = (
        "reviews/agent/committee_project-final-audit.json"
        if committee
        else "reviews/agent/canon_review.json"
    )
    path = sandbox.workspace / relative
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return

    def add(field: str, message: str, repair: str) -> None:
        issues.append(PreflightIssue("project-review-invalid", f"{relative}#{field}", message, repair))

    if state in {"canon-review-pass", "committee-pass"}:
        verdict_field = "final_recommendation" if committee else "conclusion"
        if str(payload.get(verdict_field) or "").strip().lower() != "recheck_required":
            add(verdict_field, "修订任务不能自行判定通过，必须重置为 recheck_required。", "修复正式目标后等待新的独立审查。")
        if not isinstance(payload.get("applied_repair_actions"), list) or not payload.get("applied_repair_actions"):
            add("applied_repair_actions", "必须记录已落实的项目修复动作。", "逐项写明 target_path、修改内容和验证证据。")
        targets = [str(item) for item in task.payload.get("repair_targets") or [] if str(item).strip()]
        if not targets:
            add("repair_targets", "修订任务没有可写的精确目标。", "让上一轮审查为每个行动项补充合法 target_path 后重新领取任务。")
        before = task.payload.get("repair_target_sha256_before_revision")
        hashes = before if isinstance(before, dict) else {}
        changed = False
        for target in targets:
            target_path = sandbox.workspace / Path(target)
            if not target_path.is_file():
                add("repair_targets", f"修复目标 `{target}` 未生成。", "创建或修改该精确目标文件，不能只改审查报告。")
                continue
            previous = str(hashes.get(target) or "")
            current = hashlib.sha256(target_path.read_bytes()).hexdigest()
            if not previous or current != previous:
                changed = True
        if targets and not changed:
            add("repair_targets", "没有任何声明的项目目标发生实质变化。", "落实至少一项真实修复；修改审查标签不能代替项目修改。")
        return

    verdict_field = "final_recommendation" if committee else "conclusion"
    verdict = str(payload.get(verdict_field) or "").strip().lower()
    allowed = {"approve", "approve_with_notes", "revise", "reject"} if committee else {"pass", "pass_with_notes", "revise_required", "reject"}
    if verdict not in allowed:
        add(verdict_field, f"审查结论必须是 {sorted(allowed)} 之一。", "如实记录结论；非通过结论本身可以完成本轮审查。")
        return
    if (committee and verdict == "approve") or (not committee and verdict == "pass"):
        return
    action_fields = ("action_items", "disagreements") if committee else ("recommendations",)
    actionable: list[dict[str, object]] = []
    for field in action_fields:
        values = payload.get(field) if isinstance(payload.get(field), list) else []
        actionable.extend(item for item in values if isinstance(item, dict))
    if not actionable:
        add(action_fields[0], "非通过结论必须提供至少一个结构化修复动作。", "为修复动作写出 target_path、action 和 verification。")
        return
    allowed_prefixes = ("canon/", "characters/", "plot/", "scenes/", "drafts/candidates/")
    for index, item in enumerate(actionable):
        target = str(item.get("target_path") or item.get("target") or "").replace("\\", "/").strip()
        target_file = target.split("#", 1)[0]
        valid = (
            target_file.startswith(allowed_prefixes)
            and not Path(target_file).is_absolute()
            and ".." not in Path(target_file).parts
            and Path(target_file).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".csv"}
        )
        if not valid:
            add(
                f"{action_fields[0]}[{index}].target_path",
                f"修复目标 `{target or 'missing'}` 不是允许的精确项目文件。",
                "使用 canon/、characters/、plot/、scenes/ 或 drafts/candidates/ 下的单个文本文件路径；不能写目录或 review/workflow 路径。",
            )


def _validate_scene_revision_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    if task.current_state not in {"candidate-revision", "static-revision"}:
        return

    def add(path: str, message: str, repair: str) -> None:
        issues.append(PreflightIssue("scene-revision-invalid", path, message, repair))

    candidate_rel = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if not candidate_rel:
        candidate_rel = next((item for item in task.expected_outputs if item.endswith("_revision.md") and "report" not in item), "")
    candidate = sandbox.workspace / Path(candidate_rel)
    previous = str(task.payload.get("candidate_sha256_before_revision") or "").strip().lower()
    if candidate.is_file() and previous and hashlib.sha256(candidate.read_bytes()).hexdigest() == previous:
        add(candidate_rel, "修订正文与被审查候选完全相同。", "对正文落实真实语义修改；不能只更新报告和 manifest。")

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
    if payload.get("schema") != "literary-engineering-workbench/scene-revision/v0.1":
        add(manifest_rel + "#schema", "scene revision schema 不正确。", "使用固定 schema literary-engineering-workbench/scene-revision/v0.1。")
    if payload.get("ready_for_review") is not False:
        add(manifest_rel + "#ready_for_review", "修订任务不能自行声明已审查通过。", "设为 false，并交给新的 exact-candidate AgentReview。")
    if payload.get("anti_evasion_protocol_applied") is not True:
        add(manifest_rel + "#anti_evasion_protocol_applied", "未记录反规避修订协议。", "执行语义级反规避检查并设为 true。")
    applied_fields = ("revision_actions_applied", "warnings_addressed", "style_notes_addressed", "style_adherence_addressed")
    if not any(payload.get(field) for field in applied_fields):
        add(manifest_rel, "没有记录任何已落实的审查修复。", "逐项记录 review finding 对应的正文改动。")


def _validate_source_extraction_revision(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    supported = (
        task.route == "source-ingest" and task.current_state == "extraction-review"
    ) or (
        task.route == "longform-planning"
        and task.current_state in {"budget-review", "scene-inventory-review", "chapter-obligation-review"}
    ) or (
        task.route == "review-and-audit" and task.current_state == "canon-patch-revision"
    ) or (
        task.route == "style-engineering" and task.current_state == "style-eval-revision"
    )
    if not supported:
        return
    targets = [str(item) for item in task.payload.get("repair_targets") or [] if str(item).strip()]
    before = task.payload.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    changed = False
    for target in targets:
        path = sandbox.workspace / Path(target)
        if not path.is_file():
            continue
        previous = str(hashes.get(target) or "")
        if previous and hashlib.sha256(path.read_bytes()).hexdigest() != previous:
            changed = True
            break
    if not targets or not changed:
        issues.append(
            PreflightIssue(
                "declared-repair-target-unchanged",
                "repair_targets",
                "返工没有修改任何声明的候选文件。",
                "按 review 修订至少一个候选文件；不能只把审查结论改成 pass。",
            )
        )


def _validate_review_conclusions(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    gates = " ".join(str(item) for item in task.payload.get("validation_gates") or []).lower()
    if "conclusion is pass" not in gates and "结论" not in gates:
        return
    candidates = [
        relative
        for relative in task.expected_outputs
        if relative.endswith(".md") and "review" in relative.lower() and "agent_tasks" not in relative.lower()
    ]
    for relative in candidates:
        path = sandbox.workspace / Path(relative)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = REVIEW_CONCLUSION.search(text)
        if not match:
            issues.append(
                PreflightIssue(
                    "missing-machine-conclusion",
                    relative,
                    "没有找到以 `- 结论：` 开头的独占机器行；标题或普通段落不能替代。",
                    "在报告中加入独占一行，例如 `- 结论： pass`、`- 结论： revise_required` 或 `- 结论： reject`。",
                )
            )
        elif "conclusion is pass" in gates and match.group(1).lower() != "pass":
            issues.append(
                PreflightIssue(
                    "review-not-pass",
                    relative,
                    f"当前正式门禁要求 pass，报告结论为 {match.group(1)}。",
                    "批判性修订对应候选产物并重新审查；只有阻塞问题确实消失后才把机器行改为 pass。",
                )
            )
