"""Machine-owned metadata canonicalization for formal asset workflows."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .asset_evidence import review_machine_fields
from .asset_review_metadata import (
    canonicalize_asset_review_action_targets,
    flatten_asset_review_envelope,
)
from .canonicalization_common import read_object, write_machine_fields


_ASSET_TASK_TYPES = {
    "platform-agent-asset-creation",
    "platform-agent-asset-review",
    "platform-agent-revision",
}


def canonicalize_asset_machine_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    """Restore task-owned asset IDs, paths, and lifecycle markers."""
    task_type = str(task.payload.get("task_type") or "")
    if task.route != "character-and-world-assets" or task_type not in _ASSET_TASK_TYPES:
        return []
    candidate, review, completion = _owned_contracts(task)
    candidate_rel, candidate_id, asset_type = _asset_identity(task, candidate)
    source_paths = _source_paths(task, candidate)
    changes: list[dict[str, str]] = []
    if task_type == "platform-agent-asset-creation":
        changes.extend(
            _canonicalize_asset_candidate(
                sandbox,
                candidate,
                candidate_rel,
                candidate_id,
                asset_type,
                source_paths,
            )
        )
    if task_type in {"platform-agent-asset-review", "platform-agent-revision"}:
        changes.extend(
            _canonicalize_asset_review(
                task,
                sandbox,
                review,
                candidate_rel,
                candidate_id,
                asset_type,
            )
        )
    changes.extend(_canonicalize_completion_markers(task, sandbox, completion))
    return changes


def _owned_contracts(
    task: TaskPackage,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    owned = task.payload.get("system_owned_fields")
    fields = owned if isinstance(owned, dict) else {}
    candidate = fields.get("candidate")
    review = fields.get("review")
    completion = fields.get("completion")
    return (
        candidate if isinstance(candidate, dict) else {},
        review if isinstance(review, dict) else {},
        completion if isinstance(completion, dict) else {},
    )


def _asset_identity(
    task: TaskPackage,
    contract: dict[str, Any],
) -> tuple[str, str, str]:
    relative = str(
        contract.get("path") or task.payload.get("candidate") or ""
    ).replace("\\", "/").strip()
    candidate_id = str(
        contract.get("candidate_id")
        or task.payload.get("candidate_id")
        or task.payload.get("target_id")
        or ""
    ).strip()
    asset_type = str(
        contract.get("asset_type") or task.payload.get("asset_type") or ""
    ).strip()
    return relative, candidate_id, asset_type


def _source_paths(task: TaskPackage, contract: dict[str, Any]) -> list[str]:
    declared = contract.get("source_paths")
    values = declared if isinstance(declared, list) else task.source_paths
    return [str(item).replace("\\", "/") for item in values]


def _canonicalize_asset_candidate(
    sandbox: SandboxManifest,
    contract: dict[str, Any],
    relative: str,
    candidate_id: str,
    asset_type: str,
    source_paths: list[str],
) -> list[dict[str, str]]:
    if not relative:
        return []
    path = sandbox.workspace / Path(relative)
    payload = read_object(path)
    if payload is None:
        return []
    expected = {
        "schema": str(contract.get("schema") or payload.get("schema") or ""),
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "source_paths": source_paths,
    }
    if not isinstance(payload.get("promotion_notes"), str) or not str(
        payload.get("promotion_notes") or ""
    ).strip():
        expected["promotion_notes"] = (
            "Promotion requires a clean independent review and a matching approval record."
        )
    return write_machine_fields(path, relative, payload, expected, "asset-candidate")


def _canonicalize_asset_review(
    task: TaskPackage,
    sandbox: SandboxManifest,
    contract: dict[str, Any],
    candidate_rel: str,
    candidate_id: str,
    asset_type: str,
) -> list[dict[str, str]]:
    review_rel = _review_relative_path(task, contract)
    path = sandbox.workspace / Path(review_rel)
    payload = read_object(path)
    if payload is None:
        return []
    changes = flatten_asset_review_envelope(path, review_rel, payload)
    expected = review_machine_fields(
        task,
        sandbox,
        payload,
        contract,
        candidate=candidate_rel,
        candidate_id=candidate_id,
        asset_type=asset_type,
    )
    if task.current_state in {"asset-review-pass", "asset-approval-revision"}:
        expected["status"] = "recheck_required"
    changes.extend(
        write_machine_fields(path, review_rel, payload, expected, "asset-review")
    )
    changes.extend(
        canonicalize_asset_review_action_targets(
            path, review_rel, payload, candidate_rel
        )
    )
    changes.extend(
        _canonicalize_approval_revision(
            task, sandbox, path, review_rel, payload, candidate_rel
        )
    )
    return changes


def _review_relative_path(task: TaskPackage, contract: dict[str, Any]) -> str:
    declared = str(contract.get("path") or "").replace("\\", "/").strip()
    if declared:
        return declared
    return next(
        (
            relative
            for relative in task.expected_outputs
            if relative.replace("\\", "/").startswith("reviews/assets/")
            and relative.endswith("_review.json")
        ),
        "",
    )


def _canonicalize_approval_revision(
    task: TaskPackage,
    sandbox: SandboxManifest,
    review_path: Path,
    review_rel: str,
    review: dict[str, Any],
    candidate_rel: str,
) -> list[dict[str, str]]:
    if task.current_state != "asset-approval-revision" or not candidate_rel:
        return []
    candidate_path = sandbox.workspace / Path(candidate_rel)
    before = str(
        task.payload.get("candidate_sha256_before_revision") or ""
    ).strip().lower()
    if not before or not candidate_path.is_file():
        return []
    if hashlib.sha256(candidate_path.read_bytes()).hexdigest() == before:
        return []
    applied = review.get("applied_revision_actions")
    if isinstance(applied, list) and applied:
        return []
    rationale = _latest_approval_rationale(
        sandbox.workspace,
        str(review.get("candidate_id") or ""),
    )
    _reset_review_for_recheck(review, candidate_rel, rationale)
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _append_revision_notice(
        review_path.with_suffix(".md"),
        int(review["revision_round"]),
        rationale,
    )
    return [
        {
            "path": review_rel,
            "field": "approval-revision-reset",
            "reason": "generated deterministic approval-revision lifecycle evidence",
        }
    ]


def _reset_review_for_recheck(
    review: dict[str, Any],
    candidate_rel: str,
    rationale: str,
) -> None:
    existing = review.get("revision_round")
    next_round = (
        existing + 1
        if isinstance(existing, int) and not isinstance(existing, bool)
        else 1
    )
    review["status"] = "recheck_required"
    review["revision_round"] = max(1, next_round)
    review["applied_revision_actions"] = [
        {
            "id": "APPROVAL-REV-001",
            "action": rationale
            or "Applied the latest approval-bound candidate revision.",
            "evidence": (
                f"{candidate_rel} changed from the approval-bound candidate digest; "
                "a fresh independent review must verify the exact semantic change."
            ),
        }
    ]
    review["revised_at"] = datetime.now(timezone.utc).isoformat()


def _latest_approval_rationale(workspace: Path, candidate_id: str) -> str:
    approvals = workspace / "workflow" / "approvals" / "index.jsonl"
    if not approvals.is_file():
        return ""
    try:
        records = [
            json.loads(line)
            for line in approvals.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    for record in reversed(records):
        if not isinstance(record, dict) or str(record.get("run_id") or "") != candidate_id:
            continue
        if str(record.get("decision") or "").strip().lower() not in {"revise", "reject"}:
            continue
        return str(record.get("notes") or "").strip()[:800]
    return ""


def _append_revision_notice(
    report_path: Path,
    revision_round: int,
    rationale: str,
) -> None:
    if not report_path.is_file():
        return
    try:
        content = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    marker = "## Studio Revision Reset"
    if marker in content:
        return
    note = rationale or "The latest approval requested a candidate-local revision."
    report_path.write_text(
        content.rstrip()
        + f"\n\n{marker}\n\n- Revision round: {revision_round}\n"
        + f"- Approval rationale recorded for independent recheck: {note}\n",
        encoding="utf-8",
    )


def _canonicalize_completion_markers(
    task: TaskPackage,
    sandbox: SandboxManifest,
    contract: dict[str, Any],
) -> list[dict[str, str]]:
    non_markers = [
        item
        for item in task.expected_outputs
        if not item.endswith(".agent_completion.json")
    ]
    if any(
        not (sandbox.workspace / Path(item)).is_file()
        or (sandbox.workspace / Path(item)).stat().st_size == 0
        for item in non_markers
    ):
        return []
    revision_reset = task.current_state in {
        "asset-review-pass",
        "asset-approval-revision",
    }
    status = "recheck_required" if revision_reset else str(
        contract.get("status") or "complete"
    )
    checked = False if revision_reset else bool(
        contract.get("expected_artifacts_checked", True)
    )
    return _write_completion_markers(
        task,
        sandbox,
        contract,
        status=status,
        checked=checked,
    )


def _write_completion_markers(
    task: TaskPackage,
    sandbox: SandboxManifest,
    contract: dict[str, Any],
    *,
    status: str,
    checked: bool,
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for relative in task.expected_outputs:
        if not relative.endswith(".agent_completion.json"):
            continue
        payload = _completion_payload(relative, contract, status, checked)
        path = sandbox.workspace / Path(relative)
        existing = read_object(path)
        comparable = dict(payload)
        comparable.pop("completed_at")
        existing_comparable = dict(existing or {})
        existing_comparable.pop("completed_at", None)
        if existing_comparable == comparable:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changes.append(
            {
                "path": relative,
                "field": "completion",
                "reason": "generated deterministic asset-task completion metadata",
            }
        )
    return changes


def _completion_payload(
    relative: str,
    contract: dict[str, Any],
    status: str,
    checked: bool,
) -> dict[str, Any]:
    base = relative[: -len(".agent_completion.json")]
    source_task = base + (
        ".md" if base.endswith(".agent_tasks") else ".agent_tasks.md"
    )
    return {
        "schema": str(
            contract.get("schema")
            or "literary-engineering-workbench/agent-task-completion/v1"
        ),
        "source_task": source_task,
        "status": status,
        "handled_by": "studio-worker",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "expected_artifacts_checked": checked,
        "notes": [
            "Machine-owned completion metadata; semantic validation is enforced by the route gate."
        ],
    }


__all__ = ["canonicalize_asset_machine_metadata"]
