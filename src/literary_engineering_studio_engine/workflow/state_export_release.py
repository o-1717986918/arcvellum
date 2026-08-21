"""Derived state for export-and-release evidence."""
from __future__ import annotations

from pathlib import Path

from ..literary.planning.chapter_inventory import formal_chapter_ids
from ..release_fingerprint import release_candidate_fingerprint
from .state_common import _approval_record, _file_step, _read_json, _rel
def _export_release_states(root: Path) -> list[dict[str, object]]:
    chapter_ids = list(formal_chapter_ids(root))
    return [_export_release_state(root, chapter_id) for chapter_id in chapter_ids]


def _export_release_state(root: Path, chapter_id: str) -> dict[str, object]:
    chapter_json = root / "plot" / "chapters" / f"{chapter_id}.json"
    chapter_md = root / "drafts" / "chapters" / f"{chapter_id}.md"
    export_manifest = root / "exports" / chapter_id / "export_manifest.json"
    approval_run_id = f"release-{chapter_id}"
    latest = root / "releases" / chapter_id / "latest.json"
    release_dir = root / "releases" / chapter_id / "formal-release"
    steps = [
        _chapter_workspace_step(root, chapter_id, chapter_json, chapter_md),
        _export_package_step(root, chapter_id, export_manifest),
        _release_approval_step(root, approval_run_id, export_manifest),
        _publish_release_step(root, latest, release_dir),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": chapter_id,
        "chapter_id": chapter_id,
        "scene_id": chapter_id,
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _chapter_workspace_step(root: Path, chapter_id: str, json_path: Path, markdown_path: Path) -> dict[str, object]:
    if not json_path.exists() or not markdown_path.exists():
        return {
            "key": "chapter-workspace",
            "status": "missing",
            "path": _rel(json_path, root),
            "message": "missing chapter workspace JSON or Markdown",
            "next_action": f"run chapter-workspace for {chapter_id}",
        }
    payload = _read_json(json_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blocked = int(summary.get("blocked_count", 0) or 0)
    ready = int(summary.get("ready_count", 0) or 0)
    passed = blocked == 0 and ready > 0
    return {
        "key": "chapter-workspace",
        "status": "pass" if passed else "blocked",
        "path": _rel(json_path, root),
        "message": f"ready={ready}; blocked={blocked}",
        "next_action": "" if passed else "repair scene-development gates, rerun chapter-workspace, and ensure every scene is ready",
    }


def _export_route_audit_step(root: Path, json_path: Path) -> dict[str, object]:
    payload = _read_json(json_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    route = str(summary.get("route") or "").strip().lower()
    blocking = int(summary.get("blocking_count", 0) or 0)
    passed = json_path.exists() and route == "export-and-release" and blocking == 0
    return {
        "key": "export-route-audit",
        "status": "pass" if passed else "missing" if not json_path.exists() else "blocked",
        "path": _rel(json_path, root),
        "message": f"route={route or 'missing'}; blocking={blocking}",
        "next_action": "" if passed else "run route-audit --route export-and-release with dedicated output and resolve blocking gates",
    }


def _export_package_step(root: Path, chapter_id: str, manifest_path: Path) -> dict[str, object]:
    payload = _read_json(manifest_path)
    skipped = payload.get("skipped_scenes") if isinstance(payload.get("skipped_scenes"), list) else []
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    docx = outputs.get("docx") if isinstance(outputs.get("docx"), dict) else {}
    layouts = outputs.get("docx_layout_plans") if isinstance(outputs.get("docx_layout_plans"), dict) else {}
    inspections = outputs.get("docx_inspections") if isinstance(outputs.get("docx_inspections"), dict) else {}
    delivery_keys = ("novel", "screenplay", "video_prompt_pack")
    required = [
        outputs.get("novel"),
        outputs.get("screenplay"),
        outputs.get("video_prompt_pack"),
        *[docx.get(key) for key in delivery_keys],
        *[layouts.get(key) for key in delivery_keys],
        *[inspections.get(key) for key in delivery_keys],
    ]
    missing = [str(item) for item in required if not item or not (root / str(item)).exists()]
    include_blocked = bool(payload.get("include_blocked"))
    formats = {str(item).strip().lower() for item in payload.get("requested_formats", []) if str(item).strip()}
    passed = manifest_path.exists() and {"md", "docx"}.issubset(formats) and not skipped and not include_blocked and not missing
    message = f"skipped={len(skipped)}; include_blocked={include_blocked}; missing_outputs={len(missing)}"
    return {
        "key": "export-package",
        "status": "pass" if passed else "missing" if not manifest_path.exists() else "blocked",
        "path": _rel(manifest_path, root),
        "message": message,
        "next_action": "" if passed else f"run export-package for {chapter_id}; do not use --include-blocked",
    }


def _release_approval_step(root: Path, run_id: str, manifest_path: Path) -> dict[str, object]:
    approval = _approval_record(root, run_id)
    decision = str(approval.get("decision") or "").strip().lower()
    current = _approval_matches_digest(approval, release_candidate_fingerprint(root, manifest_path.parent.name))
    passed = decision == "approve" and current
    revision_requested = decision in {"revise", "reject"} and current
    return {
        "key": "release-revision-required" if revision_requested else "release-approval",
        "status": "pass" if passed else decision if current else "missing",
        "path": "workflow/approvals/index.jsonl",
        "message": "current export approve record exists" if passed else (
            f"current export was {decision}; return the requested changes to formal scene review/revision"
            if revision_requested
            else f"missing approval bound to the current export manifest for {run_id}"
        ),
        "next_action": "" if passed else (
            "choose the affected scene revisions, rerun review/promotion/chapter export, then request a fresh release decision"
            if revision_requested
            else f"ask user to approve the current release candidate and record approval run_id `{run_id}`"
        ),
    }


def _approval_matches_digest(approval: dict[str, object], digest: str) -> bool:
    return bool(digest) and str(approval.get("subject_sha256") or "").strip().lower() == digest.lower()


def _publish_release_step(root: Path, latest_path: Path, release_dir: Path) -> dict[str, object]:
    latest = _read_json(latest_path)
    manifest = release_dir / "publish_manifest.json"
    payload = _read_json(manifest)
    status = str(payload.get("status") or "").strip().lower()
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    approved_fingerprint = str(payload.get("approved_export_fingerprint") or "").strip().lower()
    passed = (
        latest_path.exists()
        and manifest.exists()
        and status == "published"
        and not payload.get("allow_unapproved")
        and approval.get("decision") == "approve"
        and bool(approved_fingerprint)
        and str(approval.get("subject_sha256") or "").strip().lower() == approved_fingerprint
        and latest.get("manifest") == _rel(manifest, root)
    )
    return {
        "key": "publish-release",
        "status": "pass" if passed else "missing" if not manifest.exists() else "blocked",
        "path": _rel(manifest, root),
        "message": f"latest={bool(latest)}; status={status or 'missing'}; approval={approval.get('decision') or 'missing'}; content_bound={bool(approved_fingerprint)}",
        "next_action": "" if passed else "run publish-chapter with approval run id; do not use --allow-unapproved",
    }
