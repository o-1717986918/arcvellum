"""Immutable, content-addressed versions built from formal style evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from ...agent_tasks import agent_task_completion_status, default_agent_completion_path
from ...style_prompt import style_prompt_quality_report
from .review import (
    style_review_evidence,
    style_review_paths,
    style_semantic_review_errors,
)
from .session import (
    load_style_session,
    style_session_gate_errors,
    style_session_source_paths,
)
from .version_package import (
    materialize_style_version,
)
from .version_contracts import (
    COMPATIBLE_STYLE_SKILL_SCHEMA,
    STYLE_VERSION_BUILDER,
    STYLE_VERSION_SCHEMA,
)



class StyleVersionError(ValueError):
    code = "style_version_invalid"


class StyleVersionConflictError(StyleVersionError):
    code = "style_version_conflict"


@dataclass(frozen=True)
class StyleVersionPaths:
    version_dir: Path
    manifest: Path
    compatibility_manifest: Path
    prompt: Path
    profile: Path
    metrics: Path
    prompt_agent: Path
    corpus_manifest: Path
    style_markdown: Path
    evaluation_json: Path
    evaluation_markdown: Path
    review_json: Path
    review_markdown: Path

    def package_files(self) -> tuple[Path, ...]:
        return (
            self.compatibility_manifest,
            self.prompt,
            self.profile,
            self.metrics,
            self.prompt_agent,
            self.corpus_manifest,
            self.style_markdown,
            self.evaluation_json,
            self.evaluation_markdown,
            self.review_json,
            self.review_markdown,
        )

    def all_files(self) -> tuple[Path, ...]:
        return (self.manifest, *self.package_files())


@dataclass(frozen=True)
class StyleVersionPlan:
    project_root: Path
    profile_dir: Path
    style_id: str
    version_id: str
    content_hash: str
    source_evidence: tuple[dict[str, object], ...]
    review_evidence: dict[str, str]
    prompt_quality: dict[str, object]
    paths: StyleVersionPaths
    errors: tuple[str, ...]


@dataclass(frozen=True)
class StyleVersionBuildResult:
    style_id: str
    version_id: str
    content_hash: str
    version_dir: Path
    manifest_path: Path
    compatibility_manifest_path: Path
    created: bool


def plan_style_profile_version(
    project_root: Path,
    profile_dir: Path,
    *,
    target_id: str = "",
) -> StyleVersionPlan:
    root = project_root.resolve()
    profile = _inside(root, profile_dir)
    session = load_style_session(profile)
    author_id = str(session.get("author_id") or "")
    profile_id = str(session.get("profile_id") or target_id or profile.name)
    review_target_id = target_id or profile_id
    style_id = "-".join(item for item in (author_id, profile_id) if item) or profile.name
    review_evidence, evidence_errors = style_review_evidence(root, profile)
    review_evidence.update(_semantic_review_digests(root, profile))
    source_evidence = tuple(_source_evidence(session))
    prompt_quality = _prompt_quality(profile)
    errors = _build_gate_errors(
        root,
        profile,
        review_target_id,
        evidence_errors,
        prompt_quality,
    )
    hash_basis = {
        "builder": STYLE_VERSION_BUILDER,
        "style_id": style_id,
        "author_id": author_id,
        "profile_id": profile_id,
        "session_id": str(session.get("session_id") or ""),
        "session_request_digest": str(session.get("request_digest") or ""),
        "source_evidence": source_evidence,
        "artifact_digests": {
            key: value
            for key, value in review_evidence.items()
            if key.endswith("_sha256")
        },
        "prompt_detail_chars": int(prompt_quality.get("detail_chars") or 0),
        "prompt_detail_count_unit": str(prompt_quality.get("detail_count_unit") or ""),
    }
    content_hash = _object_sha256(hash_basis)
    version_id = f"v1-{content_hash[:20]}"
    version_dir = profile / "versions" / version_id
    return StyleVersionPlan(
        root,
        profile,
        style_id,
        version_id,
        content_hash,
        source_evidence,
        review_evidence,
        prompt_quality,
        _version_paths(version_dir),
        tuple(dict.fromkeys(errors)),
    )


def build_style_profile_version(
    project_root: Path,
    profile_dir: Path,
    *,
    target_id: str = "",
) -> StyleVersionBuildResult:
    plan = plan_style_profile_version(project_root, profile_dir, target_id=target_id)
    if plan.errors:
        raise StyleVersionError("style version evidence is not ready: " + "; ".join(plan.errors))
    if plan.paths.version_dir.exists():
        if _is_empty_task_scaffold(plan):
            shutil.rmtree(plan.paths.version_dir)
        else:
            errors = style_profile_version_errors(plan)
            if errors:
                raise StyleVersionConflictError(
                    f"immutable style version conflicts at {plan.paths.version_dir}: "
                    + "; ".join(errors)
                )
            return _result(plan, created=False)

    plan.paths.version_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = plan.paths.version_dir.parent / f".{plan.version_id}.build-{uuid4().hex}"
    try:
        temporary.mkdir(parents=False, exist_ok=False)
        materialize_style_version(plan, temporary)
        temporary.rename(plan.paths.version_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        if plan.paths.version_dir.is_dir() and not style_profile_version_errors(plan):
            return _result(plan, created=False)
        raise
    return _result(plan, created=True)


def inspect_style_profile_version(plan: StyleVersionPlan) -> tuple[str, tuple[str, ...]]:
    if plan.errors:
        return "blocked", plan.errors
    if not plan.paths.manifest.is_file():
        return "build", ()
    errors = tuple(style_profile_version_errors(plan))
    return ("ready", ()) if not errors else ("conflict", errors)


def style_profile_version_errors(plan: StyleVersionPlan) -> list[str]:
    manifest = _read_object(plan.paths.manifest)
    errors: list[str] = []
    expected = {
        "schema": STYLE_VERSION_SCHEMA,
        "style_id": plan.style_id,
        "version_id": plan.version_id,
        "content_hash": plan.content_hash,
        "builder": STYLE_VERSION_BUILDER,
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            errors.append(f"style version manifest has invalid {field}")
    errors.extend(_artifact_integrity_errors(plan, manifest))
    errors.extend(_compatibility_errors(plan))
    return errors


def style_version_source_paths(plan: StyleVersionPlan) -> tuple[Path, ...]:
    profile = plan.profile_dir
    evaluation = profile / "evaluation_results" / "formal"
    prompt_task = profile / "style_prompt.agent_tasks.md"
    eval_task = evaluation / "platform_agent_candidate.agent_tasks.md"
    review = style_review_paths(profile)
    candidates = [
        plan.project_root / "project.yaml",
        profile / "style_session.json",
        profile / "style-profile.md",
        profile / "style_metrics.json",
        profile / "corpus_manifest.yaml",
        profile / "style_prompt.md",
        profile / "style_prompt.agent.json",
        prompt_task,
        default_agent_completion_path(prompt_task),
        evaluation / "platform_agent_candidate.md",
        evaluation / "platform_agent_candidate.prompt.json",
        eval_task,
        default_agent_completion_path(eval_task),
        evaluation / "style_eval_current.json",
        evaluation / "style_eval_current.md",
        review.review_json,
        review.review_markdown,
        review.task,
        review.completion,
        *style_session_source_paths(profile),
    ]
    return tuple(dict.fromkeys(path for path in candidates if path.is_file()))


def _build_gate_errors(
    root: Path,
    profile: Path,
    profile_id: str,
    evidence_errors: list[str],
    prompt_quality: dict[str, object],
) -> list[str]:
    errors = list(style_session_gate_errors(profile))
    errors.extend(evidence_errors)
    if not prompt_quality.get("length_ok"):
        errors.append("style version prompt fails the 500-2500 Chinese-content character gate")
    if not prompt_quality.get("structure_ok"):
        errors.append("style version prompt is missing required executable prompt blocks")
    errors.extend(_completion_errors(root, profile / "style_prompt.agent_tasks.md", "style prompt"))
    evaluation_task = profile / "evaluation_results/formal/platform_agent_candidate.agent_tasks.md"
    errors.extend(_completion_errors(root, evaluation_task, "style evaluation"))
    errors.extend(
        style_semantic_review_errors(
            root,
            profile,
            target_id=profile_id,
            require_pass=True,
        )
    )
    return errors


def _completion_errors(root: Path, task: Path, label: str) -> list[str]:
    state = agent_task_completion_status(task, root=root)
    if state.get("complete") is True:
        return []
    return [f"{label} sidecar is incomplete: {state.get('message')}"]


def _artifact_integrity_errors(
    plan: StyleVersionPlan,
    manifest: dict[str, Any],
) -> list[str]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["style version manifest artifacts are missing"]
    expected = {
        path.relative_to(plan.paths.version_dir).as_posix()
        for path in plan.paths.package_files()
    }
    if set(artifacts) != expected:
        return ["style version manifest artifact inventory is incomplete or unexpected"]
    errors: list[str] = []
    for relative in sorted(expected):
        path = _safe_version_path(plan.paths.version_dir, relative)
        if not path.is_file() or str(artifacts.get(relative) or "") != _sha256(path):
            errors.append(f"style version artifact is missing or stale: {relative}")
    return errors


def _compatibility_errors(plan: StyleVersionPlan) -> list[str]:
    payload = _read_object(plan.paths.compatibility_manifest)
    expected = {
        "schema": COMPATIBLE_STYLE_SKILL_SCHEMA,
        "style_id": plan.style_id,
        "version_id": plan.version_id,
        "content_hash": plan.content_hash,
        "review_status": "pass",
    }
    errors = [
        f"compatible style skill has invalid {field}"
        for field, value in expected.items()
        if payload.get(field) != value
    ]
    quality = _prompt_quality(plan.paths.version_dir, prompt_name="prompt.md")
    if not quality.get("length_ok") or not quality.get("structure_ok"):
        errors.append("compatible style skill prompt fails quality gates")
    return errors


def _source_evidence(session: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in ("training_sources", "holdout_sources"):
        values = session.get(group)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            rights = value.get("rights") if isinstance(value.get("rights"), dict) else {}
            rows.append(
                {
                    "group": group,
                    "identity": str(value.get("identity") or ""),
                    "work_id": str(value.get("work_id") or ""),
                    "source_id": str(value.get("source_id") or ""),
                    "content_sha256": str(value.get("content_sha256") or ""),
                    "rights": {
                        "mode": str(rights.get("mode") or ""),
                        "declaration": str(rights.get("declaration") or ""),
                    },
                }
            )
    return rows


def _semantic_review_digests(root: Path, profile: Path) -> dict[str, str]:
    paths = style_review_paths(profile)
    artifacts = {
        "semantic_review": paths.review_json,
        "semantic_review_report": paths.review_markdown,
        "semantic_review_task": paths.task,
        "semantic_review_completion": paths.completion,
    }
    evidence: dict[str, str] = {}
    for name, path in artifacts.items():
        if not path.is_file():
            continue
        evidence[f"{name}_path"] = path.relative_to(root).as_posix()
        evidence[f"{name}_sha256"] = _sha256(path)
    return evidence


def _version_paths(version_dir: Path) -> StyleVersionPaths:
    evaluation = version_dir / "evaluation_results" / "formal"
    return StyleVersionPaths(
        version_dir,
        version_dir / "style_version.json",
        version_dir / "style_skill.json",
        version_dir / "prompt.md",
        version_dir / "style-profile.md",
        version_dir / "style_metrics.json",
        version_dir / "style_prompt.agent.json",
        version_dir / "corpus_manifest.yaml",
        version_dir / "STYLE.md",
        evaluation / "style_eval_current.json",
        evaluation / "style_eval_current.md",
        evaluation / "style_semantic_review.json",
        evaluation / "style_semantic_review.md",
    )


def _prompt_quality(profile_dir: Path, *, prompt_name: str = "style_prompt.md") -> dict[str, object]:
    prompt = profile_dir / prompt_name
    if not prompt.is_file():
        return {}
    return style_prompt_quality_report(prompt.read_text(encoding="utf-8", errors="ignore"))


def _result(plan: StyleVersionPlan, *, created: bool) -> StyleVersionBuildResult:
    return StyleVersionBuildResult(
        plan.style_id,
        plan.version_id,
        plan.content_hash,
        plan.paths.version_dir,
        plan.paths.manifest,
        plan.paths.compatibility_manifest,
        created,
    )


def _is_empty_task_scaffold(plan: StyleVersionPlan) -> bool:
    entries = list(plan.paths.version_dir.rglob("*"))
    allowed_files = {path.resolve() for path in plan.paths.all_files()}
    allowed_dirs = {
        parent.resolve()
        for path in plan.paths.all_files()
        for parent in path.parents
        if parent != plan.paths.version_dir.parent
        and parent.is_relative_to(plan.paths.version_dir)
    }
    return all(
        (
            entry.is_dir()
            and entry.resolve() in allowed_dirs
        )
        or (
            entry.is_file()
            and entry.resolve() in allowed_files
            and entry.stat().st_size == 0
        )
        for entry in entries
    )


def _safe_version_path(version_dir: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise StyleVersionConflictError(f"style version artifact path is invalid: {relative}")
    path = (version_dir / relative).resolve()
    if not path.is_relative_to(version_dir.resolve()):
        raise StyleVersionConflictError("style version artifact path escapes version directory")
    return path


def _inside(root: Path, path: Path) -> Path:
    resolved = (path if path.is_absolute() else root / path).resolve()
    if not resolved.is_relative_to(root):
        raise StyleVersionError("style profile directory must be inside the work project")
    return resolved


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _object_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
