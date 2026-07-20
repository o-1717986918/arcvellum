"""Persistent formal-route state ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .agent_tasks import agent_task_completion_status
from .asset_workshop import ASSET_CANDIDATE_DIRS
from .canon_evolver import canon_writeback_status
from .candidate_promotion import candidate_generation_gate, candidate_review_gate
from .flow_gates import branch_selection_status
from .reader_experience import reader_experience_contract
from .style_prompt import style_prompt_quality_report
from .word_budget import scene_word_budget_contract


@dataclass(frozen=True)
class WorkflowStateResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    route: str
    scene_count: int
    blocked_count: int
    ready_count: int
    next_action_count: int


def build_workflow_state(
    project_root: Path,
    *,
    route: str = "scene-development",
    output: Path | None = None,
    json_output: Path | None = None,
) -> WorkflowStateResult:
    """Write a persistent state ledger for the formal route."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    normalized_route = _normalize_route(route) or "scene-development"
    scenes = _scene_states(root) if normalized_route in {"scene-development", "overall"} else []
    longform = _longform_state(root) if normalized_route in {"longform-planning", "overall"} else {}
    source_ingests = _source_ingest_states(root) if normalized_route in {"source-ingest", "overall"} else []
    styles = _style_engineering_states(root) if normalized_route in {"style-engineering", "overall"} else []
    assets = _asset_states(root, include_intake=normalized_route == "character-and-world-assets") if normalized_route in {"character-and-world-assets", "overall"} else []
    audits = [_review_audit_state(root)] if normalized_route in {"review-and-audit", "overall"} else []
    exports = _export_release_states(root) if normalized_route in {"export-and-release", "overall"} else []
    longform_blocked = 1 if longform and longform.get("status") != "ready" else 0
    longform_ready = 1 if longform and longform.get("status") == "ready" else 0
    summary = {
        "route": normalized_route,
        "scene_count": len(scenes),
        "source_ingest_count": len(source_ingests),
        "style_profile_count": len(styles),
        "asset_count": len(assets),
        "audit_count": len(audits),
        "export_count": len(exports),
        "ready_count": (
            sum(1 for scene in scenes if scene["status"] == "ready")
            + longform_ready
            + sum(1 for item in source_ingests if item["status"] == "ready")
            + sum(1 for item in styles if item["status"] == "ready")
            + sum(1 for item in assets if item["status"] == "ready")
            + sum(1 for item in audits if item["status"] == "ready")
            + sum(1 for item in exports if item["status"] == "ready")
        ),
        "blocked_count": (
            sum(1 for scene in scenes if scene["status"] != "ready")
            + longform_blocked
            + sum(1 for item in source_ingests if item["status"] != "ready")
            + sum(1 for item in styles if item["status"] != "ready")
            + sum(1 for item in assets if item["status"] != "ready")
            + sum(1 for item in audits if item["status"] != "ready")
            + sum(1 for item in exports if item["status"] != "ready")
        ),
        "next_action_count": (
            sum(1 for scene in scenes if scene.get("next_action"))
            + (1 if longform and longform.get("next_action") else 0)
            + sum(1 for item in source_ingests if item.get("next_action"))
            + sum(1 for item in styles if item.get("next_action"))
            + sum(1 for item in assets if item.get("next_action"))
            + sum(1 for item in audits if item.get("next_action"))
            + sum(1 for item in exports if item.get("next_action"))
        ),
        "longform_status": longform.get("status", "") if isinstance(longform, dict) else "",
    }
    payload = {
        "schema": "literary-engineering-workbench/formal-route-state/v1",
        "generated_at": _now(),
        "project_root": str(root),
        "route": normalized_route,
        "summary": summary,
        "scenes": scenes,
        "longform": longform,
        "source_ingests": source_ingests,
        "styles": styles,
        "assets": assets,
        "audits": audits,
        "exports": exports,
        "rules": [
            "This state ledger is advisory plus auditable; command-level gates remain authoritative.",
            "A step is pass only when the formal CLI artifact and its platform-agent completion marker both exist where required.",
            "Formal Skill hosts must not use allow/unreview/include-blocked debug flags to move the state forward.",
        ],
    }
    markdown_path = _resolve_output(root, output, "workflow", "route_state.md")
    json_path = _resolve_output(root, json_output, "workflow", "route_state.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    return WorkflowStateResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        route=normalized_route,
        scene_count=summary["scene_count"],
        blocked_count=summary["blocked_count"],
        ready_count=summary["ready_count"],
        next_action_count=summary["next_action_count"],
    )


def _scene_states(root: Path) -> list[dict[str, object]]:
    scenes = root / "scenes"
    if not scenes.exists():
        return []
    return [_scene_state(root, path) for path in sorted(scenes.glob("*.yaml")) if not path.name.startswith("_")]


def _longform_state(root: Path) -> dict[str, object]:
    steps = [
        _word_budget_file_step(root),
        _longform_task_step(
            "budget-agent-task",
            root,
            root / "plot" / "word_budget" / "word_budget.agent_tasks.md",
            [root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"],
            "complete word_budget.agent_tasks.md, budgeted outline candidate, and budget review",
        ),
        _longform_review_step(
            "budget-review",
            root / "reviews" / "word_budget" / "word_budget_review.md",
            "write a clean word-budget review with conclusion: pass",
        ),
        _longform_task_step(
            "scene-inventory-agent-task",
            root,
            root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md",
            [root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"],
            "complete scene_inventory_expansion.agent_tasks.md, scene inventory candidate, and review",
        ),
        _longform_review_step(
            "scene-inventory-review",
            root / "reviews" / "word_budget" / "scene_inventory_review.md",
            "write a clean scene inventory review with conclusion: pass",
        ),
        _longform_task_step(
            "chapter-obligation-agent-task",
            root,
            root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md",
            [],
            "complete chapter_obligations.agent_tasks.md and write per-chapter reader contracts",
        ),
        _longform_review_step(
            "chapter-obligation-review",
            root / "reviews" / "word_budget" / "chapter_obligation_review.md",
            "write a clean chapter obligation review with conclusion: pass",
        ),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": "longform",
        "scene_id": "longform",
        "scene": "project.yaml",
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _word_budget_file_step(root: Path) -> dict[str, object]:
    json_path = root / "plot" / "word_budget" / "word_budget.json"
    markdown_path = root / "plot" / "word_budget" / "word_budget.md"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    obligation_task = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    required = [json_path, markdown_path, budget_task, scene_task, obligation_task]
    missing = [_rel(path, root) for path in required if not path.exists()]
    if missing:
        return {
            "key": "word-budget-file",
            "status": "missing",
            "path": _rel(json_path, root),
            "message": "missing " + ", ".join(missing),
            "next_action": "run word-budget / longform-budget to create budget JSON, report, scene-inventory sidecar, and chapter-obligation sidecar",
        }
    payload = _read_json(json_path)
    if not payload or payload.get("schema") != "literary-engineering-workbench/word-budget/v1":
        return {
            "key": "word-budget-file",
            "status": "invalid",
            "path": _rel(json_path, root),
            "message": "word_budget.json is invalid or has wrong schema",
            "next_action": "rerun word-budget / longform-budget",
        }
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    return {
        "key": "word-budget-file",
        "status": "pass",
        "path": _rel(json_path, root),
        "message": f"word budget exists; status={payload.get('status', '')}",
        "target_words": totals.get("target_words", 0),
        "chapter_count": totals.get("chapter_count", 0),
        "scene_count": totals.get("scene_count", 0),
        "next_action": "",
    }


def _longform_review_step(key: str, path: Path, next_action: str) -> dict[str, object]:
    conclusion = _static_review_conclusion(path)
    return {
        "key": key,
        "status": "pass" if conclusion == "pass" else conclusion or "missing",
        "path": str(path),
        "message": f"conclusion={conclusion or 'missing'}",
        "next_action": "" if conclusion == "pass" else next_action,
    }


def _source_ingest_states(root: Path) -> list[dict[str, object]]:
    imports = root / "sources" / "imports"
    if not imports.exists():
        return []
    states: list[dict[str, object]] = []
    for manifest in sorted(imports.glob("*/source_manifest.json")):
        states.append(_source_ingest_state(root, manifest.parent))
    return states


def _source_ingest_state(root: Path, import_dir: Path) -> dict[str, object]:
    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    manifest = _read_json(manifest_path)
    work_id = str(manifest.get("work_id") or import_dir.name)
    candidate_outputs = _source_candidate_outputs(manifest)
    review_path = root / str(candidate_outputs.get("review") or f"reviews/source_ingest/{work_id}_extraction_review.md")
    candidate_paths = [root / rel for key, rel in candidate_outputs.items() if key != "review"]
    steps = [
        _source_manifest_step(root, manifest_path, report_path, task_path),
        _source_extraction_step(root, task_path, candidate_paths, review_path),
        _longform_review_step(
            "extraction-review",
            review_path,
            "write source-ingest extraction review with conclusion: pass",
        ),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": work_id,
        "work_id": work_id,
        "import_dir": _rel(import_dir, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _source_manifest_step(root: Path, manifest_path: Path, report_path: Path, task_path: Path) -> dict[str, object]:
    missing = [_rel(path, root) for path in (manifest_path, report_path, task_path) if not path.exists()]
    if missing:
        return {
            "key": "source-manifest",
            "status": "missing",
            "path": _rel(manifest_path, root),
            "message": "missing " + ", ".join(missing),
            "next_action": "run source-ingest with source/text/title/work-id to create manifest, report, and extraction sidecar",
        }
    payload = _read_json(manifest_path)
    if payload.get("schema") != "literary-engineering-workbench/source-ingest/v1":
        return {
            "key": "source-manifest",
            "status": "invalid",
            "path": _rel(manifest_path, root),
            "message": "source_manifest.json is invalid or has wrong schema",
            "next_action": "rerun source-ingest or repair the manifest from source evidence",
        }
    return {
        "key": "source-manifest",
        "status": "pass",
        "path": _rel(manifest_path, root),
        "message": f"source manifest exists; chunks={payload.get('chunk_count', 0)}",
        "next_action": "",
    }


def _source_extraction_step(root: Path, task_path: Path, candidate_paths: list[Path], review_path: Path) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    required = [*candidate_paths, review_path]
    missing = [_rel(path, root) for path in required if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": "extraction-agent-task",
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else "complete source extraction sidecar, extracted candidates, review report, and completion marker",
    }


def _source_candidate_outputs(manifest: dict[str, object]) -> dict[str, str]:
    outputs = manifest.get("candidate_outputs") if isinstance(manifest.get("candidate_outputs"), dict) else {}
    return {str(key): str(value) for key, value in outputs.items() if str(value).strip()}


def _style_engineering_states(root: Path) -> list[dict[str, object]]:
    style_root = root / "style"
    if not style_root.exists():
        return []
    states: list[dict[str, object]] = []
    for profile in sorted(style_root.glob("**/style-profile.md")):
        try:
            parts = profile.relative_to(style_root).parts
        except ValueError:
            parts = profile.parts
        if profile.parent == style_root:
            continue
        if "mounted" in parts:
            continue
        states.append(_style_engineering_state(root, profile.parent))
    return states


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
        "next_action": "choose asset type from user direction and run asset-create / agent-create-* to create a platform-agent sidecar",
        "steps": [
            {
                "key": "asset-intake",
                "status": "missing",
                "path": "",
                "message": "no candidate asset or asset creation sidecar found",
                "next_action": "run asset-create / agent-create-* with asset type, brief, optional target id, and optional source",
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
        _asset_approval_step(root, candidate_id),
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
        "next_action": "" if passed else "revise candidate asset or write a clean platform-agent review with status: pass",
    }


def _asset_approval_step(root: Path, candidate_id: str) -> dict[str, object]:
    approval = _approval_record(root, candidate_id)
    passed = str(approval.get("decision") or "") == "approve"
    return {
        "key": "asset-approval",
        "status": "pass" if passed else str(approval.get("decision") or "missing"),
        "path": "workflow/approvals/index.jsonl",
        "message": "approve record exists" if passed else "missing human approve record",
        "next_action": "" if passed else f"ask user for approval and record an approve decision for run_id `{candidate_id}` before promotion",
    }


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


def _review_audit_state(root: Path) -> dict[str, object]:
    canon_lint_json = root / "reviews" / "canon_lint.json"
    canon_review_json = root / "reviews" / "agent" / "canon_review.json"
    canon_review_md = canon_review_json.with_suffix(".md")
    canon_review_task = canon_review_json.with_suffix(".agent_tasks.md")
    committee_json = root / "reviews" / "agent" / "committee_project-final-audit.json"
    committee_md = committee_json.with_suffix(".md")
    committee_task = committee_json.with_suffix(".agent_tasks.md")
    longform_json = root / "reviews" / "longform" / "longform_audit.json"
    steps = [
        _canon_lint_step(root, canon_lint_json),
        _file_step("canon-review-task-file", canon_review_task, "run agent-canon-review to create the platform-agent canon review sidecar"),
        _review_agent_step(root, "canon-review-agent-task", canon_review_task, canon_review_json, canon_review_md, "complete canon review sidecar, JSON, Markdown, and completion marker"),
        _canon_review_pass_step(root, canon_review_json),
        _file_step("longform-audit-file", longform_json, "run longform-audit to create structural longform audit JSON/Markdown"),
        _file_step("committee-task-file", committee_task, "run agent-committee --subject project-final-audit --source reviews/agent/canon_review.md"),
        _review_agent_step(root, "committee-agent-task", committee_task, committee_json, committee_md, "complete committee sidecar, JSON, Markdown, and completion marker"),
        _committee_pass_step(root, committee_json),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": "project-review",
        "scene_id": "project-review",
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _canon_lint_step(root: Path, json_path: Path) -> dict[str, object]:
    report = json_path.with_suffix(".md")
    if not json_path.exists() or not report.exists():
        return {
            "key": "canon-lint-file",
            "status": "missing",
            "path": _rel(json_path, root),
            "message": "missing canon lint report or JSON",
            "next_action": "run canon-lint before platform-agent canon review",
        }
    payload = _read_json(json_path)
    status = str(payload.get("status") or "").strip().lower()
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blocking = int(summary.get("blocking_count", 0) or 0)
    return {
        "key": "canon-lint-file",
        "status": "pass" if status in {"pass", "pass_with_warnings"} and blocking == 0 else status or "blocked",
        "path": _rel(json_path, root),
        "message": f"status={status or 'missing'}; blocking={blocking}; warning={summary.get('warning_count', 0)}",
        "next_action": "" if status in {"pass", "pass_with_warnings"} and blocking == 0 else "fix canon-lint blocking issues before Agent canon review",
    }


def _review_agent_step(root: Path, key: str, task_path: Path, json_path: Path, report_path: Path, next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    missing = [_rel(path, root) for path in (json_path, report_path) if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else next_action,
    }


def _canon_review_pass_step(root: Path, json_path: Path) -> dict[str, object]:
    payload = _read_json(json_path)
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    blocking = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    unresolved = payload.get("unresolved_facts") if isinstance(payload.get("unresolved_facts"), list) else []
    timeline = payload.get("timeline_risks") if isinstance(payload.get("timeline_risks"), list) else []
    passed = conclusion == "pass" and not blocking and not warnings and not unresolved and not timeline
    message = f"conclusion={conclusion or 'missing'}; blocking={len(blocking)}; warnings={len(warnings)}; unresolved={len(unresolved)}; timeline={len(timeline)}"
    return {
        "key": "canon-review-pass",
        "status": "pass" if passed else conclusion or "missing",
        "path": _rel(json_path, root),
        "message": message,
        "next_action": "" if passed else "resolve canon review findings or write a clean platform-agent canon_review.v1 pass",
    }


def _committee_pass_step(root: Path, json_path: Path) -> dict[str, object]:
    payload = _read_json(json_path)
    recommendation = str(payload.get("final_recommendation") or "").strip().lower()
    action_items = payload.get("action_items") if isinstance(payload.get("action_items"), list) else []
    disagreements = payload.get("disagreements") if isinstance(payload.get("disagreements"), list) else []
    passed = recommendation == "approve" and not action_items and not disagreements
    return {
        "key": "committee-pass",
        "status": "pass" if passed else recommendation or "missing",
        "path": _rel(json_path, root),
        "message": f"final_recommendation={recommendation or 'missing'}; action_items={len(action_items)}; disagreements={len(disagreements)}",
        "next_action": "" if passed else "resolve committee action items/disagreements and write final_recommendation=approve",
    }


def _export_release_states(root: Path) -> list[dict[str, object]]:
    chapter_ids = _chapter_ids(root)
    return [_export_release_state(root, chapter_id) for chapter_id in chapter_ids]


def _chapter_ids(root: Path) -> list[str]:
    ids: set[str] = set()
    chapters = root / "plot" / "chapters"
    if chapters.exists():
        ids.update(path.stem for path in chapters.glob("*.json"))
    scenes = root / "scenes"
    if scenes.exists():
        for path in scenes.glob("*.yaml"):
            if path.name.startswith("_"):
                continue
            chapter_id = _scene_chapter_id(_read(path))
            if chapter_id:
                ids.add(chapter_id)
    releases = root / "releases"
    if releases.exists():
        ids.update(path.name for path in releases.iterdir() if path.is_dir())
    return sorted(ids) or ["chapter_0001"]


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
        _release_approval_step(root, approval_run_id),
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
    required = [outputs.get("novel"), outputs.get("screenplay"), outputs.get("video_prompt_pack")]
    missing = [str(item) for item in required if not item or not (root / str(item)).exists()]
    include_blocked = bool(payload.get("include_blocked"))
    passed = manifest_path.exists() and not skipped and not include_blocked and not missing
    message = f"skipped={len(skipped)}; include_blocked={include_blocked}; missing_outputs={len(missing)}"
    return {
        "key": "export-package",
        "status": "pass" if passed else "missing" if not manifest_path.exists() else "blocked",
        "path": _rel(manifest_path, root),
        "message": message,
        "next_action": "" if passed else f"run export-package for {chapter_id}; do not use --include-blocked",
    }


def _release_approval_step(root: Path, run_id: str) -> dict[str, object]:
    approval = _approval_record(root, run_id)
    passed = str(approval.get("decision") or "") == "approve"
    return {
        "key": "release-approval",
        "status": "pass" if passed else str(approval.get("decision") or "missing"),
        "path": "workflow/approvals/index.jsonl",
        "message": "approve record exists" if passed else f"missing human approve record for {run_id}",
        "next_action": "" if passed else f"ask user to approve release candidate and record approval run_id `{run_id}`",
    }


def _publish_release_step(root: Path, latest_path: Path, release_dir: Path) -> dict[str, object]:
    latest = _read_json(latest_path)
    manifest = release_dir / "publish_manifest.json"
    payload = _read_json(manifest)
    status = str(payload.get("status") or "").strip().lower()
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    passed = (
        latest_path.exists()
        and manifest.exists()
        and status == "published"
        and not payload.get("allow_unapproved")
        and approval.get("decision") == "approve"
        and latest.get("manifest") == _rel(manifest, root)
    )
    return {
        "key": "publish-release",
        "status": "pass" if passed else "missing" if not manifest.exists() else "blocked",
        "path": _rel(manifest, root),
        "message": f"latest={bool(latest)}; status={status or 'missing'}; approval={approval.get('decision') or 'missing'}",
        "next_action": "" if passed else "run publish-chapter with approval run id; do not use --allow-unapproved",
    }


def _style_engineering_state(root: Path, profile_dir: Path) -> dict[str, object]:
    profile_id = _rel(profile_dir, root)
    task_path = profile_dir / "style_prompt.agent_tasks.md"
    prompt_path = profile_dir / "style_prompt.md"
    agent_json = profile_dir / "style_prompt.agent.json"
    steps = [
        _style_profile_step(root, profile_dir),
        _file_step("style-prompt-task-file", task_path, "run style-prompt on this profile to create platform-agent prompt sidecar"),
        _style_prompt_agent_step(root, task_path, prompt_path, agent_json),
        _style_prompt_quality_step(root, prompt_path),
        _style_eval_readiness_step(root, profile_dir),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": _slug_profile_id(profile_id),
        "profile_id": _slug_profile_id(profile_id),
        "profile_dir": profile_id,
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _style_profile_step(root: Path, profile_dir: Path) -> dict[str, object]:
    profile = profile_dir / "style-profile.md"
    metrics = profile_dir / "style_metrics.json"
    missing = [_rel(path, root) for path in (profile, metrics) if not path.exists()]
    if missing:
        return {
            "key": "style-profile",
            "status": "missing",
            "path": _rel(profile_dir, root),
            "message": "missing " + ", ".join(missing),
            "next_action": "run style-profile / style-lab-compile to create style-profile.md and style_metrics.json",
        }
    return {
        "key": "style-profile",
        "status": "pass",
        "path": _rel(profile_dir, root),
        "message": "style profile and metrics exist",
        "next_action": "",
    }


def _style_prompt_agent_step(root: Path, task_path: Path, prompt_path: Path, agent_json: Path) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    missing = [_rel(path, root) for path in (prompt_path, agent_json) if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": "style-prompt-agent-task",
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else "complete style_prompt.agent_tasks.md, style_prompt.md, style_prompt.agent.json, and completion marker",
    }


def _style_prompt_quality_step(root: Path, prompt_path: Path) -> dict[str, object]:
    if not prompt_path.exists():
        return {
            "key": "style-prompt-quality",
            "status": "missing",
            "path": _rel(prompt_path, root),
            "message": "style_prompt.md missing",
            "next_action": "write style_prompt.md through platform-agent task",
        }
    report = style_prompt_quality_report(_read(prompt_path))
    passed = bool(report.get("length_ok")) and bool(report.get("structure_ok"))
    missing = ", ".join(str(item) for item in report.get("missing_blocks", []))
    message = (
        f"detail_chars={report.get('detail_chars')} "
        f"({report.get('detail_count_unit')}); missing_blocks={missing or 'none'}"
    )
    return {
        "key": "style-prompt-quality",
        "status": "pass" if passed else "blocked",
        "path": _rel(prompt_path, root),
        "message": message,
        "next_action": "" if passed else "revise style_prompt.md to 500-2500 Chinese-content detail chars with all required prompt blocks",
    }


def _style_eval_readiness_step(root: Path, profile_dir: Path) -> dict[str, object]:
    evals = _accepted_style_evals(profile_dir)
    if evals:
        return {
            "key": "style-eval-readiness",
            "status": "pass",
            "path": _rel(profile_dir / "evaluation_results", root),
            "message": f"accepted_evaluations={len(evals)}",
            "next_action": "",
        }
    all_evals = sorted((profile_dir / "evaluation_results").glob("*/style_eval_*.json"))
    return {
        "key": "style-eval-readiness",
        "status": "missing" if not all_evals else "blocked",
        "path": _rel(profile_dir / "evaluation_results", root),
        "message": "no accepted style_eval JSON found",
        "next_action": "run style-prompt-eval/style-eval and create at least one accepted style_eval JSON before building or mounting a Style Skill",
    }


def _accepted_style_evals(profile_dir: Path) -> list[dict[str, object]]:
    accepted: list[dict[str, object]] = []
    for path in sorted((profile_dir / "evaluation_results").glob("*/style_eval_*.json")):
        payload = _read_json(path)
        risk = str(payload.get("risk_level") or "")
        try:
            score = float(payload.get("overall_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        if risk in {"high_copy_risk", "low_similarity"} or score < 45:
            continue
        accepted.append({"path": str(path), "overall_score": score, "risk_level": risk})
    return accepted


def _agent_task_base(task_path: Path) -> Path:
    name = task_path.name
    suffix = ".agent_tasks.md"
    if name.endswith(suffix):
        return task_path.with_name(name[: -len(suffix)])
    return task_path.with_suffix("")


def _infer_asset_type(root: Path, candidate_path: Path) -> str:
    try:
        rel = candidate_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = candidate_path.as_posix()
    for asset_type, folder in ASSET_CANDIDATE_DIRS.items():
        if rel.startswith(folder.as_posix() + "/"):
            return asset_type
    return "character"


def _approval_record(root: Path, candidate_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("run_id") == candidate_id:
            latest = payload if isinstance(payload, dict) else {}
    return latest


def _scene_state(root: Path, scene_path: Path) -> dict[str, object]:
    scene_id = _scene_id(scene_path)
    candidate = _promotion_candidate_path(root, scene_id) or _latest_scene_candidate(root, scene_id)
    steps = [
        _file_step("context-packet", root / "memory" / "context_packets" / f"{scene_id}.md", "run context --scene scenes/{scene}.yaml".format(scene=scene_id)),
        _file_step("context-trace", root / "memory" / "context_packets" / f"{scene_id}.trace.json", "rerun context --scene scenes/{scene}.yaml and inspect context trace".format(scene=scene_id)),
        _file_step("roleplay-simulation", root / "branches" / scene_id / "roleplay_simulation.md", "run simulate-scene --agent"),
        _task_step("roleplay-agent-task", root, root / "branches" / scene_id / "roleplay_simulation.agent_tasks.md", "complete roleplay_simulation.agent_tasks.md and marker"),
        _file_step("branch-manifest", root / "branches" / scene_id / "branch_manifest.json", "run branch-simulate --agent"),
        _task_step("branch-agent-task", root, root / "branches" / scene_id / "branch_manifest.agent_tasks.md", "complete branch_manifest.agent_tasks.md and marker"),
        _branch_selection_step(root / "branches" / scene_id / "branch_selection.md"),
        _file_step("composition-json", root / "drafts" / "compositions" / f"{scene_id}_composition.json", "run compose-scene --agent-tasks"),
        _task_step("composition-agent-task", root, root / "drafts" / "compositions" / f"{scene_id}_composition.agent_tasks.md", "complete scene composition sidecar and marker"),
        _word_budget_step(root, scene_path),
        _reader_experience_step(root, scene_path),
        _candidate_step(root, scene_id, candidate),
        _task_step("generation-agent-task", root, candidate.with_suffix(".agent_tasks.md") if candidate else root / "drafts" / "candidates" / f"{scene_id}-platform-agent.agent_tasks.md", "complete generation sidecar and marker"),
        _review_step(root, scene_id, candidate),
        _task_step("agent-review-task", root, root / "reviews" / "agent" / f"{scene_id}_scene_review.agent_tasks.md", "complete AgentReview sidecar and marker"),
        _file_step("promotion-manifest", root / "drafts" / "promotions" / f"{scene_id}_promotion.json", "run promote-candidate after exact candidate review"),
        _file_step("promoted-draft", root / "drafts" / "scenes" / f"{scene_id}.md", "promote a reviewed candidate into drafts/scenes"),
        _static_review_step(root, scene_id),
        _file_step("state-patch-json", root / "characters" / "state_patches" / f"{scene_id}_state_patch.json", "run state-evolve --agent-tasks"),
        _task_step("state-agent-task", root, root / "characters" / "state_patches" / f"{scene_id}_state_patch.agent_tasks.md", "complete state-evolve sidecar and marker"),
        _canon_writeback_step(root, scene_id),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _file_step(key: str, path: Path, next_action: str) -> dict[str, object]:
    return {
        "key": key,
        "status": "pass" if path.exists() else "missing",
        "path": str(path),
        "message": "exists" if path.exists() else "missing",
        "next_action": "" if path.exists() else next_action,
    }


def _task_step(key: str, root: Path, path: Path, next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(path, root=root)
    complete = state.get("complete") is True
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(path, root),
        "completion": state.get("completion", ""),
        "message": state.get("message", ""),
        "next_action": "" if complete else next_action,
    }


def _longform_task_step(key: str, root: Path, path: Path, required_outputs: list[Path], next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(path, root=root)
    missing = [_rel(item, root) for item in required_outputs if not item.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else next_action,
    }


def _branch_selection_step(path: Path) -> dict[str, object]:
    state = branch_selection_status(path)
    return {
        "key": "branch-selection",
        "status": "pass" if state["status"] == "selected" else state["status"],
        "path": str(path),
        "message": state["message"],
        "selected_branch": state["selected_branch"],
        "next_action": "" if state["status"] == "selected" else "fill branch_selection.md with decision: selected and selected_branch",
    }


def _word_budget_step(root: Path, scene_path: Path) -> dict[str, object]:
    contract = scene_word_budget_contract(root, scene_path)
    status = str(contract.get("status") or "")
    passed = status in {"pass", "not_required"}
    return {
        "key": "scene-word-budget-contract",
        "status": "pass" if passed else status or "missing",
        "path": str(contract.get("budget_path") or ""),
        "message": contract.get("message", ""),
        "target_words": contract.get("target_words", 0),
        "min_words": contract.get("min_words", 0),
        "max_words": contract.get("max_words", 0),
        "next_action": "" if passed else "run word-budget, handle budget sidecars, review scene inventory, then retry generation",
    }


def _reader_experience_step(root: Path, scene_path: Path) -> dict[str, object]:
    contract = reader_experience_contract(root, scene_path)
    status = str(contract.get("status") or "")
    passed = status in {"pass", "not_required"}
    chapter = contract.get("chapter_obligation") if isinstance(contract.get("chapter_obligation"), dict) else {}
    return {
        "key": "reader-experience-contract",
        "status": "pass" if passed else status or "missing",
        "path": str(chapter.get("path") or ""),
        "message": contract.get("message", ""),
        "chapter_obligation_id": chapter.get("chapter_obligation_id", ""),
        "next_action": "" if passed else "run chapter-obligation, handle its sidecar, and fill reader_experience_by_scene before prose generation",
    }


def _candidate_step(root: Path, scene_id: str, candidate: Path | None) -> dict[str, object]:
    if candidate is None:
        return {
            "key": "candidate-generation-provenance",
            "status": "missing",
            "path": "",
            "message": "no formal candidate found",
            "next_action": "run generate-scene, then have the main platform agent write candidate Markdown and manifest",
        }
    gate = candidate_generation_gate(root, scene_id, candidate)
    return {
        "key": "candidate-generation-provenance",
        "status": "pass" if gate.get("status") == "pass" else str(gate.get("status") or "missing"),
        "path": _rel(candidate, root),
        "message": gate.get("message", ""),
        "next_action": "" if gate.get("status") == "pass" else "complete generate-scene sidecar, candidate Markdown, manifest, prompt manifest, and completion marker",
    }


def _review_step(root: Path, scene_id: str, candidate: Path | None) -> dict[str, object]:
    if candidate is None:
        return {
            "key": "candidate-review",
            "status": "missing",
            "path": f"reviews/agent/{scene_id}_scene_review.json",
            "message": "no candidate to review",
            "next_action": "generate a formal candidate first",
        }
    gate = candidate_review_gate(root, scene_id, candidate)
    return {
        "key": "candidate-review",
        "status": "pass" if gate.get("status") == "pass" else str(gate.get("status") or "missing"),
        "path": str(gate.get("review") or ""),
        "message": gate.get("message", ""),
        "next_action": "" if gate.get("status") == "pass" else "run agent-review-scene --draft <candidate>, then write review JSON/MD and completion marker",
    }


def _static_review_step(root: Path, scene_id: str) -> dict[str, object]:
    path = root / "reviews" / f"{scene_id}-review.md"
    conclusion = _static_review_conclusion(path)
    return {
        "key": "static-review",
        "status": "pass" if conclusion == "pass" else conclusion or "missing",
        "path": _rel(path, root),
        "message": f"conclusion={conclusion or 'missing'}",
        "next_action": "" if conclusion == "pass" else "run review-scene on the promoted draft and resolve notes",
    }


def _canon_writeback_step(root: Path, scene_id: str) -> dict[str, object]:
    status = canon_writeback_status(root, scene_id)
    state = str(status.get("status") or "")
    passed = state in {"pass", "not_required"}
    key = "canon-agent-task" if state == "task_incomplete" else "canon-patch-json"
    next_action = "run canon-evolve, have the platform agent write canon patch/no-change rationale, then complete the sidecar"
    return {
        "key": key,
        "status": "pass" if passed else state or "unknown",
        "path": status.get("json", ""),
        "message": status.get("message", ""),
        "next_action": "" if passed else next_action,
    }


def _promotion_candidate_path(root: Path, scene_id: str) -> Path | None:
    payload = _read_json(root / "drafts" / "promotions" / f"{scene_id}_promotion.json")
    candidate = str(payload.get("candidate") or "").strip()
    if not candidate:
        return None
    path = Path(candidate)
    return path if path.is_absolute() else root / path


def _latest_scene_candidate(root: Path, scene_id: str) -> Path | None:
    candidates: list[Path] = []
    for directory, pattern in (
        (root / "drafts" / "candidates", f"{scene_id}-*.md"),
        (root / "drafts" / "revisions", f"{scene_id}_revision.md"),
    ):
        if directory.exists():
            candidates.extend(path for path in directory.glob(pattern) if not path.name.endswith(".agent_tasks.md") and not path.name.endswith(".prompt.md"))
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def _static_review_conclusion(path: Path) -> str:
    text = _read(path)
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _scene_id(path: Path) -> str:
    text = _read(path)
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    if match:
        scene_id = match.group(1).strip().strip("\"'")
        if scene_id:
            return scene_id
    return path.stem


def _scene_chapter_id(text: str) -> str:
    match = re.search(r"(?m)^\s*chapter_id:\s*['\"]?([^'\"\n#]+)", text)
    return match.group(1).strip().strip("\"'") if match else ""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        f"# Formal Route State：{payload['route']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 场景数：{summary['scene_count']}",
        f"- Ready：{summary['ready_count']}",
        f"- Blocked：{summary['blocked_count']}",
        f"- Next actions：{summary['next_action_count']}",
        "",
        "## Scene State",
        "",
        "| 场景 | 状态 | 当前步骤 | 下一步 |",
        "| --- | --- | --- | --- |",
    ]
    for scene in payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        lines.append(
            f"| {scene.get('scene_id', '')} | {scene.get('status', '')} | {scene.get('current_step', '')} | {scene.get('next_action', '')} |"
        )
    longform = payload.get("longform") if isinstance(payload.get("longform"), dict) else {}
    if longform:
        lines.extend(["", "## Longform State", ""])
        lines.append(
            f"- 状态：`{longform.get('status', '')}`；当前步骤：`{longform.get('current_step', '')}`；下一步：{longform.get('next_action', '') or 'n/a'}"
        )
        lines.extend(["", "| 步骤 | 状态 | 信息 |", "| --- | --- | --- |"])
        for step in longform.get("steps", []):
            if not isinstance(step, dict):
                continue
            lines.append(f"| {step.get('key', '')} | {step.get('status', '')} | {step.get('message', '')} |")
    source_ingests = payload.get("source_ingests") if isinstance(payload.get("source_ingests"), list) else []
    if source_ingests:
        lines.extend(["", "## Source Ingest State", "", "| work_id | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in source_ingests:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('work_id', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    styles = payload.get("styles") if isinstance(payload.get("styles"), list) else []
    if styles:
        lines.extend(["", "## Style Engineering State", "", "| profile | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in styles:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('profile_dir', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
    if assets:
        lines.extend(["", "## Asset State", "", "| candidate | 类型 | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- | --- |"])
        for item in assets:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('candidate_id', '')} | {item.get('asset_type', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    audits = payload.get("audits") if isinstance(payload.get("audits"), list) else []
    if audits:
        lines.extend(["", "## Review And Audit State", "", "| target | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in audits:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('target_id', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    exports = payload.get("exports") if isinstance(payload.get("exports"), list) else []
    if exports:
        lines.extend(["", "## Export And Release State", "", "| chapter | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in exports:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('chapter_id', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    lines.extend(["", "## Details", ""])
    for scene in payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        lines.extend([f"### {scene.get('scene_id', '')}", ""])
        for step in scene.get("steps", []):
            if not isinstance(step, dict):
                continue
            lines.append(f"- `{step.get('key', '')}`：{step.get('status', '')}。{step.get('message', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def _slug_profile_id(value: str) -> str:
    text = value.strip().lower().replace("\\", "/").replace("/", "-").replace("_", "-")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "style-profile"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
