"""Version projection for Engine-owned style profiles and built style skills."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from literary_engineering_studio_engine.public.literary import style_prompt_quality_report

from .contracts import StyleVersionState
from .evaluation_projection import project_evaluations
from .formal_version_projection import (
    project_formal_version_detail,
    project_formal_versions,
)


class StyleVersionProjectionService:
    def project_work_versions(
        self,
        project_root: Path,
        *,
        active_style_id: str = "",
        active_content_hash: str = "",
    ) -> tuple[list[dict[str, object]], list[str]]:
        return project_formal_versions(
            project_root,
            active_style_id=active_style_id,
            active_content_hash=active_content_hash,
        )

    def version_detail(
        self,
        project_root: Path,
        *,
        style_id: str,
        version_id: str,
    ) -> dict[str, object]:
        return project_formal_version_detail(
            project_root,
            style_id=style_id,
            version_id=version_id,
        )

    def project_author_versions(
        self,
        library_root: Path,
        author_dir: Path,
        *,
        active_style_id: str = "",
        active_content_hash: str = "",
    ) -> tuple[list[dict[str, object]], list[str]]:
        versions: list[dict[str, object]] = []
        issues: list[str] = []
        author_id = author_dir.name
        for profile_dir in sorted((author_dir / "profiles").glob("*")):
            if not profile_dir.is_dir() or not _inside(library_root, profile_dir):
                continue
            version, profile_issues = self._project_profile(
                author_id,
                profile_dir,
                active_style_id=active_style_id,
                active_content_hash=active_content_hash,
            )
            versions.append(version)
            issues.extend(profile_issues)
        return versions, issues

    def _project_profile(
        self,
        author_id: str,
        profile_dir: Path,
        *,
        active_style_id: str,
        active_content_hash: str,
    ) -> tuple[dict[str, object], list[str]]:
        profile_manifest = _read_json(profile_dir / "profile.json")
        profile_id = str(profile_manifest.get("profile_id") or profile_dir.name)
        prompt_path = profile_dir / "style_prompt.md"
        prompt_hash = _sha256(prompt_path)
        prompt_quality = (
            style_prompt_quality_report(prompt_path.read_text(encoding="utf-8", errors="ignore"))
            if prompt_path.is_file()
            else {}
        )
        evaluations, issues = project_evaluations(profile_dir)
        accepted = [
            item
            for item in evaluations
            if item["style_quality_status"] == "pass" and item["leakage_risk_status"] == "clear"
        ]
        skill = _find_skill_for_profile(profile_dir.parents[1], profile_id)
        skill_manifest = _read_json(skill / "style_skill.json") if skill else {}
        style_id = str(skill_manifest.get("style_id") or "")
        content_hash = _aggregate_hash(
            profile_dir / "style-profile.md",
            profile_dir / "style_metrics.json",
            prompt_path,
            *((profile_dir / "corpus").glob("*.txt")),
            *((profile_dir / "evaluation_results").glob("*/style_eval_*.json")),
        )
        state = _version_state(
            prompt_exists=prompt_path.is_file(),
            prompt_quality=prompt_quality,
            has_evaluation=bool(evaluations),
            accepted=bool(accepted),
            has_skill=bool(skill_manifest),
            mounted=bool(style_id and style_id == active_style_id and content_hash == active_content_hash),
        )
        return {
            "schema": "arcvellum/style-profile-version-projection/v1",
            "version_id": content_hash,
            "author_id": author_id,
            "profile_id": profile_id,
            "style_id": style_id,
            "state": state.value,
            "source_count": len([path for path in (profile_dir / "corpus").glob("*.txt") if path.is_file()]),
            "source_hash": _aggregate_hash(*((profile_dir / "corpus").glob("*.txt"))),
            "profile_hash": _sha256(profile_dir / "style-profile.md"),
            "prompt_hash": prompt_hash,
            "prompt_quality": prompt_quality,
            "evaluations": evaluations,
            "accepted_evaluation_count": len(accepted),
            "compiler_version": str(profile_manifest.get("compiler_version") or "legacy-v0.1"),
            "review_status": str(skill_manifest.get("review_status") or "not-recorded"),
            "content_hash": content_hash,
            "mounted": state is StyleVersionState.MOUNTED,
        }, issues


def _version_state(
    *,
    prompt_exists: bool,
    prompt_quality: dict[str, object],
    has_evaluation: bool,
    accepted: bool,
    has_skill: bool,
    mounted: bool,
) -> StyleVersionState:
    if mounted:
        return StyleVersionState.MOUNTED
    if has_skill and accepted and prompt_quality.get("length_ok") and prompt_quality.get("structure_ok"):
        return StyleVersionState.MOUNTABLE
    if has_evaluation:
        return StyleVersionState.EVALUATED
    if prompt_exists:
        return StyleVersionState.PROMPT_CANDIDATE
    return StyleVersionState.PROFILE


def _find_skill_for_profile(author_dir: Path, profile_id: str) -> Path | None:
    for manifest_path in sorted((author_dir / "style_skills").glob("*/style_skill.json")):
        payload = _read_json(manifest_path)
        if str(payload.get("profile_id") or "") == profile_id:
            return manifest_path.parent
    return None


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _aggregate_hash(*paths: Path) -> str:
    digest = hashlib.sha256()
    found = False
    for path in sorted((item for item in paths if item.is_file()), key=lambda item: item.as_posix()):
        found = True
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest() if found else ""


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
