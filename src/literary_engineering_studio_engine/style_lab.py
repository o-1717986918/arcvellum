"""Author-centered style learning projects and mountable style skills."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .model_config import load_config
from .platform_agent_tasks import write_platform_style_prompt_task
from .style_compiler import StyleCompileOptions, compile_style_profile
from .style_prompt import (
    STYLE_PROMPT_MAX_DETAIL_CHARS,
    STYLE_PROMPT_MIN_DETAIL_CHARS,
    count_style_prompt_detail_chars,
    build_style_prompt,
    style_prompt_quality_report,
)


STYLE_LAB_SCHEMA = "literary-engineering-workbench/style-library/v0.1"
STYLE_AUTHOR_SCHEMA = "literary-engineering-workbench/author-style-project/v0.1"
STYLE_WORK_SCHEMA = "literary-engineering-workbench/author-work/v0.1"
STYLE_SOURCE_SCHEMA = "literary-engineering-workbench/author-work-source/v0.1"
STYLE_SKILL_SCHEMA = "literary-engineering-workbench/style-skill/v0.1"
STYLE_MOUNT_SCHEMA = "literary-engineering-workbench/style-skill-mount/v0.1"


@dataclass(frozen=True)
class AuthorProjectResult:
    library_root: Path
    author_id: str
    author_dir: Path
    manifest_path: Path


@dataclass(frozen=True)
class WorkProjectResult:
    library_root: Path
    author_id: str
    work_id: str
    work_dir: Path
    manifest_path: Path


@dataclass(frozen=True)
class SourceImportResult:
    library_root: Path
    author_id: str
    work_id: str
    source_id: str
    raw_path: Path
    normalized_path: Path
    manifest_path: Path
    chunk_count: int
    char_count: int


@dataclass(frozen=True)
class StyleLearningResult:
    library_root: Path
    author_id: str
    profile_id: str
    profile_dir: Path
    profile_path: Path
    metrics_path: Path
    style_prompt_path: Path
    prompt_manifest_path: Path
    source_count: int


@dataclass(frozen=True)
class StyleLearningTaskResult:
    library_root: Path
    author_id: str
    profile_id: str
    profile_dir: Path
    profile_path: Path
    metrics_path: Path
    style_prompt_task_path: Path
    expected_style_prompt_path: Path
    expected_json_path: Path
    source_count: int


@dataclass(frozen=True)
class StyleSkillResult:
    library_root: Path
    author_id: str
    profile_id: str
    style_id: str
    skill_dir: Path
    manifest_path: Path
    style_markdown_path: Path
    prompt_path: Path


@dataclass(frozen=True)
class StyleMountResult:
    project_root: Path
    style_id: str
    mount_dir: Path
    mount_manifest_path: Path
    project_style_path: Path


def default_style_library_root() -> Path:
    cfg = load_config()
    defaults = cfg.get("defaults", {}) if isinstance(cfg.get("defaults"), dict) else {}
    configured = str(defaults.get("style_library_root") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".lew" / "style-library").resolve()


def ensure_style_library(root: Path | None = None) -> Path:
    library = (root or default_style_library_root()).resolve()
    library.mkdir(parents=True, exist_ok=True)
    manifest = library / "library.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "schema": STYLE_LAB_SCHEMA,
                    "created_at": _now(),
                    "updated_at": _now(),
                    "authors_dir": "authors",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return library


def create_author_project(
    library_root: Path | None,
    *,
    name: str,
    author_id: str = "",
    mode: str = "public_domain_or_authorized",
    source_note: str = "",
) -> AuthorProjectResult:
    library = ensure_style_library(library_root)
    resolved_id = _slug(author_id or name or "author")
    author_dir = library / "authors" / resolved_id
    author_dir.mkdir(parents=True, exist_ok=True)
    for child in ["works", "profiles", "style_skills"]:
        (author_dir / child).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": STYLE_AUTHOR_SCHEMA,
        "author_id": resolved_id,
        "name": name.strip() or resolved_id,
        "mode": mode,
        "source_note": source_note,
        "created_at": _now(),
        "updated_at": _now(),
        "works_dir": "works",
        "profiles_dir": "profiles",
        "style_skills_dir": "style_skills",
    }
    manifest_path = author_dir / "author.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = previous.get("created_at", manifest["created_at"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _touch_library(library)
    return AuthorProjectResult(library, resolved_id, author_dir, manifest_path)


def create_author_work(
    library_root: Path | None,
    *,
    author_id: str,
    title: str,
    work_id: str = "",
    year: str = "",
    notes: str = "",
) -> WorkProjectResult:
    library = ensure_style_library(library_root)
    author_dir = _author_dir(library, author_id)
    resolved_id = _slug(work_id or title or "work")
    work_dir = author_dir / "works" / resolved_id
    for child in ["sources/raw", "sources/normalized", "sources/chunks", "analysis"]:
        (work_dir / child).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": STYLE_WORK_SCHEMA,
        "author_id": author_id,
        "work_id": resolved_id,
        "title": title.strip() or resolved_id,
        "year": year,
        "notes": notes,
        "created_at": _now(),
        "updated_at": _now(),
        "source_count": len(list((work_dir / "sources" / "normalized").glob("*.txt"))),
    }
    manifest_path = work_dir / "work.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = previous.get("created_at", manifest["created_at"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_author_timestamp(author_dir)
    return WorkProjectResult(library, author_id, resolved_id, work_dir, manifest_path)


def import_work_source(
    library_root: Path | None,
    *,
    author_id: str,
    work_id: str,
    text: str = "",
    source_path: Path | None = None,
    filename: str = "",
    chunk_chars: int = 4000,
) -> SourceImportResult:
    library = ensure_style_library(library_root)
    work_dir = _work_dir(library, author_id, work_id)
    body = text
    if source_path is not None:
        resolved_source = source_path.resolve()
        if not resolved_source.is_file():
            raise FileNotFoundError(f"source file not found: {resolved_source}")
        body = resolved_source.read_text(encoding="utf-8", errors="ignore")
        filename = filename or resolved_source.name
    body = body.strip()
    if not body:
        raise ValueError("source text is required")
    source_id = _source_id(filename or work_id)
    raw_path = work_dir / "sources" / "raw" / f"{source_id}.txt"
    normalized_path = work_dir / "sources" / "normalized" / f"{source_id}.txt"
    chunks_dir = work_dir / "sources" / "chunks" / source_id
    chunks_dir.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body + "\n", encoding="utf-8")
    normalized = _normalize_text(body)
    normalized_path.write_text(normalized + "\n", encoding="utf-8")
    for old in chunks_dir.glob("*.txt"):
        old.unlink()
    chunks = _chunks(normalized, chunk_chars)
    for index, chunk in enumerate(chunks, start=1):
        (chunks_dir / f"chunk_{index:04d}.txt").write_text(chunk.strip() + "\n", encoding="utf-8")
    manifest_path = work_dir / "sources" / f"{source_id}.source.json"
    manifest = {
        "schema": STYLE_SOURCE_SCHEMA,
        "author_id": author_id,
        "work_id": work_id,
        "source_id": source_id,
        "filename": filename or f"{source_id}.txt",
        "raw": _rel(raw_path, work_dir),
        "normalized": _rel(normalized_path, work_dir),
        "chunks": _rel(chunks_dir, work_dir),
        "chunk_count": len(chunks),
        "char_count": len(normalized),
        "imported_at": _now(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_work_source_count(work_dir)
    _update_author_timestamp(_author_dir(library, author_id))
    return SourceImportResult(library, author_id, work_id, source_id, raw_path, normalized_path, manifest_path, len(chunks), len(normalized))


def list_author_projects(library_root: Path | None = None) -> dict[str, Any]:
    library = ensure_style_library(library_root)
    authors = []
    for path in sorted((library / "authors").glob("*/author.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        author_dir = path.parent
        works = list((author_dir / "works").glob("*/work.json"))
        skills = list((author_dir / "style_skills").glob("*/style_skill.json"))
        authors.append(
            {
                "author_id": payload.get("author_id", path.parent.name),
                "name": payload.get("name", path.parent.name),
                "mode": payload.get("mode", ""),
                "updated_at": payload.get("updated_at", ""),
                "work_count": len(works),
                "style_skill_count": len(skills),
                "path": _rel(author_dir, library),
            }
        )
    return {"library_root": str(library), "authors": authors, "count": len(authors)}


def list_style_skills(library_root: Path | None = None) -> dict[str, Any]:
    library = ensure_style_library(library_root)
    items = []
    for path in sorted((library / "authors").glob("*/style_skills/*/style_skill.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            {
                "style_id": payload.get("style_id", path.parent.name),
                "author_id": payload.get("author_id", path.parents[2].name),
                "author": payload.get("author", ""),
                "profile_id": payload.get("profile_id", ""),
                "mode": payload.get("mode", ""),
                "path": _rel(path.parent, library),
                "prompt": payload.get("prompt", ""),
                "priority": payload.get("priority", 1000),
            }
        )
    return {"library_root": str(library), "items": items, "count": len(items)}


def run_author_style_learning(
    library_root: Path | None,
    *,
    author_id: str,
    profile_id: str = "default",
    provider: str = "auto",
) -> StyleLearningResult:
    library = ensure_style_library(library_root)
    author_dir = _author_dir(library, author_id)
    author = json.loads((author_dir / "author.json").read_text(encoding="utf-8"))
    profile = author_dir / "profiles" / _slug(profile_id or "default")
    corpus_dir = profile / "corpus"
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    normalized_sources = sorted((author_dir / "works").glob("*/sources/normalized/*.txt"))
    if not normalized_sources:
        raise ValueError(f"author has no imported normalized sources: {author_id}")
    for source in normalized_sources:
        work_id = source.parents[2].name
        shutil.copyfile(source, corpus_dir / f"{work_id}-{source.name}")
    compiled = compile_style_profile(
        StyleCompileOptions(
            corpus=corpus_dir,
            output_dir=profile,
            name=str(author.get("name") or author_id),
            author=str(author.get("name") or author_id),
            mode=str(author.get("mode") or "public_domain_or_authorized"),
            source_note=str(author.get("source_note") or ""),
        )
    )
    prompt = build_style_prompt(profile, provider=provider)
    _write_profile_manifest(profile, author, author_id, profile_id, compiled.source_count, provider)
    return StyleLearningResult(
        library,
        author_id,
        _slug(profile_id or "default"),
        profile,
        compiled.profile_path,
        compiled.metrics_path,
        prompt.output_path,
        prompt.manifest_path,
        compiled.source_count,
    )


def run_author_style_learning_platform_task(
    library_root: Path | None,
    *,
    author_id: str,
    profile_id: str = "default",
) -> StyleLearningTaskResult:
    library = ensure_style_library(library_root)
    author_dir = _author_dir(library, author_id)
    author = json.loads((author_dir / "author.json").read_text(encoding="utf-8"))
    profile = author_dir / "profiles" / _slug(profile_id or "default")
    corpus_dir = profile / "corpus"
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    normalized_sources = sorted((author_dir / "works").glob("*/sources/normalized/*.txt"))
    if not normalized_sources:
        raise ValueError(f"author has no imported normalized sources: {author_id}")
    for source in normalized_sources:
        work_id = source.parents[2].name
        shutil.copyfile(source, corpus_dir / f"{work_id}-{source.name}")
    compiled = compile_style_profile(
        StyleCompileOptions(
            corpus=corpus_dir,
            output_dir=profile,
            name=str(author.get("name") or author_id),
            author=str(author.get("name") or author_id),
            mode=str(author.get("mode") or "public_domain_or_authorized"),
            source_note=str(author.get("source_note") or ""),
        )
    )
    task = write_platform_style_prompt_task(profile)
    _write_profile_manifest(profile, author, author_id, profile_id, compiled.source_count, "platform-agent")
    return StyleLearningTaskResult(
        library,
        author_id,
        _slug(profile_id or "default"),
        profile,
        compiled.profile_path,
        compiled.metrics_path,
        task.task_path,
        task.expected_report_path,
        task.expected_json_path,
        compiled.source_count,
    )


def build_style_skill(
    library_root: Path | None,
    *,
    author_id: str,
    profile_id: str = "default",
    style_id: str = "",
) -> StyleSkillResult:
    library = ensure_style_library(library_root)
    author_dir = _author_dir(library, author_id)
    author = json.loads((author_dir / "author.json").read_text(encoding="utf-8"))
    resolved_profile = _slug(profile_id or "default")
    profile = author_dir / "profiles" / resolved_profile
    if not (profile / "style_prompt.md").exists():
        raise FileNotFoundError(f"style prompt not found: {profile / 'style_prompt.md'}")
    resolved_style_id = _slug(style_id or f"{author_id}-{resolved_profile}")
    skill_dir = author_dir / "style_skills" / resolved_style_id
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)
    copies = {
        "style-profile.md": profile / "style-profile.md",
        "style_metrics.json": profile / "style_metrics.json",
        "style_prompt.agent.json": profile / "style_prompt.agent.json",
        "style_prompt.prompt.json": profile / "style_prompt.prompt.json",
        "corpus_manifest.yaml": profile / "corpus_manifest.yaml",
    }
    for name, source in copies.items():
        if source.exists():
            shutil.copyfile(source, skill_dir / name)
    prompt_path = skill_dir / "prompt.md"
    prompt_path.write_text((profile / "style_prompt.md").read_text(encoding="utf-8"), encoding="utf-8")
    source_eval_dir = profile / "evaluation_results"
    target_eval_dir = skill_dir / "evaluation_results"
    if target_eval_dir.exists():
        shutil.rmtree(target_eval_dir)
    if source_eval_dir.exists():
        shutil.copytree(source_eval_dir, target_eval_dir)
    style_markdown_path = skill_dir / "STYLE.md"
    style_markdown_path.write_text(_render_style_skill_markdown(author, resolved_style_id, resolved_profile), encoding="utf-8")
    readiness = _style_skill_readiness(skill_dir)
    manifest = {
        "schema": STYLE_SKILL_SCHEMA,
        "style_id": resolved_style_id,
        "author_id": author_id,
        "author": author.get("name", author_id),
        "profile_id": resolved_profile,
        "mode": author.get("mode", "public_domain_or_authorized"),
        "priority": 1000,
        "prompt": "prompt.md",
        "profile": "style-profile.md",
        "metrics": "style_metrics.json",
        "style_markdown": "STYLE.md",
        "readiness": readiness,
        "created_at": _now(),
        "guardrails": [
            "文风约束优先影响表达、叙述距离、句法节奏、意象系统和心理呈现。",
            f"可靠可挂载的 prompt.md 必须足够详细但可执行，正文中文内容字符为 {STYLE_PROMPT_MIN_DETAIL_CHARS}-{STYLE_PROMPT_MAX_DETAIL_CHARS} 字，计入汉字和中文标点。",
            "文风标点节奏必须建立在标准中文标点约束之上，不得无理由混用中英标点。",
            "文风不得覆盖 canon、人物事实、剧情因果或用户明确约束。",
            "不直接复刻原文连续片段；精确模仿仅限公版或授权语料。",
        ],
    }
    manifest_path = skill_dir / "style_skill.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_author_timestamp(author_dir)
    return StyleSkillResult(library, author_id, resolved_profile, resolved_style_id, skill_dir, manifest_path, style_markdown_path, prompt_path)


def mount_style_skill(
    project_root: Path,
    *,
    library_root: Path | None,
    style_id: str,
    allow_unreviewed: bool = False,
) -> StyleMountResult:
    project = project_root.resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"project root not found: {project}")
    library = ensure_style_library(library_root)
    source = _find_style_skill_dir(library, style_id)
    payload = json.loads((source / "style_skill.json").read_text(encoding="utf-8"))
    readiness = _payload_readiness(payload, source)
    if not readiness.get("ready") and not allow_unreviewed:
        missing = ", ".join(str(item) for item in readiness.get("missing", [])) or "unknown readiness gate"
        blocking = ", ".join(str(item) for item in readiness.get("blocking_risks", []))
        suffix = f"; blocking risks: {blocking}" if blocking else ""
        raise ValueError(
            "style skill is not ready to mount. "
            "Complete platform-agent style prompt generation and effectiveness/risk review first, "
            f"or pass allow_unreviewed for an internal experiment. Missing: {missing}{suffix}"
        )
    mount_dir = project / "style" / "mounted" / str(payload.get("style_id") or style_id)
    if mount_dir.exists():
        shutil.rmtree(mount_dir)
    shutil.copytree(source, mount_dir)
    project_style_path = project / "style" / "active_style_skill.json"
    manifest = {
        "schema": STYLE_MOUNT_SCHEMA,
        "style_id": payload.get("style_id", style_id),
        "author": payload.get("author", ""),
        "author_id": payload.get("author_id", ""),
        "profile_id": payload.get("profile_id", ""),
        "priority": "highest",
        "mount_path": _rel(mount_dir, project),
        "prompt": _rel(mount_dir / str(payload.get("prompt") or "prompt.md"), project),
        "style_skill": _rel(mount_dir / "style_skill.json", project),
        "library_source": _rel(source, library),
        "mounted_at": _now(),
        "allow_unreviewed": allow_unreviewed,
        "readiness": readiness,
        "enforcement": {
            "director": "required",
            "generation": "required",
            "review": "required",
        },
    }
    project_style_path.parent.mkdir(parents=True, exist_ok=True)
    project_style_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_project_yaml_style_mount(project, manifest)
    return StyleMountResult(project, str(payload.get("style_id") or style_id), mount_dir, mount_dir / "style_skill.json", project_style_path)


def active_project_style(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    path = root / "style" / "active_style_skill.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    prompt_path = root / str(payload.get("prompt") or "")
    payload["prompt_exists"] = prompt_path.is_file()
    payload["prompt_path"] = _rel(prompt_path, root) if prompt_path.exists() else ""
    return payload


def _write_profile_manifest(profile: Path, author: dict[str, Any], author_id: str, profile_id: str, source_count: int, provider: str) -> None:
    payload = {
        "schema": "literary-engineering-workbench/author-style-profile/v0.1",
        "author_id": author_id,
        "author": author.get("name", author_id),
        "profile_id": _slug(profile_id or "default"),
        "provider": provider,
        "source_count": source_count,
        "style_profile": "style-profile.md",
        "style_metrics": "style_metrics.json",
        "style_prompt": "style_prompt.md",
        "updated_at": _now(),
    }
    (profile / "profile.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _payload_readiness(payload: dict[str, Any], skill_dir: Path) -> dict[str, Any]:
    readiness = payload.get("readiness")
    if isinstance(readiness, dict):
        fresh = _style_skill_readiness(skill_dir)
        if fresh.get("ready") == readiness.get("ready"):
            fresh["manifest_readiness_checked"] = True
        return fresh
    return _style_skill_readiness(skill_dir)


def _style_skill_readiness(skill_dir: Path) -> dict[str, Any]:
    missing: list[str] = []
    blocking_risks: list[str] = []

    prompt_path = skill_dir / "prompt.md"
    prompt_exists = prompt_path.is_file()
    prompt_detail_chars = 0
    prompt_length_ok = False
    prompt_quality: dict[str, Any] = {}
    agent_json_exists = (skill_dir / "style_prompt.agent.json").is_file()
    eval_jsons = sorted((skill_dir / "evaluation_results").glob("*/style_eval_*.json"))
    accepted_evals: list[dict[str, Any]] = []

    if not prompt_exists:
        missing.append("prompt.md")
    else:
        prompt_quality = style_prompt_quality_report(prompt_path.read_text(encoding="utf-8", errors="ignore"))
        prompt_detail_chars = int(prompt_quality.get("detail_chars") or count_style_prompt_detail_chars(prompt_path.read_text(encoding="utf-8", errors="ignore")))
        prompt_length_ok = bool(prompt_quality.get("length_ok"))
        if prompt_detail_chars < STYLE_PROMPT_MIN_DETAIL_CHARS:
            blocking_risks.append(f"prompt.md: detail_chars_below_{STYLE_PROMPT_MIN_DETAIL_CHARS}")
        elif prompt_detail_chars > STYLE_PROMPT_MAX_DETAIL_CHARS:
            blocking_risks.append(f"prompt.md: detail_chars_above_{STYLE_PROMPT_MAX_DETAIL_CHARS}")
        for missing_block in prompt_quality.get("missing_blocks", []):
            blocking_risks.append(f"prompt.md: missing_required_block:{missing_block}")
    if not agent_json_exists:
        missing.append("style_prompt.agent.json")
    if not eval_jsons:
        missing.append("evaluation_results/*/style_eval_*.json")

    for path in eval_jsons:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            blocking_risks.append(f"{_rel(path, skill_dir)}: invalid_json")
            continue
        risk = str(payload.get("risk_level") or "")
        score = float(payload.get("overall_score") or 0)
        item = {
            "path": _rel(path, skill_dir),
            "mode": payload.get("mode", ""),
            "overall_score": score,
            "risk_level": risk,
        }
        if risk in {"high_copy_risk", "low_similarity"}:
            blocking_risks.append(f"{item['path']}: {risk}")
            continue
        if score < 45:
            blocking_risks.append(f"{item['path']}: score_below_45")
            continue
        accepted_evals.append(item)

    if eval_jsons and not accepted_evals:
        missing.append("accepted style evaluation")

    return {
        "ready": prompt_exists and prompt_length_ok and bool(prompt_quality.get("structure_ok")) and agent_json_exists and bool(accepted_evals) and not blocking_risks,
        "prompt_exists": prompt_exists,
        "prompt_detail_chars": prompt_detail_chars,
        "prompt_length_range": [STYLE_PROMPT_MIN_DETAIL_CHARS, STYLE_PROMPT_MAX_DETAIL_CHARS],
        "prompt_length_ok": prompt_length_ok,
        "prompt_quality": prompt_quality,
        "platform_agent_prompt_json": "style_prompt.agent.json" if agent_json_exists else "",
        "accepted_evaluations": accepted_evals,
        "evaluation_count": len(eval_jsons),
        "missing": missing,
        "blocking_risks": blocking_risks,
        "rules": [
            "style prompt must be written by the platform agent into style_prompt.md",
            f"style prompt detail must be {STYLE_PROMPT_MIN_DETAIL_CHARS}-{STYLE_PROMPT_MAX_DETAIL_CHARS} Chinese-content characters, counting Han characters and Chinese punctuation",
            "style prompt must include identity/boundary, mechanism, narrative distance, syntax/rhythm, punctuation, imagery/sensory, psychology/behavior, dialogue, avoid rules, and self-check blocks",
            "style_prompt.agent.json must record the platform-agent prompt contract",
            "at least one deterministic style_eval JSON must pass copy-risk and similarity gates",
        ],
    }


def _render_style_skill_markdown(author: dict[str, Any], style_id: str, profile_id: str) -> str:
    return f"""# Style Skill: {style_id}

- Author: {author.get("name", "")}
- Profile: {profile_id}
- Mode: {author.get("mode", "public_domain_or_authorized")}

This is a mountable Literary Engineering Workbench style skill.

## Priority

When mounted in a creative project, this style skill has highest priority for expression-level choices: narrative distance, syntax rhythm, image system, sensory balance, dialogue density, and psychological presentation.

It does not override canon, character facts, plot causality, legal/safety boundaries, or explicit user constraints.

## Files

- `style_skill.json`: machine-readable mount contract.
- `prompt.md`: LLM-facing style constraint prompt.
- `style-profile.md`: compiled profile.
- `style_metrics.json`: measurable style signals.

## Readiness

`prompt.md` must be a reliable LLM-facing style constraint prompt with {STYLE_PROMPT_MIN_DETAIL_CHARS}-{STYLE_PROMPT_MAX_DETAIL_CHARS} Chinese-content characters, counting Han characters and Chinese punctuation after Markdown scaffolding is stripped. Shorter prompts are treated as under-specified; longer prompts are treated as too diffuse for stable mounting.
"""


def _find_style_skill_dir(library: Path, style_id: str) -> Path:
    safe = _slug(style_id)
    matches = list((library / "authors").glob(f"*/style_skills/{safe}/style_skill.json"))
    if not matches:
        raise FileNotFoundError(f"style skill not found: {style_id}")
    return matches[0].parent


def _update_project_yaml_style_mount(project: Path, manifest: dict[str, Any]) -> None:
    project_yaml = project / "project.yaml"
    if not project_yaml.exists():
        return
    text = project_yaml.read_text(encoding="utf-8")
    replacement = "\n".join(
        [
            "style:",
            "  mode: public_domain_or_authorized",
            f"  active_style_skill: {json.dumps(manifest.get('style_id', ''), ensure_ascii=False)}",
            "  priority: highest",
            f"  mount_path: {json.dumps(manifest.get('mount_path', ''), ensure_ascii=False)}",
            "  target_profiles:",
            f"    - {json.dumps(manifest.get('style_id', ''), ensure_ascii=False)}",
            "  blend_strategy: single-style-skill",
        ]
    )
    lines = text.splitlines()
    out: list[str] = []
    index = 0
    replaced = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("style:"):
            out.append(replacement)
            replaced = True
            index += 1
            while index < len(lines) and (lines[index].startswith(" ") or not lines[index].strip()):
                index += 1
            continue
        out.append(line)
        index += 1
    if not replaced:
        out.extend(["", replacement])
    project_yaml.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _update_work_source_count(work_dir: Path) -> None:
    manifest_path = work_dir / "work.json"
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["source_count"] = len(list((work_dir / "sources" / "normalized").glob("*.txt")))
    payload["updated_at"] = _now()
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _update_author_timestamp(author_dir: Path) -> None:
    manifest_path = author_dir / "author.json"
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["updated_at"] = _now()
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _touch_library(library: Path) -> None:
    manifest = library / "library.json"
    payload = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {"schema": STYLE_LAB_SCHEMA}
    payload["updated_at"] = _now()
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _author_dir(library: Path, author_id: str) -> Path:
    path = library / "authors" / _slug(author_id)
    if not (path / "author.json").exists():
        raise FileNotFoundError(f"author project not found: {author_id}")
    return path


def _work_dir(library: Path, author_id: str, work_id: str) -> Path:
    path = _author_dir(library, author_id) / "works" / _slug(work_id)
    if not (path / "work.json").exists():
        raise FileNotFoundError(f"work project not found: {author_id}/{work_id}")
    return path


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current:
                paragraphs.append("".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("".join(current))
    return "\n\n".join(paragraphs)


def _chunks(text: str, chunk_chars: int) -> list[str]:
    size = max(int(chunk_chars or 4000), 500)
    return [text[index : index + size] for index in range(0, len(text), size)] or [text]


def _source_id(filename: str) -> str:
    stem = Path(filename).stem if filename else "source"
    return f"{_slug(stem or 'source')}-{uuid4().hex[:6]}"


def _slug(value: str) -> str:
    text = re.sub(r"\s+", "-", str(value).strip().lower())
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", text).strip("-")
    return text[:48].strip("-") or "item"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
