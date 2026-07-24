"""Derived state for character-and-world asset candidates."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ..agent_tasks import agent_task_completion_status
from ..asset_workshop import ASSET_CANDIDATE_DIRS
from .state_common import _approval_record, _file_step, _parse_datetime, _read_json, _rel


def _infer_asset_type(root: Path, candidate_path: Path) -> str:
    """Recover the asset type from its registered candidate directory."""

    try:
        relative = candidate_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""
    for asset_type, folder in ASSET_CANDIDATE_DIRS.items():
        if relative.startswith(f"{folder.as_posix()}/"):
            return asset_type
    return ""


def _agent_task_base(task_path: Path) -> Path:
    """Resolve the declared candidate base path for an asset task sidecar."""

    suffix = ".agent_tasks.md"
    if task_path.name.endswith(suffix):
        return task_path.with_name(task_path.name[: -len(suffix)])
    return task_path.with_suffix("")


def _asset_states(root: Path, *, include_intake: bool = False) -> list[dict[str, object]]:
    records: dict[str, dict[str, Path | str]] = {}
    for asset_type, folder in ASSET_CANDIDATE_DIRS.items():
        base = root / folder
        if not base.exists():
            continue
        for candidate in sorted(base.glob("*.json")):
            if candidate.name.endswith(".agent_completion.json") or candidate.name.endswith(".submission.json"):
                continue
            candidate_id = candidate.stem
            record = records.setdefault(candidate_id, {"candidate": candidate, "asset_type": asset_type})
            record["candidate"] = candidate
            record["asset_type"] = str(_read_json(candidate).get("asset_type") or asset_type)
        for task in sorted(base.glob("*.agent_tasks.md")):
            candidate_id = _agent_task_base(task).stem
            record = records.setdefault(candidate_id, {"candidate": _agent_task_base(task).with_suffix(".json"), "asset_type": asset_type})
            record["creation_task"] = task
            record.setdefault("candidate", _agent_task_base(task).with_suffix(".json"))
            record.setdefault("asset_type", asset_type)
    states = [_asset_state(root, record) for _candidate_id, record in sorted(records.items())]
    if not states and include_intake:
        states.append(_asset_intake_state())
    return states


def _asset_intake_state() -> dict[str, object]:
    return {
        "target_id": "asset-intake",
        "candidate_id": "asset-intake",
        "asset_type": "",
        "candidate": "",
        "status": "blocked",
        "current_step": "asset-intake",
        "next_action": "run seed-project-assets to create foundational world and protagonist platform-agent sidecars",
        "steps": [
            {
                "key": "asset-intake",
                "status": "missing",
                "path": "",
                "message": "no candidate asset or asset creation sidecar found",
                "next_action": "run seed-project-assets; the resulting sidecars will hand creative asset generation to the Agent",
            }
        ],
    }


def _asset_state(root: Path, record: dict[str, Path | str]) -> dict[str, object]:
    candidate = record.get("candidate")
    candidate_path = candidate if isinstance(candidate, Path) else root / str(candidate)
    candidate_id = candidate_path.stem
    payload = _read_json(candidate_path)
    asset_type = str(payload.get("asset_type") or record.get("asset_type") or _infer_asset_type(root, candidate_path))
    creation_task = record.get("creation_task")
    creation_task_path = creation_task if isinstance(creation_task, Path) else candidate_path.with_suffix(".agent_tasks.md")
    report_path = candidate_path.with_suffix(".md")
    review_path = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    review_json = review_path.with_suffix(".json")
    review_task = review_json.with_suffix(".agent_tasks.md")
    promotion_manifest = root / "workflow" / "asset_promotions" / f"{candidate_id}_promotion.json"
    steps = [
        _asset_creation_step(root, candidate_path, report_path, creation_task_path),
        _file_step("asset-review-task-file", review_task, "run review-candidate-asset to create the platform-agent asset review sidecar"),
        _asset_review_agent_step(root, review_task, review_json, review_path),
        _asset_review_pass_step(root, review_json),
        _asset_approval_step(root, candidate_id, candidate_path),
        _asset_promotion_step(root, promotion_manifest),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": candidate_id,
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "candidate": _rel(candidate_path, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _asset_creation_step(root: Path, candidate_path: Path, report_path: Path, task_path: Path) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    missing = [_rel(path, root) for path in (candidate_path, report_path) if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": "asset-creation-agent-task",
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else "complete asset creation sidecar, candidate JSON, candidate report, and completion marker",
    }


def _asset_review_agent_step(root: Path, task_path: Path, json_path: Path, report_path: Path) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    missing = [_rel(path, root) for path in (json_path, report_path) if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": "asset-review-agent-task",
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else "complete asset review sidecar, review JSON, review report, and completion marker",
    }


def _asset_review_pass_step(root: Path, review_json: Path) -> dict[str, object]:
    payload = _read_json(review_json)
    status = str(payload.get("status") or "").strip().lower()
    blocking = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
    revisions = payload.get("revision_actions") if isinstance(payload.get("revision_actions"), list) else []
    passed = status == "pass" and not blocking and not revisions
    return {
        "key": "asset-review-pass",
        "status": "pass" if passed else status or "missing",
        "path": _rel(review_json, root),
        "message": f"status={status or 'missing'}; blocking={len(blocking)}; revision_actions={len(revisions)}",
        "next_action": (
            ""
            if passed
            else "revise the candidate against every recorded finding, reset review evidence to recheck_required, then run a fresh independent asset review"
        ),
    }


def _asset_approval_step(root: Path, candidate_id: str, candidate_path: Path) -> dict[str, object]:
    approval = _approval_record(root, candidate_id)
    decision = str(approval.get("decision") or "").strip().lower()
    current = _approval_matches_candidate(approval, candidate_path)
    passed = decision == "approve" and current
    revision_requested = decision in {"revise", "reject"} and current
    return {
        "key": "asset-approval-revision" if revision_requested else "asset-approval",
        "status": "pass" if passed else decision if current else "missing",
        "path": "workflow/approvals/index.jsonl",
        "message": "current-candidate approve record exists" if passed else (
            f"current candidate was {decision}; revise it using the recorded approval notes" if revision_requested else "missing approve record for current candidate content"
        ),
        "next_action": "" if passed else (
            "revise the candidate against the latest approval rationale, reset review evidence, and request an independent re-review"
            if revision_requested
            else f"ask user for approval and record an approve decision for run_id `{candidate_id}` before promotion"
        ),
    }


def _approval_matches_candidate(approval: dict[str, object], candidate_path: Path) -> bool:
    if not approval or not candidate_path.is_file():
        return False
    actual = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    recorded = str(approval.get("subject_sha256") or "").strip().lower()
    if recorded:
        return recorded == actual
    recorded_at = _parse_datetime(str(approval.get("recorded_at") or ""))
    if recorded_at is None:
        return False
    candidate_time = datetime.fromtimestamp(candidate_path.stat().st_mtime, tz=timezone.utc)
    return candidate_time <= recorded_at


def _asset_promotion_step(root: Path, manifest_path: Path) -> dict[str, object]:
    payload = _read_json(manifest_path)
    outputs = [root / str(item) for item in payload.get("outputs", [])] if isinstance(payload.get("outputs"), list) else []
    missing_outputs = [_rel(path, root) for path in outputs if not path.exists()]
    blocked = bool(payload.get("allow_unapproved")) or missing_outputs or str(payload.get("status") or "") != "promoted"
    message = f"status={payload.get('status') or 'missing'}"
    if payload.get("allow_unapproved"):
        message += "; allow_unapproved=true"
    if missing_outputs:
        message += "; missing outputs=" + ", ".join(missing_outputs)
    return {
        "key": "asset-promotion",
        "status": "pass" if manifest_path.exists() and not blocked else "missing" if not manifest_path.exists() else "blocked",
        "path": _rel(manifest_path, root),
        "message": message,
        "next_action": "" if manifest_path.exists() and not blocked else "run promote-candidate-asset with an approval run id; do not use --allow-unapproved",
    }
