"""Formal task blueprint and Gate logic for the style-engineering route.

The route produces a mountable style prompt only after a profile, a concrete
platform-agent task, deterministic evaluation, and a fresh accepted score all
agree.  Keeping those rules here prevents the task registry from becoming the
implementation home for every route.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...style_prompt import style_prompt_quality_report
from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path,
    now,
    relative_path,
    resolve_project_path,
    task_id,
)


def build_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    """Build one stable, CLI-owned style-engineering task contract."""

    profile_id = str(state.get("profile_id") or state.get("target_id") or "")
    profile_dir = str(state.get("profile_dir") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = blueprint_for_state(root, profile_id, profile_dir, current_state, next_action)
    identifier = task_id(route, profile_id or "style-profile", current_state)
    expected_outputs = _unique([normalize_relative_path(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([normalize_relative_path(item) for item in blueprint["source_paths"]])
    payload: dict[str, object] = {
        "schema": TASK_SCHEMA,
        "task_id": identifier,
        "status": "issued",
        "created_at": now(),
        "route": route,
        "scene_id": profile_id,
        "target_id": profile_id,
        "profile_id": profile_id,
        "profile_dir": profile_dir,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/workflows.md",
                "docs/modules/style-compiler.md",
                "docs/implementation/phase26-style-prompt-effectiveness.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {identifier} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {identifier}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not mount a Style Skill from an under-specified prompt.",
            "Do not use --allow-unreviewed for formal Skill-host work.",
            "Do not treat style metrics or a dry profile report as an LLM-facing prompt.",
            "Do not pursue exact author imitation unless the corpus is public-domain, authorized, or user-owned.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(resolve_project_path(root, relative))
            for relative in repair_targets
            if resolve_project_path(root, relative).is_file()
        }
    return payload


def blueprint_for_state(root: Path, profile_id: str, profile_dir: str, current_state: str, next_action: str) -> dict[str, object]:
    """Return the exact task blueprint for a style profile state."""

    profile = f"{profile_dir}/style-profile.md"
    metrics = f"{profile_dir}/style_metrics.json"
    corpus_manifest = f"{profile_dir}/corpus_manifest.yaml"
    task = f"{profile_dir}/style_prompt.agent_tasks.md"
    prompt = f"{profile_dir}/style_prompt.md"
    agent_json = f"{profile_dir}/style_prompt.agent.json"
    completion = f"{profile_dir}/style_prompt.agent_completion.json"
    eval_dir = f"{profile_dir}/evaluation_results/formal"
    eval_candidate = f"{eval_dir}/platform_agent_candidate.md"
    eval_manifest = f"{eval_dir}/platform_agent_candidate.prompt.json"
    eval_task = f"{eval_dir}/platform_agent_candidate.agent_tasks.md"
    eval_completion = f"{eval_dir}/platform_agent_candidate.agent_completion.json"
    eval_json = f"{eval_dir}/style_eval_current.json"
    eval_report = f"{eval_dir}/style_eval_current.md"
    profile_path = resolve_project_path(root, profile_dir)
    reference_path = next(
        (path for path in sorted((profile_path / "corpus").glob("*.txt")) if path.is_file() and path.stat().st_size > 0),
        None,
    )
    reference = relative_path(reference_path, root) if reference_path is not None else ""
    table: dict[str, dict[str, object]] = {
        "style-profile": {
            "task_type": "deterministic-cli-or-repair",
            "prompt_asset_id": "route.style-engineering.profile.v1",
            "command": "python -m literary_engineering_studio_engine style-profile <corpus> --out-dir <profile-dir> --name <name>",
            "source_paths": [profile_dir],
            "expected_outputs": [profile, metrics],
            "hard_constraints": ["Compile or repair style-profile.md and style_metrics.json before prompt generation."],
            "style_constraints": [],
            "validation_gates": ["style profile exists", "style metrics exists"],
            "next_allowed_states": ["style-prompt-task-file"],
        },
        "style-prompt-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.prompt.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine style-prompt <project>/{profile_dir}",
            "source_paths": [profile, metrics, corpus_manifest],
            "expected_outputs": [task],
            "hard_constraints": [
                "Run style-prompt to create a platform-agent style prompt task sidecar.",
                "The command prepares the task; the platform agent still writes style_prompt.md and style_prompt.agent.json.",
            ],
            "style_constraints": [],
            "validation_gates": ["style_prompt.agent_tasks.md exists"],
            "next_allowed_states": ["style-prompt-agent-task"],
        },
        "style-prompt-agent-task": {
            "task_type": "platform-agent-style-prompt",
            "prompt_asset_id": "route.style-engineering.prompt.execute.v1",
            "command": "",
            "source_paths": [profile, metrics, corpus_manifest, task],
            "expected_outputs": [prompt, agent_json, completion],
            "hard_constraints": [
                "Read style_prompt.agent_tasks.md and write a detailed executable LLM-facing style prompt.",
                "style_prompt.md must be 500-2500 Chinese-content detail characters, counting Han characters and Chinese punctuation after Markdown scaffolding is stripped.",
                "style_prompt.md must include all required blocks: identity/boundary, mechanism, narrative distance, rhythm, punctuation, imagery, psychology/behavior, dialogue, AI-trace controls, forbidden tendencies, and self-check.",
            ],
            "style_constraints": [
                "Do not authorize mechanical contrast frames or dash variants as style.",
                "Public-domain or authorized corpora may support closer imitation; otherwise extract high-level craft only.",
            ],
            "validation_gates": ["style prompt sidecar completion marker exists", "style_prompt.md exists", "style_prompt.agent.json exists", "style prompt quality passes"],
            "next_allowed_states": ["style-prompt-quality", "style-eval-setup"],
        },
        "style-prompt-quality": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.style-engineering.prompt-quality.v1",
            "command": "",
            "source_paths": [profile, metrics, prompt, agent_json],
            "expected_outputs": [prompt, agent_json],
            "hard_constraints": [
                "Revise style_prompt.md until style_prompt_quality_report passes length and required-block checks.",
                "A vague prompt that only says the style is beautiful, restrained, literary, or advanced is not mountable.",
            ],
            "style_constraints": [],
            "validation_gates": ["style prompt quality passes"],
            "next_allowed_states": ["style-eval-setup"],
        },
        "style-eval-setup": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.style-engineering.eval.setup.v1",
            "command": "Import at least one authorized or public-domain UTF-8 corpus text into this style profile.",
            "source_paths": [profile, metrics, corpus_manifest],
            "expected_outputs": [],
            "hard_constraints": [
                "Do not fabricate a source corpus or claim authorization that the user did not provide.",
                "The formal evaluation reference must be a real non-empty UTF-8 text in the profile corpus.",
            ],
            "style_constraints": [],
            "validation_gates": ["authorized corpus reference exists"],
            "next_allowed_states": ["style-eval-task-file"],
        },
        "style-eval-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.eval.prepare.v1",
            "command": (
                f'python -m literary_engineering_studio_engine style-prompt-eval "<project>/{profile_dir}" '
                f'--reference "<project>/{reference}" --input "<project>/project.yaml" --mode blind-review '
                f'--out-dir "<project>/{eval_dir}"'
            ),
            "source_paths": [profile, metrics, prompt, agent_json, reference, "project.yaml"],
            "expected_outputs": [eval_task],
            "hard_constraints": [
                "Prepare one concrete formal evaluation sidecar; no path placeholders may remain.",
                "Use the project direction as neutral content input and the corpus text only as evaluation reference.",
            ],
            "style_constraints": [],
            "validation_gates": ["formal style evaluation sidecar exists"],
            "next_allowed_states": ["style-eval-agent-task"],
        },
        "style-eval-agent-task": {
            "task_type": "platform-agent-evaluation",
            "prompt_asset_id": "route.style-engineering.eval.execute.v1",
            "command": "",
            "source_paths": [profile, metrics, prompt, agent_json, reference, "project.yaml", eval_task],
            "expected_outputs": [eval_candidate, eval_manifest, eval_completion],
            "hard_constraints": [
                "Generate the evaluation candidate from project.yaml under the mounted style prompt; do not copy the corpus reference.",
                "Write the exact candidate, prompt manifest, and completion marker declared by the sidecar.",
                "Do not self-score or label the candidate accepted; deterministic style-eval owns that decision.",
            ],
            "style_constraints": [],
            "validation_gates": ["evaluation sidecar completed", "candidate exists", "prompt manifest exists"],
            "next_allowed_states": ["style-eval-score-file"],
        },
        "style-eval-score-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.eval.score.v1",
            "command": (
                f'python -m literary_engineering_studio_engine style-eval "<project>/{profile_dir}" '
                f'--reference "<project>/{reference}" --candidate "<project>/{eval_candidate}" '
                f'--mode blind-review --out-dir "<project>/{eval_dir}"'
            ),
            "source_paths": [profile, metrics, prompt, reference, eval_candidate, eval_manifest],
            "expected_outputs": [eval_json, eval_report],
            "hard_constraints": [
                "Score the exact current candidate deterministically.",
                "Preserve candidate_sha256 and reference_sha256 in the current score JSON.",
            ],
            "style_constraints": [],
            "validation_gates": ["style score matches current candidate digest", "score and risk are recorded"],
            "next_allowed_states": ["style-eval-readiness", "style-eval-revision"],
        },
        "style-eval-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.style-engineering.eval.fix.v1",
            "command": "",
            "source_paths": [profile, metrics, prompt, agent_json, reference, "project.yaml", eval_candidate, eval_manifest, eval_json, eval_report],
            "expected_outputs": [prompt, agent_json, eval_candidate, eval_manifest, eval_completion],
            "repair_targets": [prompt, agent_json, eval_candidate, eval_manifest],
            "hard_constraints": [
                "Use deterministic score dimensions and risk evidence to revise both the style prompt and the generated candidate.",
                "Do not copy reference phrases to raise similarity and do not edit score files.",
                "Keep style_prompt.md within 500-2500 Chinese-content detail characters and preserve every required prompt block.",
                "Do not self-accept the revision; a fresh deterministic style-eval must score the new candidate digest.",
            ],
            "style_constraints": [],
            "validation_gates": ["at least one declared repair target changed", "style prompt quality passes", "evaluation candidate is complete", "current score becomes stale until rerun"],
            "next_allowed_states": ["style-eval-score-file"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.style-engineering.repair.v1",
        "command": next_action,
        "source_paths": [profile_dir],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and repair the missing style-engineering gate."],
        "style_constraints": [],
        "validation_gates": ["style-engineering gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def validate_task(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    """Validate exactly the style artifacts required by the active state."""

    current_state = str(task.get("current_state") or "")
    profile_dir = profile_dir_for_task(root, task)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "style-profile":
        errors.extend(profile_gate_errors(root, profile_dir))
    if current_state == "style-prompt-task-file":
        errors.extend(profile_gate_errors(root, profile_dir))
        if not (profile_dir / "style_prompt.agent_tasks.md").exists():
            errors.append(f"style prompt task sidecar missing: {relative_path(profile_dir / 'style_prompt.agent_tasks.md', root)}")
    if current_state == "style-prompt-agent-task":
        errors.extend(profile_gate_errors(root, profile_dir))
        errors.extend(prompt_gate_errors(root, profile_dir, require_quality=False))
    if current_state == "style-prompt-quality":
        errors.extend(profile_gate_errors(root, profile_dir))
        errors.extend(prompt_gate_errors(root, profile_dir, require_quality=True))
    if current_state == "style-eval-setup":
        errors.extend(eval_reference_gate_errors(root, profile_dir))
    if current_state == "style-eval-task-file":
        errors.extend(profile_gate_errors(root, profile_dir))
        errors.extend(prompt_gate_errors(root, profile_dir, require_quality=True))
        errors.extend(eval_reference_gate_errors(root, profile_dir))
        if not (profile_dir / "evaluation_results" / "formal" / "platform_agent_candidate.agent_tasks.md").is_file():
            errors.append("formal style evaluation sidecar is missing")
    if current_state == "style-eval-agent-task":
        errors.extend(profile_gate_errors(root, profile_dir))
        errors.extend(prompt_gate_errors(root, profile_dir, require_quality=True))
        errors.extend(eval_agent_gate_errors(root, profile_dir))
    if current_state == "style-eval-score-file":
        errors.extend(eval_agent_gate_errors(root, profile_dir))
        errors.extend(eval_current_score_errors(root, profile_dir, require_accepted=False))
    if current_state == "style-eval-revision":
        errors.extend(declared_repair_targets_changed(root, task, "style-evaluation revision"))
        errors.extend(prompt_gate_errors(root, profile_dir, require_quality=True))
        errors.extend(eval_agent_gate_errors(root, profile_dir))
        if not eval_score_is_stale(profile_dir):
            errors.append("style evaluation revision must make the previous deterministic score stale")
    if current_state == "style-eval-readiness":
        errors.extend(eval_current_score_errors(root, profile_dir, require_accepted=True))
    if current_state in {"style-prompt-agent-task", "style-prompt-quality"} and not errors:
        notes.append("style prompt task completed and quality gate passed")
    if current_state == "style-eval-agent-task" and not errors:
        notes.append("style evaluation candidate completed; deterministic scoring is next")
    if current_state == "style-eval-score-file" and not errors:
        notes.append("deterministic style score recorded for the exact current candidate")
    if current_state == "style-eval-revision" and not errors:
        notes.append("style prompt/evaluation candidate revised; fresh deterministic scoring is required")
    if current_state == "style-eval-readiness" and not errors:
        notes.append("style evaluation readiness passed")
    return errors, notes


def profile_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in (profile_dir / "style-profile.md", profile_dir / "style_metrics.json"):
        if not path.exists():
            errors.append(f"style profile artifact missing: {relative_path(path, root)}")
    return errors


def prompt_gate_errors(root: Path, profile_dir: Path, *, require_quality: bool = True) -> list[str]:
    task_path = profile_dir / "style_prompt.agent_tasks.md"
    prompt_path = profile_dir / "style_prompt.md"
    agent_json = profile_dir / "style_prompt.agent.json"
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"style prompt sidecar is incomplete: {state.get('message')}")
    for path in (prompt_path, agent_json):
        if not path.exists():
            errors.append(f"style prompt artifact missing: {relative_path(path, root)}")
    if prompt_path.exists() and require_quality:
        report = style_prompt_quality_report(_read_text(prompt_path))
        if not report.get("length_ok"):
            errors.append(
                "style_prompt.md detail length must be 500-2500 Chinese-content characters; "
                f"got {report.get('detail_chars')} ({report.get('detail_count_unit')})"
            )
        if not report.get("structure_ok"):
            missing = ", ".join(str(item) for item in report.get("missing_blocks", []))
            errors.append(f"style_prompt.md missing required prompt blocks: {missing}")
    return errors


def eval_reference_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    references = [path for path in sorted((profile_dir / "corpus").glob("*.txt")) if path.is_file() and path.stat().st_size > 0]
    if references:
        return []
    return [f"authorized style evaluation reference missing under {relative_path(profile_dir / 'corpus', root)}"]


def eval_agent_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    eval_dir = profile_dir / "evaluation_results" / "formal"
    candidate = eval_dir / "platform_agent_candidate.md"
    manifest = eval_dir / "platform_agent_candidate.prompt.json"
    task = eval_dir / "platform_agent_candidate.agent_tasks.md"
    errors: list[str] = []
    completion = agent_task_completion_status(task, root=root)
    if completion.get("complete") is not True:
        errors.append(f"style evaluation sidecar is incomplete: {completion.get('message')}")
    if not candidate.is_file() or not _read_text(candidate).strip():
        errors.append(f"style evaluation candidate is missing or empty: {relative_path(candidate, root)}")
    payload, error = _read_optional_json(manifest)
    if error:
        errors.append(error)
    else:
        mode = str(payload.get("mode") or "").strip().lower()
        if mode not in {"back-translation", "outline-expansion", "blind-review"}:
            errors.append(f"style evaluation prompt manifest has invalid mode: {mode or 'missing'}")
        for field in ("style_prompt", "reference", "input", "candidate"):
            if not str(payload.get(field) or "").strip():
                errors.append(f"style evaluation prompt manifest missing {field}")
    return errors


def eval_score_is_stale(profile_dir: Path) -> bool:
    candidate = profile_dir / "evaluation_results" / "formal" / "platform_agent_candidate.md"
    current = profile_dir / "evaluation_results" / "formal" / "style_eval_current.json"
    if not candidate.is_file():
        return False
    payload, error = _read_optional_json(current)
    if error:
        return True
    return str(payload.get("candidate_sha256") or "").strip().lower() != _file_sha256(candidate)


def eval_current_score_errors(root: Path, profile_dir: Path, *, require_accepted: bool) -> list[str]:
    eval_dir = profile_dir / "evaluation_results" / "formal"
    candidate = eval_dir / "platform_agent_candidate.md"
    current = eval_dir / "style_eval_current.json"
    report = eval_dir / "style_eval_current.md"
    payload, error = _read_optional_json(current)
    errors: list[str] = []
    if error:
        return [error]
    if not report.is_file():
        errors.append(f"current style evaluation report missing: {relative_path(report, root)}")
    if payload.get("schema") != "literary-engineering-workbench/style-eval/v0.1":
        errors.append("current style evaluation JSON has wrong or missing schema")
    candidate_sha = _file_sha256(candidate) if candidate.is_file() else ""
    if not candidate_sha or str(payload.get("candidate_sha256") or "").strip().lower() != candidate_sha:
        errors.append("current style evaluation score is stale for the candidate digest")
    try:
        score = float(payload.get("overall_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    risk = str(payload.get("risk_level") or "").strip().lower()
    if require_accepted and (score < 45 or risk in {"high_copy_risk", "low_similarity"}):
        errors.append(f"style evaluation not accepted: overall_score={score}; risk_level={risk or 'missing'}")
    return errors


def accepted_style_eval_jsons(profile_dir: Path) -> list[Path]:
    accepted: list[Path] = []
    for path in sorted((profile_dir / "evaluation_results").glob("*/style_eval_*.json")):
        payload, error = _read_optional_json(path)
        if error:
            continue
        risk = str(payload.get("risk_level") or "")
        try:
            score = float(payload.get("overall_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        if risk in {"high_copy_risk", "low_similarity"} or score < 45:
            continue
        accepted.append(path)
    return accepted


def eval_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    if accepted_style_eval_jsons(profile_dir):
        return []
    return [f"accepted style_eval_*.json missing under {relative_path(profile_dir / 'evaluation_results', root)}"]


def profile_dir_for_task(root: Path, task: dict[str, object]) -> Path:
    profile_dir = str(task.get("profile_dir") or "").strip()
    if profile_dir:
        return resolve_project_path(root, profile_dir)
    source_paths = [str(item) for item in task.get("source_paths") or []]
    for item in source_paths:
        normalized = item.replace("\\", "/")
        if normalized.endswith("/style-profile.md"):
            return resolve_project_path(root, normalized).parent
    profile_id = str(task.get("profile_id") or task.get("target_id") or task.get("scene_id") or "style-profile")
    return root / "style" / profile_id


def declared_repair_targets_changed(root: Path, task: dict[str, object], label: str) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    hashes = task.get("repair_target_sha256_before_revision")
    before = hashes if isinstance(hashes, dict) else {}
    if not targets or not before:
        return [f"{label} is missing declared repair target hash provenance"]
    for target in targets:
        path = resolve_project_path(root, target)
        previous = str(before.get(target) or "").strip().lower()
        if path.is_file() and previous and _file_sha256(path) != previous:
            return []
    return [f"{label} did not change any declared planning candidate; review-only edits cannot complete revision"]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {relative_path(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
