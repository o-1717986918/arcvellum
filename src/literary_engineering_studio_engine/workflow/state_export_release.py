"""Derived state for export-and-release evidence."""
from __future__ import annotations

from pathlib import Path

from ..literary.planning.chapter_inventory import formal_chapter_ids, is_final_chapter
from ..literary.planning.length_repair import target_length_repair_status
from ..literary.export.freshness import (
    chapter_workspace_is_fresh,
    export_package_is_fresh,
    missing_export_outputs,
    published_release_is_current,
)
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
        _target_length_step(root, chapter_id),
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

def _target_length_step(root: Path, chapter_id: str) -> dict[str, object]:
    if not is_final_chapter(root, chapter_id):
        return {
            "key": "target-length-gate",
            "status": "pass",
            "path": "plot/word_budget/word_budget.json",
            "message": "whole-work target is enforced at the final formal chapter",
            "next_action": "",
        }
    repair = target_length_repair_status(root)
    length = repair["delivery_length"]
    if length["status"] == "pass":
        return {
            "key": "target-length-gate",
            "status": "pass",
            "path": "plot/word_budget/word_budget.json",
            "message": f"actual={length['actual_chinese_chars']}; target={length['target_chinese_chars']}",
            "next_action": "",
        }
    if repair["status"] == "insufficient_capacity":
        return {
            "key": "target-length-capacity-blocked",
            "status": "blocked",
            "path": str(repair["path"]),
            "message": (
                f"whole-work shortfall={length['shortfall_chinese_chars']}; "
                "the current scene inventory has insufficient safe expansion capacity"
            ),
            "next_action": (
                "return to longform planning and add an earned scene, subplot beat, "
                "or formally revise scene capacities before generating more prose"
            ),
        }
    plan_ready = repair["status"] == "pending"
    return {
        "key": "target-length-repair-scenes" if plan_ready else "target-length-repair-plan",
        "status": "blocked" if plan_ready else "missing",
        "path": str(repair["path"]),
        "message": (
            f"whole-work shortfall={length['shortfall_chinese_chars']}; "
            f"pending scenes={','.join(repair['pending_scene_ids']) or 'unplanned'}"
        ),
        "next_action": (
            "resume scene-development for every pending target-length allocation"
            if plan_ready
            else "run plan-length-repair before final release approval"
        ),
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
    fresh = chapter_workspace_is_fresh(root, chapter_id, [json_path, markdown_path])
    payload = _read_json(json_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blocked = int(summary.get("blocked_count", 0) or 0)
    ready = int(summary.get("ready_count", 0) or 0)
    passed = blocked == 0 and ready > 0 and fresh
    return {
        "key": "chapter-workspace",
        "status": "pass" if passed else "stale" if not fresh else "blocked",
        "path": _rel(json_path, root),
        "message": f"ready={ready}; blocked={blocked}; fresh={fresh}",
        "next_action": "" if passed else (
            f"rerun chapter-workspace for {chapter_id} after the current formal drafts"
            if not fresh
            else "repair scene-development gates, rerun chapter-workspace, and ensure every scene is ready"
        ),
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
    missing = missing_export_outputs(root, payload)
    include_blocked = bool(payload.get("include_blocked"))
    formats = {str(item).strip().lower() for item in payload.get("requested_formats", []) if str(item).strip()}
    fresh = export_package_is_fresh(root, chapter_id, manifest_path)
    passed = manifest_path.exists() and fresh and {"md", "docx"}.issubset(formats) and not skipped and not include_blocked and not missing
    message = f"skipped={len(skipped)}; include_blocked={include_blocked}; missing_outputs={len(missing)}; fresh={fresh}"
    return {
        "key": "export-package",
        "status": "pass" if passed else "missing" if not manifest_path.exists() else "stale" if not fresh else "blocked",
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
    chapter_id = latest_path.parent.name
    passed, content_bound = published_release_is_current(
        root, chapter_id, latest_path, manifest, latest, payload,
    )
    return {
        "key": "publish-release",
        "status": "pass" if passed else "missing" if not manifest.exists() else "blocked",
        "path": _rel(manifest, root),
        "message": f"latest={bool(latest)}; status={status or 'missing'}; approval={approval.get('decision') or 'missing'}; current_content_bound={content_bound}",
        "next_action": "" if passed else "run publish-chapter with approval run id; do not use --allow-unapproved",
    }
