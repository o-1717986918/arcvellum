"""Shared scene readiness gates for chapter, longform, and export routes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_schema import validate_payload
from .anti_ai_style import style_lint_gate, style_lint_gate_message
from .context_broker import context_trace_status
from .flow_gates import branch_selection_status
from .new_character_register import new_character_register_issues
from .reader_experience import reader_experience_adherence_for_body
from .word_budget import word_budget_adherence_for_body


def scene_flow_gate_issues(root: Path, scene_id: str) -> tuple[str, ...]:
    """Return blocking formal-scene-flow issues for a scene."""

    issues: list[str] = []
    context = root / "memory" / "context_packets" / f"{scene_id}.md"
    roleplay = root / "branches" / scene_id / "roleplay_simulation.md"
    branch_manifest = root / "branches" / scene_id / "branch_manifest.json"
    selection = root / "branches" / scene_id / "branch_selection.md"
    composition_json = root / "drafts" / "compositions" / f"{scene_id}_composition.json"

    if not context.exists():
        issues.append(f"missing context packet: memory/context_packets/{scene_id}.md")
    trace = context_trace_status(root, scene_id, context)
    if not trace.passed:
        issues.append(trace.message)

    roleplay_text = _read_text(roleplay)
    if not roleplay.exists():
        issues.append(f"missing roleplay simulation: branches/{scene_id}/roleplay_simulation.md")
    else:
        if "读取回执" not in roleplay_text:
            issues.append("roleplay simulation missing platform-agent reading receipt")
        if "[AGENT_TASK:" in roleplay_text:
            issues.append("roleplay simulation still contains unresolved AGENT_TASK directives")

    branch_payload = _read_json(branch_manifest)
    branches = branch_payload.get("branches")
    if not (branch_manifest.exists() and isinstance(branches, list) and branches):
        issues.append(f"missing valid branch manifest: branches/{scene_id}/branch_manifest.json")

    selection_gate = branch_selection_status(selection)
    if selection_gate["status"] != "selected":
        issues.append(f"formal branch selection missing or incomplete: {selection_gate['message']}")

    composition_payload = _read_json(composition_json)
    flow_gate = composition_payload.get("flow_gate", {}) if isinstance(composition_payload.get("flow_gate"), dict) else {}
    composition_ready = (
        composition_json.exists()
        and composition_payload.get("selection_source") == "selection"
        and flow_gate.get("ready_for_generation") is True
    )
    if not composition_ready:
        issues.append(f"composition is not ready for generation: drafts/compositions/{scene_id}_composition.json")

    return tuple(issues)


def agent_review_gate_state(root: Path, json_path: Path, reviewed_path: Path) -> dict[str, Any]:
    """Analyze whether an AgentReview JSON cleanly reviews the current draft."""

    rel_reviewed = _rel(reviewed_path, root)
    state: dict[str, Any] = {
        "conclusion": "",
        "schema_status": "",
        "validation_path": "",
        "source_match": False,
        "unresolved_notes": [],
        "style_adherence_status": "",
        "word_budget_adherence_status": "",
        "word_budget_narrative_load_satisfied": False,
        "reader_experience_adherence_status": "",
        "reader_promise_satisfied": False,
        "new_character_register_issues": [],
        "schema_errors": [],
    }
    if not json_path.exists():
        return state
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state["schema_status"] = "failed"
        state["schema_errors"] = [{"path": "review", "message": "invalid json", "actual": ""}]
        return state
    if not isinstance(payload, dict):
        state["schema_status"] = "failed"
        state["schema_errors"] = [{"path": "review", "message": "json root is not object", "actual": type(payload).__name__}]
        return state

    errors, _warnings = validate_payload(payload, "scene_review.v1")
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    style = payload.get("style_adherence") if isinstance(payload.get("style_adherence"), dict) else {}
    style_status = str(style.get("status") or "").strip().lower() if isinstance(style, dict) else ""
    budget = payload.get("word_budget_adherence") if isinstance(payload.get("word_budget_adherence"), dict) else {}
    budget_status = str(budget.get("status") or "").strip().lower() if isinstance(budget, dict) else ""
    reader = payload.get("reader_experience_adherence") if isinstance(payload.get("reader_experience_adherence"), dict) else {}
    reader_status = str(reader.get("status") or "").strip().lower() if isinstance(reader, dict) else ""
    new_character_issues = new_character_register_issues(payload, root, mode="review")
    validation_status = "pass" if not errors else "failed"
    validation_rel = str(payload.get("schema_validation") or "").strip()
    if validation_rel:
        validation_path = root / validation_rel
        if validation_path.exists():
            try:
                validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
                recorded_status = str(validation_payload.get("status") or "").strip()
                if recorded_status:
                    validation_status = recorded_status
            except json.JSONDecodeError:
                validation_status = "failed"

    state.update(
        {
            "conclusion": conclusion,
            "schema_status": validation_status,
            "validation_path": validation_rel,
            "source_match": _review_mentions_path(payload, rel_reviewed, reviewed_path),
            "unresolved_notes": _unresolved_review_notes(payload),
            "style_adherence_status": style_status,
            "word_budget_adherence_status": budget_status,
            "word_budget_narrative_load_satisfied": budget.get("narrative_load_satisfied") is not False if isinstance(budget, dict) and budget_status else False,
            "reader_experience_adherence_status": reader_status,
            "reader_promise_satisfied": reader.get("reader_promise_satisfied") is not False if isinstance(reader, dict) and reader_status else False,
            "new_character_register_issues": new_character_issues,
            "schema_errors": errors,
        }
    )
    return state


def scene_readiness_status(
    root: Path,
    *,
    draft_path: Path,
    review_path: Path,
    agent_review_json_path: Path,
    body: str,
    static_review_conclusion: str,
    flow_gate_issues: tuple[str, ...],
    agent_review_state: dict[str, Any],
) -> tuple[str, tuple[str, ...]]:
    """Return a normalized scene status and the reasons behind it."""

    issues: list[str] = []
    conclusion = static_review_conclusion.strip().lower()
    agent_conclusion = str(agent_review_state.get("conclusion") or "").strip().lower()
    schema_status = str(agent_review_state.get("schema_status") or "").strip().lower()
    style_status = str(agent_review_state.get("style_adherence_status") or "").strip().lower()
    agent_budget_status = str(agent_review_state.get("word_budget_adherence_status") or "").strip().lower()
    agent_budget_load = bool(agent_review_state.get("word_budget_narrative_load_satisfied"))
    agent_reader_status = str(agent_review_state.get("reader_experience_adherence_status") or "").strip().lower()
    agent_reader_promise = bool(agent_review_state.get("reader_promise_satisfied"))
    unresolved = [str(item) for item in agent_review_state.get("unresolved_notes", [])]
    new_character_issues = [str(item) for item in agent_review_state.get("new_character_register_issues", [])]
    source_match = bool(agent_review_state.get("source_match"))
    lint_gate = style_lint_gate(body)
    scene_id = _scene_id_from_draft(draft_path)
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    word_budget = word_budget_adherence_for_body(root, scene_path, body)
    reader_experience = reader_experience_adherence_for_body(root, scene_path, body)
    reader_required = str(reader_experience.get("status") or "").strip().lower() != "not_required"

    if not draft_path.exists() or not body:
        return "needs_draft", ("missing cleaned draft body",)

    if flow_gate_issues:
        return "needs_flow_gates", flow_gate_issues

    if not review_path.exists() or not conclusion:
        return "needs_review", ("missing static scene review",)
    if conclusion == "pass_with_notes":
        return "needs_revision", ("static review is pass_with_notes",)
    if conclusion in {"revise_required", "reject"}:
        return "needs_revision", (f"static review is {conclusion}",)
    if conclusion != "pass":
        return "blocked", (f"static review conclusion is {conclusion or 'missing'}",)
    if lint_gate.get("status") == "blocking":
        return "needs_revision", (f"Style Lint Gate failed: {style_lint_gate_message(lint_gate)}",)
    if str(word_budget.get("status") or "").strip().lower() not in {"pass", "not_required"}:
        return "needs_revision", (f"word budget gate failed: {word_budget.get('message')}",)
    if str(reader_experience.get("status") or "").strip().lower() not in {"pass", "not_required"}:
        return "needs_revision", (f"reader experience gate failed: {reader_experience.get('message')}",)

    if not agent_review_json_path.exists() or not agent_conclusion or not schema_status:
        return "needs_agent_review", ("missing platform Agent scene_review.v1 JSON",)
    if schema_status != "pass":
        return "blocked", (f"AgentReview schema status is {schema_status}",)
    if not source_match:
        return "needs_agent_review", ("AgentReview does not cite current draft path",)
    if agent_conclusion == "pass_with_notes":
        issues.append("AgentReview conclusion is pass_with_notes")
    elif agent_conclusion in {"revise_required", "reject"}:
        issues.append(f"AgentReview conclusion is {agent_conclusion}")
    elif agent_conclusion != "pass":
        return "blocked", (f"AgentReview conclusion is {agent_conclusion or 'missing'}",)
    issues.extend(unresolved)

    style_required = _mounted_style_exists(root)
    if style_required and style_status != "pass":
        issues.append(f"mounted style_adherence.status is {style_status or 'missing'}")
    if not style_required and style_status in {"pass_with_notes", "revise_required", "reject"}:
        issues.append(f"style_adherence.status is {style_status}")
    if agent_budget_status not in {"pass", "not_required"}:
        issues.append(f"word_budget_adherence.status is {agent_budget_status or 'missing'}")
    elif not agent_budget_load:
        issues.append("word_budget_adherence.narrative_load_satisfied is false or missing")
    if reader_required:
        if agent_reader_status not in {"pass", "not_required"}:
            issues.append(f"reader_experience_adherence.status is {agent_reader_status or 'missing'}")
        elif not agent_reader_promise:
            issues.append("reader_experience_adherence.reader_promise_satisfied is false or missing")
    issues.extend(f"new_character_register: {item}" for item in new_character_issues)

    if issues:
        return "needs_revision", tuple(issues)
    return "ready", ()


def _review_mentions_path(payload: dict[str, Any], rel_path: str, absolute_path: Path) -> bool:
    expected = _normalize_review_path(rel_path)
    absolute = _normalize_review_path(str(absolute_path.resolve()))
    direct_values = [
        payload.get("candidate"),
        payload.get("reviewed_candidate"),
        payload.get("draft"),
        payload.get("source_candidate"),
    ]
    source_paths = payload.get("source_paths")
    if isinstance(source_paths, list):
        direct_values.extend(source_paths)
    for value in direct_values:
        normalized = _normalize_review_path(str(value or ""))
        if normalized in {expected, absolute}:
            return True
    return False


def _unresolved_review_notes(payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    if conclusion in {"pass_with_notes", "revise_required", "reject"}:
        notes.append(f"conclusion={conclusion}")
    for key in ("blocking_issues", "warnings", "revision_actions", "style_notes"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            notes.append(key)
    style = payload.get("style_adherence")
    if isinstance(style, dict):
        style_status = str(style.get("status") or "").strip().lower()
        if style_status in {"pass_with_notes", "revise_required", "reject"}:
            notes.append(f"style_adherence.status={style_status}")
        for key in ("deviations", "revision_actions"):
            value = style.get(key)
            if isinstance(value, list) and value:
                notes.append(f"style_adherence.{key}")
    budget = payload.get("word_budget_adherence")
    if isinstance(budget, dict):
        budget_status = str(budget.get("status") or "").strip().lower()
        if budget_status not in {"", "pass", "not_required"}:
            notes.append(f"word_budget_adherence.status={budget_status}")
        if budget_status in {"pass", "not_required"} and budget.get("narrative_load_satisfied") is False:
            notes.append("word_budget_adherence.narrative_load_satisfied=false")
    reader = payload.get("reader_experience_adherence")
    if isinstance(reader, dict):
        reader_status = str(reader.get("status") or "").strip().lower()
        if reader_status not in {"", "pass", "not_required"}:
            notes.append(f"reader_experience_adherence.status={reader_status}")
        if reader_status in {"pass", "not_required"} and reader.get("reader_promise_satisfied") is False:
            notes.append("reader_experience_adherence.reader_promise_satisfied=false")
    return notes


def _mounted_style_exists(root: Path) -> bool:
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        return True
    mounted = root / "style" / "mounted"
    return mounted.exists() and any(mounted.iterdir())


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize_review_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("`").lstrip("./")


def _scene_id_from_draft(path: Path) -> str:
    name = path.stem
    if name.endswith("_revision"):
        return name[: -len("_revision")]
    return name


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
