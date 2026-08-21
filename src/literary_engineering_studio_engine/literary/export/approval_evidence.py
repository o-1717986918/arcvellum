"""Project-relative evidence contract for a chapter release decision."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..planning.chapter_inventory import is_final_chapter
from .fingerprint import release_candidate_fingerprint


RELEASE_APPROVAL_CONTEXT_REVISION = "chapter-release/v2"


def release_approval_evidence_paths(
    project_root: Path,
    chapter_id: str,
) -> tuple[str, ...]:
    """Return bounded evidence for this chapter's actual release scope."""

    prefix = f"exports/{chapter_id}/{chapter_id}"
    chapter_evidence = (
        f"exports/{chapter_id}/export_manifest.json",
        f"{prefix}_novel.inspection.json",
        f"{prefix}_screenplay.inspection.json",
        f"{prefix}_video_prompt_pack.inspection.json",
        f"{prefix}_novel.md",
        f"plot/chapters/{chapter_id}.json",
    )
    if not is_final_chapter(project_root, chapter_id):
        return chapter_evidence
    return (
        *chapter_evidence[:4],
        "reviews/longform/longform_audit.json",
        *chapter_evidence[4:],
        "reviews/agent/committee_project-final-audit.json",
    )


def release_approval_scope(project_root: Path, chapter_id: str) -> dict[str, str]:
    final = is_final_chapter(project_root, chapter_id)
    return {
        "release_scope": "whole-work-final" if final else "chapter-only",
        "target_chapter": chapter_id,
        "is_final_chapter": "true" if final else "false",
        "whole_work_target_gate": "required-before-approval" if final else "deferred-to-final-chapter",
    }


def release_approval_context_sha256(project_root: Path, chapter_id: str) -> str:
    """Bind delegated approval to its scoped evidence, not only delivery text."""

    root = project_root.resolve()
    evidence = []
    for relative in release_approval_evidence_paths(root, chapter_id):
        path = root / relative
        evidence.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                if path.is_file()
                else "missing",
            }
        )
    payload = {
        "contract_revision": RELEASE_APPROVAL_CONTEXT_REVISION,
        "scope": release_approval_scope(root, chapter_id),
        "evidence": evidence,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def release_approval_is_current(
    project_root: Path,
    chapter_id: str,
    approval: dict[str, object],
) -> bool:
    """Validate content binding and delegated evidence-context binding."""

    root = project_root.resolve()
    fingerprint = release_candidate_fingerprint(root, chapter_id)
    if not fingerprint or str(approval.get("subject_sha256") or "").strip().lower() != fingerprint:
        return False
    recorded_context = str(approval.get("decision_context_sha256") or "").strip().lower()
    if recorded_context:
        return recorded_context == release_approval_context_sha256(root, chapter_id)
    actor = str(approval.get("actor") or "").strip().lower()
    return not actor.startswith("delegated-agent:")

__all__ = [
    "RELEASE_APPROVAL_CONTEXT_REVISION",
    "release_approval_context_sha256",
    "release_approval_evidence_paths",
    "release_approval_is_current",
    "release_approval_scope",
]
