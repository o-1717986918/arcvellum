"""Shared eligibility gates for deterministic candidate-asset promotion.

The formal route and the direct CLI both pass through this module. Candidate
rendering remains in ``workshop`` and route sequencing remains in
``routes.assets``; this module owns the promotion transaction boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Callable

from ...tasking.agent_tasks.writer import agent_task_completion_status


REVIEW_SCHEMA = "literary-engineering-workbench/candidate-asset-review/v0.1"


def candidate_review_gate_errors(
    root: Path,
    candidate: Path,
    *,
    asset_type: str,
    require_pass: bool,
) -> list[str]:
    """Validate review evidence against the exact current candidate content."""

    candidate_id = candidate.stem
    review = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    review_json = review.with_suffix(".json")
    review_task = review_json.with_suffix(".agent_tasks.md")
    errors: list[str] = []

    completion = agent_task_completion_status(review_task, root=root)
    if completion.get("complete") is not True:
        errors.append(f"asset review sidecar is incomplete: {completion.get('message')}")

    payload, error = _read_object(review_json)
    if error:
        errors.append(error)
    else:
        errors.extend(_review_identity_errors(payload, root, candidate, asset_type))
        errors.extend(_review_verdict_errors(payload, require_pass=require_pass))

    if not review.exists():
        errors.append(f"asset review report missing: {_relative(review, root)}")
    return errors


def approval_gate_errors(root: Path, run_id: str, candidate: Path) -> list[str]:
    approval = latest_approval(root, run_id)
    if str(approval.get("decision") or "").strip().lower() == "approve" and approval_matches_file(
        approval, candidate
    ):
        return []
    return [
        "asset promotion requires current-content approve record for "
        f"run_id {run_id}; got {approval.get('decision') or 'missing/stale'}"
    ]


def promotion_eligibility_errors(
    root: Path,
    candidate: Path,
    *,
    asset_type: str,
    approval_run_id: str,
    allow_unapproved: bool,
) -> list[str]:
    errors = candidate_review_gate_errors(
        root,
        candidate,
        asset_type=asset_type,
        require_pass=True,
    )
    if not allow_unapproved:
        errors.extend(approval_gate_errors(root, approval_run_id, candidate))
    return errors


def require_promotion_eligibility(
    root: Path,
    candidate: Path,
    *,
    asset_type: str,
    approval_run_id: str,
    allow_unapproved: bool,
) -> None:
    errors = promotion_eligibility_errors(
        root,
        candidate,
        asset_type=asset_type,
        approval_run_id=approval_run_id,
        allow_unapproved=allow_unapproved,
    )
    if errors:
        raise RuntimeError("candidate promotion gate failed: " + "; ".join(errors))


def latest_approval(root: Path, run_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.is_file():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def approval_matches_file(approval: dict[str, object], subject: Path) -> bool:
    if not approval or not subject.is_file():
        return False
    recorded = str(approval.get("subject_sha256") or "").strip().lower()
    if recorded:
        return recorded == file_sha256(subject)
    recorded_at = _parse_datetime(str(approval.get("recorded_at") or ""))
    if recorded_at is None:
        return False
    subject_time = datetime.fromtimestamp(subject.stat().st_mtime, tz=timezone.utc)
    return subject_time <= recorded_at


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def promotion_output_paths(root: Path, asset_type: str, payload: dict[str, object]) -> tuple[Path, ...]:
    """Return the exact formal files the deterministic renderer may mutate."""

    normalized = asset_type.strip().lower().replace("_", "-")
    if normalized == "character":
        return (root / "characters" / f"{_safe_id(payload.get('character_id'), 'agent_character')}.yaml",)
    if normalized == "background-story":
        return (
            root / "characters" / f"{_safe_id(payload.get('target_character_id'), 'agent_character')}.yaml",
        )
    if normalized == "relationship":
        return (root / "plot" / "relationship_graph.json",)
    if normalized == "world":
        return (root / "canon" / "world_rules.yaml",)
    if normalized == "location":
        return (root / "canon" / "locations.yaml",)
    if normalized == "organization":
        return (root / "canon" / "organizations.yaml",)

    outputs = [root / "plot" / "outline.md"]
    scene_list = payload.get("scene_list") if isinstance(payload.get("scene_list"), list) else []
    for item in scene_list:
        if not isinstance(item, dict):
            continue
        scene_id = _safe_id(item.get("scene_id"), "scene_candidate")
        path = root / "scenes" / f"{scene_id}.yaml"
        if path not in outputs:
            outputs.append(path)
    return tuple(outputs)


def restore_file_snapshots(snapshots: dict[Path, bytes | None]) -> None:
    """Restore files captured before a failed multi-output promotion."""

    for path, content in snapshots.items():
        if content is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def commit_promotion(
    root: Path,
    candidate: Path,
    *,
    asset_type: str,
    payload: dict[str, object],
    approval_run_id: str,
    allow_unapproved: bool,
    writer: Callable[[Path, str, dict[str, object]], list[Path]],
    report_renderer: Callable[[dict[str, object]], str],
    timestamp: Callable[[], str],
) -> tuple[tuple[Path, ...], Path, Path]:
    """Write all promotion outputs or restore every previous file."""

    promotion_dir = root / "workflow" / "asset_promotions"
    manifest = promotion_dir / f"{candidate.stem}_promotion.json"
    report = manifest.with_suffix(".md")
    planned = promotion_output_paths(root, asset_type, payload)
    snapshots = {path: path.read_bytes() if path.is_file() else None for path in (*planned, manifest, report)}
    try:
        outputs = tuple(writer(root, asset_type, payload))
        if outputs != planned:
            raise RuntimeError("promotion renderer mutated outputs outside its declared output plan")
        promotion_dir.mkdir(parents=True, exist_ok=True)
        receipt = _promotion_receipt(
            root,
            candidate,
            asset_type=asset_type,
            approval_run_id=approval_run_id,
            allow_unapproved=allow_unapproved,
            outputs=outputs,
            promoted_at=timestamp(),
        )
        manifest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report.write_text(report_renderer(receipt), encoding="utf-8")
        return outputs, manifest, report
    except Exception:
        restore_file_snapshots(snapshots)
        raise


def _review_identity_errors(
    payload: dict[str, object],
    root: Path,
    candidate: Path,
    asset_type: str,
) -> list[str]:
    errors: list[str] = []
    expected_candidate = _relative(candidate, root)
    expected = {
        "candidate": expected_candidate,
        "candidate_id": candidate.stem,
        "asset_type": asset_type.strip().lower().replace("_", "-"),
    }
    actual = {
        "candidate": str(payload.get("candidate") or "").replace("\\", "/").lstrip("/"),
        "candidate_id": str(payload.get("candidate_id") or "").strip(),
        "asset_type": str(payload.get("asset_type") or "").strip().lower().replace("_", "-"),
    }
    if payload.get("schema") != REVIEW_SCHEMA:
        errors.append(f"asset review schema must be {REVIEW_SCHEMA}")
    for field, expected_value in expected.items():
        if actual[field] != expected_value:
            errors.append(f"asset review {field} must be {expected_value}; got {actual[field] or 'missing'}")
    digest = str(payload.get("candidate_sha256") or "").strip().lower()
    if not digest:
        errors.append("asset review candidate_sha256 is required")
    elif not candidate.is_file() or digest != file_sha256(candidate):
        errors.append("asset review candidate_sha256 does not match the current candidate content")
    return errors


def _review_verdict_errors(payload: dict[str, object], *, require_pass: bool) -> list[str]:
    errors: list[str] = []
    status = str(payload.get("status") or "").strip().lower()
    allowed = {"pass", "failed", "revise_required"}
    if status not in allowed:
        errors.append(f"asset review status must be one of {', '.join(sorted(allowed))}; got {status or 'missing'}")
    elif require_pass and status != "pass":
        errors.append(f"asset review status must be pass; got {status}")
    for field in ("blocking_issues", "warnings", "revision_actions", "promotion_risks"):
        value = payload.get(field)
        if not isinstance(value, list):
            errors.append(f"asset review {field} must be a list")
        elif require_pass and field in {"blocking_issues", "revision_actions"} and value:
            errors.append(f"asset review has unresolved {field}: {len(value)}")
    return errors


def _promotion_receipt(
    root: Path,
    candidate: Path,
    *,
    asset_type: str,
    approval_run_id: str,
    allow_unapproved: bool,
    outputs: tuple[Path, ...],
    promoted_at: str,
) -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/candidate-asset-promotion/v0.1",
        "candidate": _relative(candidate, root),
        "candidate_id": candidate.stem,
        "asset_type": asset_type,
        "status": "promoted",
        "approval_run_id": approval_run_id,
        "allow_unapproved": allow_unapproved,
        "outputs": [_relative(path, root) for path in outputs],
        "promoted_at": promoted_at,
    }


def _read_object(path: Path) -> tuple[dict[str, object], str]:
    if not path.is_file():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {path} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip().replace("Z", "+00:00")
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _safe_id(value: object, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", str(value or fallback).strip()).strip("_")
    return cleaned or "asset"
