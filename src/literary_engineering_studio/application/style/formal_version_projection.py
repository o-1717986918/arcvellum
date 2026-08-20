"""Safe projections for project-local immutable style profile versions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.literary import (
    formal_style_profile_dirs,
    load_style_session,
)
from literary_engineering_studio_engine.public.literary import (
    inspect_style_profile_version,
    inspect_style_version_directory,
    plan_style_profile_version,
)

from .contracts import RightsStatus, StyleVersionState
from .evaluation_projection import project_evaluations


def project_formal_versions(
    project_root: Path,
    *,
    active_style_id: str = "",
    active_content_hash: str = "",
) -> tuple[list[dict[str, object]], list[str]]:
    versions: list[dict[str, object]] = []
    issues: list[str] = []
    for profile in formal_style_profile_dirs(project_root):
        session = load_style_session(profile)
        plan = plan_style_profile_version(
            project_root,
            profile,
            target_id=_target_id(project_root, profile),
        )
        built_ids: set[str] = set()
        for version_dir in sorted((profile / "versions").glob("v1-*")):
            if not version_dir.is_dir():
                continue
            manifest, errors = inspect_style_version_directory(version_dir)
            if manifest:
                built_ids.add(str(manifest.get("version_id") or version_dir.name))
            versions.append(
                _built_projection(
                    session,
                    manifest,
                    errors,
                    active_style_id=active_style_id,
                    active_content_hash=active_content_hash,
                )
            )
            if errors:
                issues.append(
                    f"{_session_label(session)}:{version_dir.name}: package-integrity"
                )
        stage, stage_errors = inspect_style_profile_version(plan)
        if plan.version_id not in built_ids and stage != "conflict":
            versions.append(
                _planned_projection(
                    profile,
                    session,
                    plan,
                    stage,
                    stage_errors,
                )
            )
    return versions, issues


def project_formal_version_detail(
    project_root: Path,
    *,
    style_id: str,
    version_id: str,
) -> dict[str, object]:
    version_dir, manifest, errors = _find_version(
        project_root,
        style_id,
        version_id,
    )
    return _detail_projection(version_dir, manifest, errors)


def _find_version(
    project_root: Path,
    style_id: str,
    version_id: str,
) -> tuple[Path, dict[str, Any], tuple[str, ...]]:
    for profile in formal_style_profile_dirs(project_root):
        version_dir = profile / "versions" / version_id
        if not version_dir.is_dir():
            continue
        manifest, errors = inspect_style_version_directory(version_dir)
        if str(manifest.get("style_id") or "") != style_id:
            continue
        return version_dir, manifest, errors
    raise FileNotFoundError(
        f"style profile version not found: {style_id}/{version_id}"
    )


def _detail_projection(
    version_dir: Path,
    manifest: dict[str, Any],
    errors: tuple[str, ...],
) -> dict[str, object]:
    review = _read_object(
        version_dir
        / "evaluation_results"
        / "formal"
        / "style_semantic_review.json"
    )
    return {
        "schema": "arcvellum/style-profile-version-detail/v1",
        "style_id": str(manifest.get("style_id") or ""),
        "version_id": str(manifest.get("version_id") or ""),
        "content_hash": str(manifest.get("content_hash") or ""),
        "author_id": str(manifest.get("author_id") or ""),
        "profile_id": str(manifest.get("profile_id") or ""),
        "session_id": str(manifest.get("session_id") or ""),
        "compiler_version": str(manifest.get("builder") or ""),
        "state": _built_state(errors, mounted=False).value,
        "integrity": {
            "status": "pass" if not errors else "conflict",
            "issues": _public_integrity_errors(errors),
        },
        "source_evidence": _safe_source_evidence(
            manifest.get("source_evidence")
        ),
        "prompt_quality": _safe_prompt_quality(manifest.get("prompt_quality")),
        "evaluation": _safe_evaluation(manifest.get("evaluation")),
        "review": _safe_review(manifest, review),
        "priority": _object(manifest.get("priority")),
        "copy_boundary": str(manifest.get("copy_boundary") or ""),
        "artifacts": _safe_artifacts(manifest.get("artifacts")),
    }


def _planned_projection(
    profile: Path,
    session: dict[str, object],
    plan: Any,
    stage: str,
    errors: tuple[str, ...],
) -> dict[str, object]:
    evaluations, _ = project_evaluations(profile)
    state = (
        StyleVersionState.BUILD_READY
        if stage == "build"
        else StyleVersionState.ENGINEERING
    )
    return {
        "schema": "arcvellum/style-profile-version-projection/v1",
        "origin": "formal-session",
        "version_id": "",
        "planned_version_id": plan.version_id,
        "author_id": str(session.get("author_id") or ""),
        "profile_id": str(session.get("profile_id") or ""),
        "style_id": plan.style_id,
        "display_name": str(session.get("display_name") or ""),
        "state": state.value,
        "source_count": len(plan.source_evidence),
        "rights": _rights_summary(plan.source_evidence),
        "prompt_quality": _safe_prompt_quality(plan.prompt_quality),
        "evaluations": evaluations,
        "accepted_evaluation_count": sum(
            1
            for item in evaluations
            if item.get("style_quality_status") == "pass"
            and item.get("leakage_risk_status") == "clear"
        ),
        "compiler_version": "",
        "review_status": "pass" if stage == "build" else "in-progress",
        "content_hash": "",
        "planned_content_hash": plan.content_hash,
        "built": False,
        "mounted": False,
        "build_status": stage,
        "blocking_reasons": (
            [] if not errors else ["formal-evidence-incomplete"]
        ),
    }


def _built_projection(
    session: dict[str, object],
    manifest: dict[str, Any],
    errors: tuple[str, ...],
    *,
    active_style_id: str,
    active_content_hash: str,
) -> dict[str, object]:
    style_id = str(manifest.get("style_id") or "")
    content_hash = str(manifest.get("content_hash") or "")
    author_id, profile_id = _built_identity(manifest, session)
    mounted = (
        not errors
        and style_id == active_style_id
        and content_hash == active_content_hash
    )
    state = _built_state(errors, mounted)
    source_evidence = manifest.get("source_evidence")
    return {
        "schema": "arcvellum/style-profile-version-projection/v1",
        "origin": "formal-session",
        "version_id": str(manifest.get("version_id") or ""),
        "planned_version_id": "",
        "author_id": author_id,
        "profile_id": profile_id,
        "style_id": style_id,
        "display_name": str(session.get("display_name") or ""),
        "state": state.value,
        "source_count": len(
            source_evidence if isinstance(source_evidence, list) else []
        ),
        "rights": _rights_summary(source_evidence),
        "prompt_quality": _safe_prompt_quality(
            manifest.get("prompt_quality")
        ),
        "evaluations": [_safe_evaluation(manifest.get("evaluation"))],
        "accepted_evaluation_count": 1 if not errors else 0,
        "compiler_version": str(manifest.get("builder") or ""),
        "review_status": str(manifest.get("review_status") or ""),
        "content_hash": content_hash,
        "planned_content_hash": "",
        "built": True,
        "mounted": mounted,
        "build_status": "ready" if not errors else "conflict",
        "blocking_reasons": _public_integrity_errors(errors),
    }


def _built_identity(
    manifest: dict[str, Any],
    session: dict[str, object],
) -> tuple[str, str]:
    return (
        str(manifest.get("author_id") or session.get("author_id") or ""),
        str(manifest.get("profile_id") or session.get("profile_id") or ""),
    )


def _built_state(
    errors: tuple[str, ...],
    mounted: bool,
) -> StyleVersionState:
    if errors:
        return StyleVersionState.CONFLICT
    return StyleVersionState.MOUNTED if mounted else StyleVersionState.MOUNTABLE


def _safe_review(
    manifest: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, object]:
    evidence = _object(manifest.get("review_evidence"))
    return {
        "status": str(manifest.get("review_status") or ""),
        "verdict": str(review.get("verdict") or ""),
        "reviewer_session_id": str(manifest.get("reviewer_session_id") or ""),
        "evidence_digest_count": sum(
            1 for key in evidence if key.endswith("_sha256")
        ),
    }


def _safe_artifacts(value: object) -> list[dict[str, str]]:
    return [
        {"name": name, "sha256": str(digest)}
        for name, digest in sorted(_object(value).items())
    ]


def _safe_source_evidence(value: object) -> list[dict[str, object]]:
    rows = value if isinstance(value, list) else []
    projected: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rights = _object(row.get("rights"))
        projected.append(
            {
                "group": str(row.get("group") or ""),
                "identity": str(row.get("identity") or ""),
                "work_id": str(row.get("work_id") or ""),
                "source_id": str(row.get("source_id") or ""),
                "content_sha256": str(row.get("content_sha256") or ""),
                "rights": {
                    "status": (
                        RightsStatus.DECLARED.value
                        if rights.get("mode") and rights.get("declaration")
                        else RightsStatus.MISSING.value
                    ),
                    "mode": str(rights.get("mode") or ""),
                    "declaration_present": bool(
                        str(rights.get("declaration") or "").strip()
                    ),
                },
            }
        )
    return projected


def _rights_summary(value: object) -> dict[str, object]:
    evidence = _safe_source_evidence(value)
    modes = sorted(
        {
            str(_object(item.get("rights")).get("mode") or "")
            for item in evidence
            if _object(item.get("rights")).get("mode")
        }
    )
    declared = bool(evidence) and all(
        _object(item.get("rights")).get("status")
        == RightsStatus.DECLARED.value
        for item in evidence
    )
    return {
        "status": (
            RightsStatus.DECLARED.value
            if declared
            else RightsStatus.MISSING.value
        ),
        "modes": modes,
    }


def _safe_prompt_quality(value: object) -> dict[str, object]:
    quality = _object(value)
    allowed = (
        "detail_chars",
        "detail_count_unit",
        "length_ok",
        "structure_ok",
        "missing_sections",
    )
    return {key: quality[key] for key in allowed if key in quality}


def _safe_evaluation(value: object) -> dict[str, object]:
    evaluation = _object(value)
    allowed = (
        "overall_score",
        "risk_level",
        "candidate_sha256",
        "reference_sha256",
    )
    return {key: evaluation[key] for key in allowed if key in evaluation}


def _public_integrity_errors(errors: tuple[str, ...]) -> list[str]:
    categories: list[str] = []
    for error in errors:
        if "artifact" in error:
            category = "artifact-integrity"
        elif "compatible style skill" in error:
            category = "compatibility-integrity"
        elif "prompt" in error:
            category = "prompt-integrity"
        elif "directory" in error:
            category = "directory-integrity"
        else:
            category = "manifest-integrity"
        if category not in categories:
            categories.append(category)
    return categories


def _target_id(project_root: Path, profile: Path) -> str:
    relative = profile.relative_to(project_root).as_posix()
    value = relative.lower().replace("/", "-").replace("_", "-")
    return "-".join(part for part in value.split("-") if part)


def _session_label(session: dict[str, object]) -> str:
    return "-".join(
        value
        for value in (
            str(session.get("author_id") or ""),
            str(session.get("profile_id") or ""),
        )
        if value
    ) or "style-profile"


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
