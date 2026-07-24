"""Derived state for the style-engineering route."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..agent_tasks import agent_task_completion_status
from ..style_prompt import style_prompt_quality_report
from .state_common import _file_step, _read, _read_json, _rel, _slug_profile_id


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
        if profile.parent == style_root or "mounted" in parts:
            continue
        states.append(_style_engineering_state(root, profile.parent))
    return states


def _style_engineering_state(root: Path, profile_dir: Path) -> dict[str, object]:
    profile_id = _rel(profile_dir, root)
    task_path = profile_dir / "style_prompt.agent_tasks.md"
    prompt_path = profile_dir / "style_prompt.md"
    agent_json = profile_dir / "style_prompt.agent.json"
    eval_dir = profile_dir / "evaluation_results" / "formal"
    eval_reference = _style_eval_reference(profile_dir)
    eval_candidate = eval_dir / "platform_agent_candidate.md"
    eval_manifest = eval_dir / "platform_agent_candidate.prompt.json"
    eval_task = eval_candidate.with_suffix(".agent_tasks.md")
    eval_current = eval_dir / "style_eval_current.json"
    steps = [
        _style_profile_step(root, profile_dir),
        _file_step("style-prompt-task-file", task_path, "run style-prompt on this profile to create platform-agent prompt sidecar"),
        _style_prompt_agent_step(root, task_path, prompt_path, agent_json),
        _style_prompt_quality_step(root, prompt_path),
        _style_eval_setup_step(root, profile_dir, eval_reference),
        _file_step("style-eval-task-file", eval_task, "prepare the formal style evaluation task with a concrete corpus reference and project direction input"),
        _style_eval_agent_step(root, eval_task, eval_candidate, eval_manifest),
        _style_eval_score_step(root, eval_candidate, eval_current),
        _style_eval_readiness_step(root, profile_dir, eval_candidate, eval_current),
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


def _style_eval_setup_step(root: Path, profile_dir: Path, reference: Path | None) -> dict[str, object]:
    if reference is not None:
        return {
            "key": "style-eval-setup",
            "status": "pass",
            "path": _rel(reference, root),
            "message": "concrete corpus reference available for formal evaluation",
            "next_action": "",
        }
    return {
        "key": "style-eval-setup",
        "status": "missing",
        "path": _rel(profile_dir / "corpus", root),
        "message": "formal style evaluation needs at least one authorized UTF-8 corpus text",
        "next_action": "import an authorized or public-domain corpus text into this profile before evaluation",
    }


def _style_eval_agent_step(root: Path, task_path: Path, candidate: Path, manifest: Path) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    missing = [_rel(path, root) for path in (candidate, manifest) if not path.is_file()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": "style-eval-agent-task",
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "message": message,
        "next_action": "" if complete else "complete the formal style evaluation candidate, prompt manifest, and sidecar marker",
    }


def _style_eval_score_step(root: Path, candidate: Path, current: Path) -> dict[str, object]:
    payload = _read_json(current)
    candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else ""
    scored_sha = str(payload.get("candidate_sha256") or "")
    current_score = current.is_file() and candidate_sha and scored_sha == candidate_sha
    return {
        "key": "style-eval-score-file",
        "status": "pass" if current_score else "missing" if not current.is_file() else "stale",
        "path": _rel(current, root),
        "message": "deterministic style score matches current candidate" if current_score else "style score is missing or stale for the current evaluation candidate",
        "next_action": "" if current_score else "run deterministic style-eval for the current formal candidate and corpus reference",
    }


def _style_eval_readiness_step(root: Path, profile_dir: Path, candidate: Path, current: Path) -> dict[str, object]:
    payload = _read_json(current)
    candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else ""
    risk = str(payload.get("risk_level") or "")
    try:
        score = float(payload.get("overall_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    accepted = bool(candidate_sha) and str(payload.get("candidate_sha256") or "") == candidate_sha and risk not in {"high_copy_risk", "low_similarity"} and score >= 45
    return {
        "key": "style-eval-readiness" if accepted else "style-eval-revision",
        "status": "pass" if accepted else "blocked",
        "path": _rel(current, root),
        "message": f"overall_score={score}; risk_level={risk or 'missing'}; current_candidate={bool(candidate_sha)}",
        "next_action": "" if accepted else "revise the style prompt and evaluation candidate against deterministic score evidence, then rerun style-eval",
    }


def _style_eval_reference(profile_dir: Path) -> Path | None:
    candidates = sorted((profile_dir / "corpus").glob("*.txt"))
    return next((path for path in candidates if path.is_file() and path.stat().st_size > 0), None)


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
