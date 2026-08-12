"""Derived state for the formal scene-development route."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from ..canon_evolver import canon_writeback_status
from ..character_state_apply import state_patch_writeback_status
from ..candidate_promotion import candidate_generation_gate, candidate_review_gate
from ..continuity_ledger import continuity_ledger_task_status
from ..context_broker import context_trace_status
from ..flow_gates import branch_selection_status
from ..narrative_rhythm import narrative_rhythm_contract
from ..reader_experience import reader_experience_contract
from ..scene_character_assets import scene_character_asset_requirements
from ..scene_composer import composition_input_digest
from ..tasking.semantic_contracts import semantic_artifact_errors, semantic_artifact_relative_path
from ..word_budget import scene_word_budget_contract
from .historical_truth import preserve_current_historical_style_steps
from .scene_scope import started_scene_ids
from .state_common import (
    _file_step, _read, _read_json, _rel, _semantic_task_step,
    _static_review_conclusion, _task_step,
)
def _scene_states(root: Path) -> list[dict[str, object]]:
    scenes = root / "scenes"
    if not scenes.exists():
        return []
    return [_scene_state(root, path) for path in sorted(scenes.glob("*.yaml")) if not path.name.startswith("_")]


def _scene_paths_for_scope(root: Path, scope: str) -> tuple[list[Path], dict[str, object]]:
    """Select the scene evidence appropriate for a caller's read surface.

    Formal CLI state and audits retain the full scene ledger. A live dashboard,
    however, must not spend tens of seconds recomputing contracts for hundreds
    of untouched planned scenes just to identify the next task. It observes all
    started scenes near the active frontier and one upcoming planned scene.
    """

    paths = [path for path in sorted((root / "scenes").glob("*.yaml")) if not path.name.startswith("_")]
    if scope != "dashboard":
        return paths, _scene_scope_summary(root, paths, mode="full")

    started = started_scene_ids(root)
    started_paths = [path for path in paths if _scene_id(path) in started]
    planned_paths = [path for path in paths if _scene_id(path) not in started]
    active_scene_id = _latest_scene_task_id(root)
    selected: list[Path] = list(started_paths[-12:])
    active_path = next((path for path in paths if _scene_id(path) == active_scene_id), None)
    if active_path is not None and active_path not in selected:
        selected.append(active_path)
    if planned_paths:
        selected.append(planned_paths[0])
    if not selected and paths:
        selected.append(paths[0])
    selected = sorted(set(selected))
    return selected, _scene_scope_summary(root, selected, mode="active-frontier", started_count=len(started_paths))


def _scene_scope_summary(
    root: Path,
    selected: list[Path],
    *,
    mode: str,
    started_count: int | None = None,
) -> dict[str, object]:
    all_paths = [path for path in (root / "scenes").glob("*.yaml") if not path.name.startswith("_")]
    known_started = len(started_scene_ids(root)) if started_count is None else started_count
    total = len(all_paths)
    return {
        "mode": mode,
        "total_scene_count": total,
        "started_scene_count": known_started,
        "planned_scene_count": max(0, total - known_started),
        "observed_scene_count": len(selected),
        "truncated": len(selected) < total,
    }


def next_scene_workflow_state(root: Path, scene: Path | str | None = None) -> dict[str, object] | None:
    scene_paths = sorted(path for path in (root / "scenes").glob("*.yaml") if not path.name.startswith("_"))
    if scene:
        selected = Path(scene)
        if not selected.is_absolute():
            selected = root / selected
        return _scene_state(root, selected.resolve()) if selected.is_file() else None
    if not scene_paths:
        return None

    latest_scene_id = _latest_scene_task_id(root)
    start = 0
    if latest_scene_id:
        start = next((index for index, path in enumerate(scene_paths) if _scene_id(path) == latest_scene_id), 0)
    for path in scene_paths[start:]:
        state = _scene_state(root, path)
        if state.get("status") != "ready":
            return state
    for path in scene_paths[:start]:
        state = _scene_state(root, path)
        if state.get("status") != "ready":
            return state
    return None


def _latest_scene_task_id(root: Path) -> str:
    latest: tuple[int, str] | None = None
    tasks = root / "workflow" / "tasks"
    if not tasks.is_dir():
        return ""
    for path in tasks.glob("*.task.json"):
        payload = _read_json(path)
        if payload.get("route") != "scene-development":
            continue
        scene_id = str(payload.get("scene_id") or "").strip()
        if not scene_id:
            continue
        stamp = path.stat().st_mtime_ns
        if latest is None or stamp > latest[0]:
            latest = (stamp, scene_id)
    return latest[1] if latest else ""

def _scene_state(root: Path, scene_path: Path) -> dict[str, object]:
    scene_id = _scene_id(scene_path)
    candidate = _current_scene_candidate(root, scene_id)
    context_trace = root / "memory" / "context_packets" / f"{scene_id}.trace.json"
    roleplay = root / "branches" / scene_id / "roleplay_simulation.md"
    roleplay_result = root / semantic_artifact_relative_path("roleplay-agent-task", scene_id)
    branch_manifest = root / "branches" / scene_id / "branch_manifest.json"
    steps = [
        _scene_character_assets_step(root, scene_path),
        _file_step("context-packet", root / "memory" / "context_packets" / f"{scene_id}.md", "run context --scene scenes/{scene}.yaml".format(scene=scene_id)),
        _context_trace_step(root, scene_id),
        _dependency_file_step("roleplay-simulation", roleplay, [context_trace], "run simulate-scene --agent"),
        _semantic_task_step("roleplay-agent-task", root, scene_id, root / "branches" / scene_id / "roleplay_simulation.agent_tasks.md", "complete the RP semantic result and sidecar marker"),
        _dependency_file_step("branch-manifest", branch_manifest, [roleplay, roleplay_result], "run branch-simulate --agent"),
        _task_step("branch-agent-task", root, root / "branches" / scene_id / "branch_manifest.agent_tasks.md", "complete branch_manifest.agent_tasks.md and marker"),
        _branch_selection_step(root / "branches" / scene_id / "branch_selection.md", dependency=branch_manifest),
        _word_budget_step(root, scene_path),
        _reader_experience_step(root, scene_path),
        _narrative_rhythm_step(root, scene_path),
        _composition_step(root, scene_path),
        _semantic_task_step("composition-agent-task", root, scene_id, root / "drafts" / "compositions" / f"{scene_id}_composition.agent_tasks.md", "complete the composition semantic review and sidecar marker"),
        _candidate_step(root, scene_id, candidate),
        _task_step("generation-agent-task", root, candidate.with_suffix(".agent_tasks.md") if candidate else root / "drafts" / "candidates" / f"{scene_id}-platform-agent.agent_tasks.md", "complete generation sidecar and marker"),
        _review_step(root, scene_id, candidate),
        _task_step("agent-review-task", root, root / "reviews" / "agent" / f"{scene_id}_scene_review.agent_tasks.md", "complete AgentReview sidecar and marker"),
        _promotion_step(root, scene_id, candidate),
        _promoted_draft_step(root, scene_id, candidate),
        _static_review_step(root, scene_id),
        _file_step("state-patch-json", root / "characters" / "state_patches" / f"{scene_id}_state_patch.json", "run state-evolve --agent-tasks"),
        _semantic_task_step("state-agent-task", root, scene_id, root / "characters" / "state_patches" / f"{scene_id}_state_patch.agent_tasks.md", "complete the state semantic review and sidecar marker"),
        _state_patch_writeback_step(root, scene_id),
        _canon_writeback_step(root, scene_id),
        _file_step("continuity-ledger-prepare", root / "plot" / "ledger_deltas" / f"{scene_id}.agent_tasks.md", "run prepare-continuity-ledger after the promoted scene"),
        _continuity_ledger_step(root, scene_id, review=False),
        _file_step("continuity-ledger-review-prepare", root / "reviews" / "continuity" / f"{scene_id}_ledger_review.agent_tasks.md", "run prepare-continuity-ledger-review after the delta is complete"),
        _continuity_ledger_step(root, scene_id, review=True),
        _file_step("continuity-ledger-apply", root / "plot" / "ledger_deltas" / f"{scene_id}_apply.json", "run apply-continuity-ledger after independent review passes"),
    ]
    steps = preserve_current_historical_style_steps(root, scene_id, steps)
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _scene_character_assets_step(root: Path, scene_path: Path) -> dict[str, object]:
    """Resolve durable named participants before context, RP, or prose."""

    requirements = scene_character_asset_requirements(root, scene_path)
    if not requirements:
        return {
            "key": "scene-character-assets",
            "status": "pass",
            "path": _rel(scene_path, root),
            "message": "all durable named participants resolve to formal character assets",
            "next_action": "",
        }
    missing_tasks = [item for item in requirements if not item.task_path.is_file()]
    names = "、".join(item.name for item in requirements)
    if missing_tasks:
        return {
            "key": "scene-character-asset-tasks",
            "status": "missing",
            "path": _rel(scene_path, root),
            "message": f"named participants require candidate-asset task contracts: {names}",
            "next_action": f"run prepare-scene-character-assets --scene {_rel(scene_path, root)}",
        }
    return {
        "key": "scene-character-asset-dependency",
        "status": "dependency_pending",
        "path": _rel(scene_path, root),
        "message": f"candidate assets await review, approval, and promotion: {names}",
        "next_action": "complete the character-and-world-assets route before returning to scene-development",
    }


def _context_trace_step(root: Path, scene_id: str) -> dict[str, object]:
    context = root / "memory" / "context_packets" / f"{scene_id}.md"
    trace = context_trace_status(root, scene_id, context)
    return {
        "key": "context-trace",
        "status": "pass" if trace.passed else trace.status,
        "path": _rel(trace.path, root),
        "message": trace.message,
        "next_action": "" if trace.passed else f"rerun context --scene scenes/{scene_id}.yaml and inspect context trace",
    }


def _dependency_file_step(key: str, path: Path, dependencies: list[Path], next_action: str) -> dict[str, object]:
    """Treat outputs older than their formal inputs as stale evidence."""

    if not path.is_file():
        return _file_step(key, path, next_action)
    current_dependencies = [dependency for dependency in dependencies if dependency.is_file()]
    newest = max(current_dependencies, key=lambda dependency: dependency.stat().st_mtime_ns) if current_dependencies else None
    if newest is not None and path.stat().st_mtime_ns < newest.stat().st_mtime_ns:
        return {
            "key": key,
            "status": "stale",
            "path": str(path),
            "message": f"formal input was refreshed after this artifact: {newest.name}",
            "next_action": next_action,
        }
    return _file_step(key, path, next_action)


def _state_patch_writeback_step(root: Path, scene_id: str) -> dict[str, object]:
    """Expose the concrete state-machine handoff, never a prose repair step.

    ``state-writeback`` used to be a dashboard-only aggregate label.  When it
    became the first unfinished step, task-next treated that label as a formal
    state and fell through to a manual task whose natural-language command
    cannot run inside the Worker command bridge.  Map the aggregate status
    back to the executable approval, apply, or review state instead.
    """

    status = state_patch_writeback_status(root, scene_id)
    value = str(status.get("status") or "missing")
    passed = value in {"pass", "not_required"}
    if value == "needs_approval":
        key = "state-patch-approval"
        next_action = "record a digest-bound state_patch_confirmation for the current state patch"
    elif value == "pending_apply":
        key = "state-apply"
        next_action = "run state-apply with the recorded approval run id"
    elif value == "stale_source":
        key = "state-patch-json"
        next_action = "rerun state-evolve from the current structured writeback contract"
    elif passed:
        key = "state-writeback"
        next_action = ""
    else:
        key = "state-agent-task"
        next_action = "complete the state patch semantic review before state writeback"
    return {
        "key": key,
        "display_key": "state-writeback",
        "status": "pass" if passed else value,
        "path": str(status.get("patch") or ""),
        "message": str(status.get("message") or ""),
        "approval_run_id": str(status.get("approval_run_id") or ""),
        "next_action": next_action,
    }


def _continuity_ledger_step(root: Path, scene_id: str, *, review: bool) -> dict[str, object]:
    passed, message = continuity_ledger_task_status(root, scene_id, review=review)
    return {
        "key": "continuity-ledger-review" if review else "continuity-ledger-agent-task",
        "status": "pass" if passed else "blocked",
        "path": f"reviews/continuity/{scene_id}_ledger_review.json" if review else f"plot/ledger_deltas/{scene_id}.json",
        "message": message,
        "next_action": "" if passed else (
            "complete independent continuity ledger review with a different reviewer session"
            if review
            else "complete reader-question and promise/payoff delta with prose evidence"
        ),
    }


def _branch_selection_step(path: Path, *, dependency: Path | None = None) -> dict[str, object]:
    if path.is_file() and dependency is not None and dependency.is_file() and path.stat().st_mtime_ns < dependency.stat().st_mtime_ns:
        return {
            "key": "branch-selection",
            "status": "stale",
            "path": str(path),
            "message": "branch manifest was refreshed after this selection",
            "selected_branch": "",
            "next_action": "fill branch_selection.md with decision: selected and selected_branch",
        }
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


def _narrative_rhythm_step(root: Path, scene_path: Path) -> dict[str, object]:
    contract = narrative_rhythm_contract(root, scene_path)
    status = str(contract.get("status") or "")
    passed = status == "pass"
    return {
        "key": "scene-rhythm-contract",
        "status": "pass" if passed else status or "missing",
        "path": _rel(scene_path, root),
        "message": contract.get("message", ""),
        "next_action": "complete the CLI-issued scene-rhythm-contract task before composition" if not passed else "",
    }


def _composition_step(root: Path, scene_path: Path) -> dict[str, object]:
    scene_id = _scene_id(scene_path)
    path = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    if not path.is_file():
        return {
            "key": "composition-json",
            "status": "missing",
            "path": _rel(path, root),
            "message": "composition JSON is missing",
            "next_action": "run compose-scene --agent-tasks",
        }
    payload = _read_json(path)
    provenance = payload.get("formal_cli_provenance") if isinstance(payload.get("formal_cli_provenance"), dict) else {}
    expected = composition_input_digest(root, scene_path)
    recorded = str(provenance.get("input_contract_digest") or "")
    if not recorded or recorded != expected:
        return {
            "key": "composition-json",
            "status": "stale",
            "path": _rel(path, root),
            "message": "composition input contracts changed or were generated by an older CLI; rebuild after the current budget, reader, and rhythm contracts.",
            "next_action": "rerun compose-scene --agent-tasks from the CLI task package",
        }
    return {
        "key": "composition-json",
        "status": "pass",
        "path": _rel(path, root),
        "message": "composition matches the current formal input contracts",
        "next_action": "",
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
    status = str(gate.get("status") or "missing")
    review_again = {
        "missing",
        "task_incomplete",
        "schema_failed",
        "semantic_contract_failed",
        "stale_or_wrong_source",
        "creative_quality_review_stale",
        "word_budget_review_failed",
        "reader_experience_review_failed",
        "narrative_rhythm_review_failed",
        "canon_writeback_review_failed",
        "revision_integrity_review_failed",
        "review_session_independence_failed",
    }
    if status == "human_decision_required":
        if _candidate_revision_direction(root, scene_id, gate):
            return {
                "key": "candidate-revision",
                "status": "needs_revision",
                "path": str(gate.get("review") or ""),
                "message": "a matching formal revision direction is recorded; revise prose without modifying canon or character assets",
                "next_action": "run revise-scene against the exact candidate and review, then independently review the new revision candidate",
            }
        return {
            "key": "candidate-human-decision",
            "status": "human_required",
            "path": str(gate.get("review") or ""),
            "message": gate.get("message", "candidate review requires a formal decision"),
            "next_action": "choose whether prose should align with the existing formal asset or hold the candidate for a separate asset revision",
        }
    key = "candidate-review" if status in review_again else "candidate-revision"
    if status == "pass":
        key = "candidate-review"
    return {
        "key": key,
        "status": "pass" if status == "pass" else status,
        "path": str(gate.get("review") or ""),
        "message": gate.get("message", ""),
        "next_action": (
            ""
            if status == "pass"
            else "run agent-review-scene on the exact candidate and complete its sidecar"
            if key == "candidate-review"
            else "run revise-scene against the exact candidate and review, then independently review the new revision candidate"
        ),
    }


def _candidate_revision_direction(root: Path, scene_id: str, gate: dict[str, object]) -> bool:
    """Require a decision tied to this exact candidate, never a generic old note."""

    expected_sha = str(gate.get("candidate_sha256") or "").strip().lower()
    if not expected_sha:
        return False
    index = root / "workflow" / "human_choices" / "index.jsonl"
    if not index.is_file():
        return False
    for line in reversed(index.read_text(encoding="utf-8", errors="ignore").splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or str(record.get("decision_type") or "") != "cross_asset_alignment":
            continue
        target = record.get("target") if isinstance(record.get("target"), dict) else {}
        if str(target.get("scene_id") or target.get("target_id") or "") != scene_id:
            continue
        if str(target.get("candidate_sha256") or "").strip().lower() != expected_sha:
            continue
        return str(record.get("selected") or "") == "align_prose_to_formal_asset"
    return False


def _static_review_step(root: Path, scene_id: str) -> dict[str, object]:
    path = root / "reviews" / f"{scene_id}-review.md"
    conclusion = _static_review_conclusion(path)
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    fresh = _static_review_matches_draft(path, draft)
    key = "static-review" if not conclusion or not fresh else "static-revision"
    if conclusion == "pass" and fresh:
        key = "static-review"
    return {
        "key": key,
        "status": "pass" if conclusion == "pass" and fresh else "stale" if conclusion and not fresh else conclusion or "missing",
        "path": _rel(path, root),
        "message": f"conclusion={conclusion or 'missing'}; exact_draft={fresh}",
        "next_action": "" if conclusion == "pass" and fresh else (
            "run review-scene on the exact promoted draft" if not conclusion or not fresh else "revise the promoted draft against static review findings, then run exact-candidate AgentReview and promotion again"
        ),
    }


def _promotion_step(root: Path, scene_id: str, candidate: Path | None) -> dict[str, object]:
    manifest = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    payload = _read_json(manifest)
    recorded = str(payload.get("candidate") or "").replace("\\", "/")
    expected = _rel(candidate, root) if candidate else ""
    current = bool(candidate and manifest.is_file() and recorded == expected)
    if current and payload.get("candidate_sha256"):
        current = str(payload.get("candidate_sha256") or "").lower() == hashlib.sha256(candidate.read_bytes()).hexdigest()
    return {
        "key": "promotion-manifest",
        "status": "pass" if current else "missing" if not manifest.exists() else "stale",
        "path": _rel(manifest, root),
        "message": f"candidate={recorded or 'missing'}; current_candidate={expected or 'missing'}",
        "next_action": "" if current else "run promote-candidate for the exact independently reviewed candidate",
    }


def _promoted_draft_step(root: Path, scene_id: str, candidate: Path | None) -> dict[str, object]:
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    manifest = _read_json(root / "drafts" / "promotions" / f"{scene_id}_promotion.json")
    expected_hash = str(manifest.get("draft_sha256") or "").lower()
    actual_hash = hashlib.sha256(draft.read_bytes()).hexdigest() if draft.is_file() else ""
    current = bool(candidate and draft.is_file() and expected_hash and expected_hash == actual_hash)
    return {
        "key": "promoted-draft",
        "status": "pass" if current else "missing" if not draft.exists() else "stale",
        "path": _rel(draft, root),
        "message": "promoted draft matches current promotion manifest" if current else "promoted draft is missing or stale",
        "next_action": "" if current else "promote the exact reviewed candidate into drafts/scenes",
    }


def _current_scene_candidate(root: Path, scene_id: str) -> Path | None:
    promoted = _promotion_candidate_path(root, scene_id)
    latest = _latest_scene_candidate(root, scene_id)
    manifest = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    if latest and (not manifest.exists() or latest.stat().st_mtime_ns > manifest.stat().st_mtime_ns):
        return latest
    return promoted or latest


def current_scene_candidate(root: Path, scene_id: str) -> Path | None:
    """Return the exact candidate that the formal scene route currently governs."""

    return _current_scene_candidate(root.resolve(), scene_id)


def _canon_writeback_step(root: Path, scene_id: str) -> dict[str, object]:
    status = canon_writeback_status(root, scene_id)
    state = str(status.get("status") or "")
    passed = state in {"pass", "not_required"}
    key = "canon-agent-task" if state in {"task_incomplete", "semantic_incomplete"} else "canon-patch-json"
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
        (root / "drafts" / "revisions", f"{scene_id}_revision*.md"),
    ):
        if directory.exists():
            candidates.extend(
                path
                for path in directory.glob(pattern)
                if not path.name.endswith(".agent_tasks.md")
                and not path.name.endswith(".prompt.md")
                and not path.name.endswith("_report.md")
            )
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def _static_review_matches_draft(review: Path, draft: Path) -> bool:
    if not review.is_file() or not draft.is_file():
        return False
    match = re.search(r"(?m)^-\s*审查对象 SHA-256：`([0-9a-fA-F]{64})`\s*$", _read(review))
    return bool(match and match.group(1).lower() == hashlib.sha256(draft.read_bytes()).hexdigest())


def _scene_id(path: Path) -> str:
    text = _read(path)
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    if match:
        scene_id = match.group(1).strip().strip("\"'")
        if scene_id:
            return scene_id
    return path.stem
