"""Controlled Studio adapter for Engine-owned candidate promotion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.literary import ASSET_CANDIDATE_DIRS
from literary_engineering_studio_engine.public.literary import (
    file_sha256,
    latest_approval,
    promotion_eligibility_errors,
    promotion_output_paths,
)
from literary_engineering_studio_engine.public.workflow import asset_candidate_states

from ...runtime.runtime_selection import DEFAULT_CREATIVE_RUNTIME
from .staleness import build_formal_stale_preview, build_formal_stale_propagation


class CandidateNotFoundError(FileNotFoundError):
    pass


class CandidateIdentityConflictError(ValueError):
    pass


class CandidatePromotionNotReadyError(RuntimeError):
    def __init__(self, candidate_id: str, blockers: tuple[str, ...]):
        super().__init__(f"candidate {candidate_id} is not ready for promotion")
        self.candidate_id = candidate_id
        self.blockers = blockers


class CandidatePromotionPreviewStaleError(RuntimeError):
    pass


class CandidatePromotionService:
    """Read candidate truth and compile an exact formal Worker request."""

    def list(self, project_root: Path) -> tuple[dict[str, object], ...]:
        root = project_root.resolve()
        return tuple(self._summary(root, state) for state in asset_candidate_states(root))

    def detail(self, project_root: Path, candidate_id: str) -> dict[str, object]:
        root = project_root.resolve()
        state = self._state(root, candidate_id)
        candidate_path = self._candidate_path(root, state)
        payload = _read_object(candidate_path)
        asset_type = str(state.get("asset_type") or payload.get("asset_type") or "")
        review_json = root / "reviews" / "assets" / f"{candidate_id}_review.json"
        review_report = review_json.with_suffix(".md")
        approval = latest_approval(root, candidate_id)
        outputs = promotion_output_paths(root, asset_type, payload)
        output_rows = tuple(self._output_row(root, path) for path in outputs)
        blockers = tuple(
            _safe_message(root, message)
            for message in promotion_eligibility_errors(
                root,
                candidate_path,
                asset_type=asset_type,
                approval_run_id=candidate_id,
                allow_unapproved=False,
            )
        )
        receipt_path = root / "workflow" / "asset_promotions" / f"{candidate_id}_promotion.json"
        receipt = _read_object(receipt_path)
        promoted = str(receipt.get("status") or "") == "promoted"
        current_step = str(state.get("current_step") or "")
        can_promote = current_step == "asset-promotion" and not blockers and not promoted
        changed_paths = tuple(str(row["path"]) for row in output_rows)
        stale = (
            _merged_stale_propagation(root, changed_paths)
            if promoted
            else build_formal_stale_preview(root, changed_paths)
        )
        digest = _preview_digest(
            candidate_path,
            review_json,
            approval,
            output_rows,
            current_step=current_step,
            promoted=promoted,
        )
        return {
            **self._summary(root, state),
            "schema": "arcvellum/archive-candidate-detail/v1",
            "title": _candidate_title(payload, candidate_id),
            "content": candidate_path.read_text(encoding="utf-8") if candidate_path.is_file() else "",
            "report": _read_text(candidate_path.with_suffix(".md")),
            "review": {
                "evidence": _public_review(_read_object(review_json)),
                "report": _read_text(review_report),
            },
            "approval": _public_approval(approval),
            "impact": {
                "schema": "arcvellum/archive-candidate-impact/v1",
                "formal_outputs": list(output_rows),
                "create_count": sum(not bool(row["exists"]) for row in output_rows),
                "replace_count": sum(bool(row["exists"]) for row in output_rows),
                "stale": stale,
            },
            "promotion_blockers": list(blockers),
            "can_promote": can_promote,
            "promoted": promoted,
            "preview_digest": digest,
            "receipt": _public_receipt(receipt),
        }

    def worker_request(
        self,
        project_root: Path,
        candidate_id: str,
        *,
        preview_digest: str,
    ) -> dict[str, str]:
        root = project_root.resolve()
        detail = self.detail(root, candidate_id)
        if not detail["can_promote"]:
            raise CandidatePromotionNotReadyError(
                candidate_id,
                tuple(str(item) for item in detail["promotion_blockers"]),
            )
        if preview_digest != detail["preview_digest"]:
            raise CandidatePromotionPreviewStaleError(
                "candidate, review, approval, or formal output changed after impact confirmation"
            )
        return {
            "project_root": str(root),
            "route": "character-and-world-assets",
            "runtime": DEFAULT_CREATIVE_RUNTIME,
            "task_id": "",
            "scene": candidate_id,
            "idempotency_key": f"archive-promotion:{candidate_id}:{preview_digest}",
        }

    def _state(self, root: Path, candidate_id: str) -> dict[str, object]:
        _validate_candidate_id(candidate_id)
        matches = [
            state
            for state in asset_candidate_states(root)
            if str(state.get("candidate_id") or "") == candidate_id
        ]
        if len(matches) > 1:
            raise CandidateIdentityConflictError(f"duplicate candidate id: {candidate_id}")
        if not matches:
            raise CandidateNotFoundError(f"candidate not found: {candidate_id}")
        return matches[0]

    def _candidate_path(self, root: Path, state: dict[str, object]) -> Path:
        relative = str(state.get("candidate") or "").replace("\\", "/").lstrip("/")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("candidate path leaves the work project")
        allowed = tuple((root / folder).resolve() for folder in ASSET_CANDIDATE_DIRS.values())
        if not any(path.is_relative_to(folder) for folder in allowed):
            raise ValueError("candidate path is outside registered candidate directories")
        return path

    def _summary(self, root: Path, state: dict[str, object]) -> dict[str, object]:
        candidate_path = self._candidate_path(root, state)
        payload = _read_object(candidate_path)
        steps = [
            {
                "key": str(step.get("key") or ""),
                "status": str(step.get("status") or ""),
                "message": _safe_message(root, str(step.get("message") or "")),
            }
            for step in state.get("steps", [])
            if isinstance(step, dict)
        ]
        return {
            "candidate_id": str(state.get("candidate_id") or ""),
            "asset_type": str(state.get("asset_type") or ""),
            "title": _candidate_title(payload, candidate_path.stem),
            "source_path": candidate_path.relative_to(root).as_posix(),
            "status": str(state.get("status") or ""),
            "current_step": str(state.get("current_step") or ""),
            "steps": steps,
        }

    @staticmethod
    def _output_row(root: Path, path: Path) -> dict[str, object]:
        exists = path.is_file()
        return {
            "path": path.relative_to(root).as_posix(),
            "exists": exists,
            "effect": "replace" if exists else "create",
            "revision": f"sha256:{file_sha256(path)}" if exists else "",
        }


def _preview_digest(
    candidate: Path,
    review: Path,
    approval: dict[str, object],
    outputs: tuple[dict[str, object], ...],
    *,
    current_step: str,
    promoted: bool,
) -> str:
    payload = {
        "candidate_sha256": file_sha256(candidate) if candidate.is_file() else "",
        "review_sha256": file_sha256(review) if review.is_file() else "",
        "approval": approval,
        "outputs": outputs,
        "current_step": current_step,
        "promoted": promoted,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _merged_stale_propagation(root: Path, changed_paths: tuple[str, ...]) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    statuses: list[str] = []
    for relative in changed_paths:
        result = build_formal_stale_propagation(root, relative)
        statuses.append(str(result.get("status") or ""))
        entries.extend(item for item in result.get("entries", []) if isinstance(item, dict))
    unique_entries = {
        (str(item.get("scene_id") or ""), str(item.get("context_trace") or "")): item
        for item in entries
    }
    propagated = "propagated" in statuses and all(
        status in {"propagated", "not-required"} for status in statuses
    )
    return {
        "schema": "arcvellum/archive-stale-propagation-summary/v1",
        "status": "propagated" if propagated else "not-required" if not entries else "incomplete",
        "mechanism": "engine-context-trace-sha256",
        "scene_ids": sorted({key[0] for key in unique_entries if key[0]}),
        "entries": list(unique_entries.values()),
        "invalidated_stages": [
            "context",
            "roleplay",
            "branch",
            "composition",
            "candidate",
            "review",
            "promotion",
        ]
        if entries
        else [],
        "historical_prose": "preserved",
    }


def _candidate_title(payload: dict[str, object], fallback: str) -> str:
    for field in ("name", "title", "character_name", "location_name", "organization_name", "candidate_id"):
        value = str(payload.get(field) or "").strip()
        if value:
            return value
    return fallback


def _public_review(payload: dict[str, object]) -> dict[str, object]:
    allowed = (
        "schema",
        "candidate_id",
        "candidate_sha256",
        "asset_type",
        "status",
        "blocking_issues",
        "warnings",
        "revision_actions",
        "promotion_risks",
        "reviewed_at",
    )
    return {field: payload[field] for field in allowed if field in payload}


def _public_approval(payload: dict[str, object]) -> dict[str, object]:
    allowed = ("run_id", "decision", "subject_sha256", "recorded_at", "reason", "rationale")
    return {field: payload[field] for field in allowed if field in payload}


def _public_receipt(payload: dict[str, object]) -> dict[str, object]:
    allowed = (
        "schema",
        "candidate_id",
        "asset_type",
        "status",
        "approval_run_id",
        "outputs",
        "promoted_at",
    )
    return {field: payload[field] for field in allowed if field in payload}


def _read_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _safe_message(root: Path, message: str) -> str:
    normalized = message.replace(str(root), "<project>").replace(str(root).replace("\\", "/"), "<project>")
    return normalized.replace("\\", "/")


def _validate_candidate_id(candidate_id: str) -> None:
    if not candidate_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in candidate_id):
        raise ValueError("candidate_id contains unsupported characters")
