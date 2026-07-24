"""Candidate asset creation and asset-review preflight gates."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from .common import PreflightIssue
from ..sandbox import SandboxManifest


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
