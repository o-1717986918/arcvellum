"""Task blueprints for independent style review and its revision loop."""

from __future__ import annotations

from pathlib import Path

from ...literary.style.review import (
    inspect_style_semantic_review,
    style_eval_generation_digest_errors,
    style_semantic_review_errors,
)
from ...style_prompt import style_prompt_quality_report
from .support import declared_repair_targets_changed, file_sha256


def style_review_blueprints(
    root: Path,
    profile_id: str,
    profile_dir: str,
) -> dict[str, dict[str, object]]:
    paths = _review_paths(profile_dir)
    sources = _safe_sources(root, paths)
    return {
        "style-review-task-file": _prepare_blueprint(profile_id, profile_dir, paths, sources),
        "style-review-agent-task": _agent_blueprint(paths, sources),
        "style-review-revision": _revision_blueprint(paths, sources),
    }


def _review_paths(profile_dir: str) -> dict[str, str]:
    evaluation = f"{profile_dir}/evaluation_results/formal"
    return {
        "session": f"{profile_dir}/style_session.json",
        "profile": f"{profile_dir}/style-profile.md",
        "metrics": f"{profile_dir}/style_metrics.json",
        "prompt": f"{profile_dir}/style_prompt.md",
        "prompt_manifest": f"{profile_dir}/style_prompt.agent.json",
        "prompt_completion": f"{profile_dir}/style_prompt.agent_completion.json",
        "candidate": f"{evaluation}/platform_agent_candidate.md",
        "generation_manifest": f"{evaluation}/platform_agent_candidate.prompt.json",
        "evaluation_completion": f"{evaluation}/platform_agent_candidate.agent_completion.json",
        "score": f"{evaluation}/style_eval_current.json",
        "score_report": f"{evaluation}/style_eval_current.md",
        "review": f"{evaluation}/style_semantic_review.json",
        "review_report": f"{evaluation}/style_semantic_review.md",
        "review_task": f"{evaluation}/style_semantic_review.agent_tasks.md",
        "review_completion": f"{evaluation}/style_semantic_review.agent_completion.json",
    }


def _safe_sources(root: Path, paths: dict[str, str]) -> list[str]:
    names = [
        "profile",
        "metrics",
        "prompt",
        "prompt_manifest",
        "candidate",
        "generation_manifest",
        "score",
        "score_report",
        "review",
        "review_report",
        "review_task",
    ]
    sources = [paths[name] for name in names]
    if (root / paths["session"]).is_file():
        sources.insert(0, paths["session"])
    return sources


def _prepare_blueprint(
    profile_id: str,
    profile_dir: str,
    paths: dict[str, str],
    sources: list[str],
) -> dict[str, object]:
    review_outputs = [paths["review"], paths["review_report"], paths["review_task"]]
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.style-engineering.review.prepare.v1",
        "command": (
            f'python -m literary_engineering_studio_engine prepare-style-review "<project>" '
            f'--profile-dir "{profile_dir}" --target-id "{profile_id}"'
        ),
        "source_paths": [item for item in sources if item not in review_outputs],
        "expected_outputs": review_outputs,
        "hard_constraints": [
            "Prepare a digest-bound independent semantic review task after deterministic evaluation passes.",
            "Do not expose the raw holdout text to the semantic reviewer.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "review skeleton binds current session, source set, profile, prompt, candidate, and score digests",
            "independent review sidecar exists",
        ],
        "next_allowed_states": ["style-review-agent-task"],
    }


def _agent_blueprint(paths: dict[str, str], sources: list[str]) -> dict[str, object]:
    return {
        "task_type": "platform-agent-review",
        "prompt_asset_id": "route.style-engineering.review.execute.v1",
        "command": "",
        "source_paths": sources,
        "agent_source_paths": sources,
        "expected_outputs": [paths["review"], paths["review_report"], paths["review_completion"]],
        "hard_constraints": [
            "Review the exact digest bundle without reading raw holdout prose.",
            "Reviewer session must differ from both prompt and evaluation writer sessions.",
            "A required change forces verdict=revise or block; pass_with_notes is forbidden.",
            "Return concise findings and evidence, never hidden chain-of-thought.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "review JSON and Markdown satisfy the formal contract",
            "machine-owned evidence digests match current upstream artifacts",
            "review sidecar completion exists",
        ],
        "next_allowed_states": ["style-review-readiness", "style-review-revision"],
    }


def _revision_blueprint(paths: dict[str, str], sources: list[str]) -> dict[str, object]:
    repair_targets = [
        paths["prompt"],
        paths["prompt_manifest"],
        paths["candidate"],
        paths["generation_manifest"],
    ]
    return {
        "task_type": "platform-agent-revision",
        "prompt_asset_id": "route.style-engineering.review.fix.v1",
        "command": "",
        "source_paths": sources,
        "agent_source_paths": sources,
        "expected_outputs": [
            paths["prompt"],
            paths["prompt_manifest"],
            paths["prompt_completion"],
            paths["candidate"],
            paths["generation_manifest"],
            paths["evaluation_completion"],
        ],
        "repair_targets": repair_targets,
        "hard_constraints": [
            "Repair every required semantic-review change in the prompt and evaluation candidate.",
            "Do not edit the deterministic score or independent review files.",
            "Invalidate generation/score evidence so the route must evaluate and review the revision afresh.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "at least one declared prompt or candidate repair target changed",
            "previous generation or score evidence is stale",
            "fresh deterministic evaluation and independent review are required",
        ],
        "next_allowed_states": ["style-eval-agent-task", "style-eval-score-file"],
    }


def validate_style_review_task(
    root: Path,
    task: dict[str, object],
    profile_dir: Path,
) -> tuple[list[str], list[str]]:
    state = str(task.get("current_state") or "")
    if not state.startswith("style-review-"):
        return [], []
    target_id = str(task.get("profile_id") or task.get("target_id") or "")
    errors: list[str] = []
    notes: list[str] = []
    if state == "style-review-task-file":
        review = inspect_style_semantic_review(root, profile_dir, target_id=target_id)
        if review.stage == "prepare":
            errors.extend([review.message, *review.errors])
        else:
            notes.append("independent style review task prepared for the exact evidence bundle")
    elif state == "style-review-agent-task":
        errors.extend(
            style_semantic_review_errors(
                root,
                profile_dir,
                target_id=target_id,
                require_pass=False,
            )
        )
        if not errors:
            notes.append("independent style semantic review recorded")
    elif state == "style-review-revision":
        errors.extend(
            declared_repair_targets_changed(
                root,
                task,
                "style semantic-review revision",
            )
        )
        errors.extend(_prompt_quality_errors(profile_dir))
        if not _evaluation_is_stale(root, profile_dir):
            errors.append("style semantic-review revision must invalidate generation or score evidence")
        if not errors:
            notes.append(
                "style review repair changed upstream evidence; fresh evaluation and review are required"
            )
    elif state == "style-review-readiness":
        errors.extend(
            style_semantic_review_errors(
                root,
                profile_dir,
                target_id=target_id,
                require_pass=True,
            )
        )
        if not errors:
            notes.append("independent style semantic review passes")
    return errors, notes


def _prompt_quality_errors(profile_dir: Path) -> list[str]:
    prompt = profile_dir / "style_prompt.md"
    if not prompt.is_file():
        return ["style semantic-review revision removed style_prompt.md"]
    report = style_prompt_quality_report(
        prompt.read_text(encoding="utf-8", errors="ignore")
    )
    errors: list[str] = []
    if not report.get("length_ok"):
        errors.append("revised style prompt fails the 500-2500 Chinese-content character gate")
    if not report.get("structure_ok"):
        errors.append("revised style prompt is missing required executable prompt blocks")
    return errors


def _evaluation_is_stale(root: Path, profile_dir: Path) -> bool:
    if style_eval_generation_digest_errors(root, profile_dir):
        return True
    candidate = profile_dir / "evaluation_results/formal/platform_agent_candidate.md"
    score = profile_dir / "evaluation_results/formal/style_eval_current.json"
    if not candidate.is_file() or not score.is_file():
        return True
    import json

    try:
        payload = json.loads(score.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    return str(payload.get("candidate_sha256") or "") != file_sha256(candidate)
