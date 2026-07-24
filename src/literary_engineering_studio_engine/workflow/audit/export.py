"""Export-and-release audit gates."""
from __future__ import annotations

from pathlib import Path
import re

from ...route_audit_common import _add_gate, _approval_record, _path_exists, _read_json, _read_text, _rel
def _non_ready_scene_count(chapter_jsons: list[Path]) -> int:
    total = 0
    for path in chapter_jsons:
        payload = _read_json(path)
        for scene in payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []:
            if isinstance(scene, dict) and scene.get("status") != "ready":
                total += 1
    return total


def _stale_or_weak_chapter_gate_count(chapter_jsons: list[Path]) -> int:
    total = 0
    required_keys = {
        "agent_review_source_match",
        "agent_review_unresolved_notes",
        "style_adherence_status",
        "word_budget_adherence_status",
        "reader_experience_adherence_status",
        "reader_promise_satisfied",
        "flow_gate_issues",
        "readiness_issues",
    }
    for path in chapter_jsons:
        payload = _read_json(path)
        for scene in payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []:
            if not isinstance(scene, dict):
                continue
            if not required_keys.issubset(scene):
                total += 1
                continue
            reader_status = scene.get("reader_experience_adherence_status")
            weak = (
                scene.get("review_conclusion") != "pass"
                or scene.get("agent_review_conclusion") != "pass"
                or scene.get("agent_review_schema_status") != "pass"
                or scene.get("agent_review_source_match") is not True
                or bool(scene.get("agent_review_unresolved_notes"))
                or scene.get("word_budget_adherence_status") not in {"pass", "not_required"}
                or reader_status not in {"", "pass", "not_required"}
                or (reader_status in {"pass", "not_required"} and scene.get("reader_promise_satisfied") is False)
                or bool(scene.get("flow_gate_issues"))
                or bool(scene.get("readiness_issues"))
            )
            if weak:
                total += 1
    return total


def _unapplied_state_patch_count(root: Path) -> int:
    patch_dir = root / "characters" / "state_patches"
    if not patch_dir.exists():
        return 0
    count = 0
    for path in sorted(patch_dir.glob("*_state_patch.json")):
        scene_id = path.name[: -len("_state_patch.json")]
        apply_json = patch_dir / f"{scene_id}_state_apply.json"
        apply_report = patch_dir / f"{scene_id}_state_apply.md"
        if not (apply_json.exists() and apply_report.exists()):
            count += 1
    return count


def _unapplied_canon_patch_count(root: Path) -> int:
    patch_dir = root / "canon" / "patches"
    if not patch_dir.exists():
        return 0
    count = 0
    for path in sorted(patch_dir.glob("*_canon_patch.json")):
        payload = _read_json(path)
        if payload.get("applied") is True or str(payload.get("status") or "").strip().lower() == "applied":
            continue
        change = payload.get("canon_change")
        if change is True or str(change).strip().lower() in {"true", "yes", "1", "changed", "change"}:
            count += 1
    return count


def _add_export_release_route_gates(gates: list[dict[str, str]], root: Path, chapter_jsons: list[Path]) -> None:
    chapter_ids = [path.stem for path in chapter_jsons] or ["chapter_0001"]
    for chapter_id in chapter_ids:
        manifest = root / "exports" / chapter_id / "export_manifest.json"
        payload = _read_json(manifest)
        skipped = payload.get("skipped_scenes") if isinstance(payload.get("skipped_scenes"), list) else []
        outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
        output_missing: list[str] = []
        trace_hits: list[str] = []
        for key in ("novel", "screenplay", "video_prompt_pack"):
            rel = str(outputs.get(key) or "")
            if not rel:
                output_missing.append(key)
                continue
            path = root / rel
            if not path.exists():
                output_missing.append(rel)
                continue
            hits = _delivery_trace_hits(path)
            if hits:
                trace_hits.append(f"{rel}:{','.join(hits[:3])}")
        _add_gate(
            gates,
            f"{chapter_id}:export-package-clean",
            manifest.exists()
            and payload.get("schema") == "literary-engineering-workbench/export-package/v0.1"
            and payload.get("include_blocked") is not True
            and not skipped
            and not output_missing
            and not trace_hits,
            "blocking",
            f"{chapter_id} export package is clean",
            f"{chapter_id} 导出包未通过：manifest/schema/include_blocked/skipped/output/trace 有问题；skipped={len(skipped)}，missing={', '.join(output_missing) or 'none'}，trace={'; '.join(trace_hits[:4]) or 'none'}。",
        )

        docx = outputs.get("docx") if isinstance(outputs.get("docx"), dict) else {}
        inspections = outputs.get("docx_inspections") if isinstance(outputs.get("docx_inspections"), dict) else {}
        missing_docx = [str(rel) for rel in docx.values() if not (root / str(rel)).exists()]
        missing_inspections = [str(rel) for rel in inspections.values() if not (root / str(rel)).exists()]
        _add_gate(
            gates,
            f"{chapter_id}:docx-inspection",
            not docx or (not missing_docx and not missing_inspections and set(docx) <= set(inspections)),
            "blocking",
            f"{chapter_id} DOCX outputs have inspection reports or DOCX was not requested",
            f"{chapter_id} DOCX 导出缺少文件或 inspection：docx_missing={', '.join(missing_docx) or 'none'}，inspection_missing={', '.join(missing_inspections) or 'none'}。",
        )

        run_id = f"release-{chapter_id}"
        approval = _approval_record(root, run_id)
        _add_gate(
            gates,
            f"{chapter_id}:release-approval",
            str(approval.get("decision") or "") == "approve",
            "blocking",
            f"{chapter_id} release approve record exists",
            f"{chapter_id} 缺少 run_id={run_id} 的用户 approve 记录；平台 Agent 不能自批发布。",
        )

        publish_manifest = root / "releases" / chapter_id / "formal-release" / "publish_manifest.json"
        latest = root / "releases" / chapter_id / "latest.json"
        publish_payload = _read_json(publish_manifest)
        latest_payload = _read_json(latest)
        published_outputs = publish_payload.get("published_outputs") if isinstance(publish_payload.get("published_outputs"), dict) else {}
        missing_published = [str(rel) for rel in published_outputs.values() if not (root / str(rel)).exists()]
        _add_gate(
            gates,
            f"{chapter_id}:publish-release",
            publish_manifest.exists()
            and latest.exists()
            and publish_payload.get("schema") == "literary-engineering-workbench/publish-chapter/v0.1"
            and publish_payload.get("status") == "published"
            and (publish_payload.get("approval") if isinstance(publish_payload.get("approval"), dict) else {}).get("decision") == "approve"
            and latest_payload.get("manifest") == _rel(publish_manifest, root)
            and published_outputs
            and not missing_published,
            "blocking",
            f"{chapter_id} published release exists and latest points to it",
            f"{chapter_id} 发布未闭合：formal-release/latest/approval/status/outputs 有问题；missing_published={', '.join(missing_published) or 'none'}。",
        )


def _delivery_trace_hits(path: Path) -> list[str]:
    text = _read_text(path)
    patterns = {
        "scene-id": r"\bscene_\d{4}\b",
        "agent-task": r"\[AGENT_TASK:",
        "canon-note-heading": r"(?m)^#{1,4}\s*(新增事实候选|人物状态变化|关系变化|伏笔变化|需要人工确认|世界状态变化|状态变化候选)\s*$",
        "review-heading": r"(?m)^#{1,4}\s*(审查|AgentReview|Route Audit|平台 Agent 任务|门禁问题汇总)\b",
        "workflow-path": r"\b(workflow/tasks|reviews/agent|characters/state_patches|drafts/promotions|branch_manifest|roleplay_simulation)\b",
    }
    hits = []
    for label, pattern in patterns.items():
        if re.search(pattern, text):
            hits.append(label)
    return hits
