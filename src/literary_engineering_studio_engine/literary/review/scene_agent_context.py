"""Read-only context assembly for legacy provider-backed scene review."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from ...context_broker import default_context_trace_path
from ...creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
)
from ...draft_text import final_body_from_workbench_text
from ...narrative_rhythm import render_narrative_rhythm_contract
from ...reader_experience import reader_experience_adherence_for_body, scene_chapter_obligation_id
from ...word_budget import word_budget_adherence_for_body
from .style_context import render_review_style_snapshot, scene_review_style_context


@dataclass(frozen=True)
class SceneAgentReviewContext:
    root: Path
    scene_path: Path
    draft_path: Path
    scene_id: str
    source_paths: list[str]
    scene_text: str
    draft_text: str
    candidate_sha256: str
    context_text: str
    context_trace_text: str
    style_text: str
    style_mount_snapshot: dict[str, str]
    quality_profile: dict[str, object]
    quality_path: Path
    word_budget_adherence: dict[str, object]
    reader_adherence: dict[str, object]
    rhythm_contract_text: str


def prepare_scene_agent_review_context(
    project_root: Path,
    scene: Path | None,
    draft: Path | None,
) -> SceneAgentReviewContext:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scene_path = resolve_scene(root, scene)
    scene_id = scene_path.stem
    draft_path = resolve_draft(root, scene_id, draft)
    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    trace_path = default_context_trace_path(context_path)
    style_context = scene_review_style_context(root)
    quality_profile = load_creative_quality_profile(root)
    quality_path = creative_quality_profile_path(root)
    source_paths = _source_paths(
        root,
        scene_path,
        draft_path,
        context_path,
        trace_path,
        style_context.evidence_paths,
        quality_path,
    )
    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    obligation = root / "plot" / "chapter_obligations" / f"{scene_chapter_obligation_id(root, scene_path)}.json"
    for path in (composition, obligation):
        if path.exists():
            source_paths.append(relative_path(path, root))
    draft_text = read_text(draft_path) if draft_path.exists() else ""
    draft_body = final_body_from_workbench_text(draft_text) or draft_text
    return SceneAgentReviewContext(
        root=root,
        scene_path=scene_path,
        draft_path=draft_path,
        scene_id=scene_id,
        source_paths=source_paths,
        scene_text=read_text(scene_path),
        draft_text=draft_text,
        candidate_sha256=hashlib.sha256(draft_path.read_bytes()).hexdigest(),
        context_text=read_text(context_path) if context_path.exists() else "",
        context_trace_text=read_text(trace_path) if trace_path.exists() else "",
        style_text=render_review_style_snapshot(style_context.snapshot)
        + "\n\n"
        + (read_text(style_context.prompt_path) if style_context.prompt_path else ""),
        style_mount_snapshot=style_context.snapshot,
        quality_profile=quality_profile,
        quality_path=quality_path,
        word_budget_adherence=word_budget_adherence_for_body(root, scene_path, draft_body),
        reader_adherence=reader_experience_adherence_for_body(root, scene_path, draft_body),
        rhythm_contract_text=render_narrative_rhythm_contract(
            root,
            scene_path,
            composition if composition.exists() else None,
        ),
    )


def _source_paths(
    root: Path,
    scene_path: Path,
    draft_path: Path,
    context_path: Path,
    trace_path: Path,
    style_paths: list[Path],
    quality_path: Path,
) -> list[str]:
    paths = [scene_path]
    paths.extend(path for path in (draft_path, context_path, trace_path) if path.exists())
    paths.extend(style_paths)
    source_paths = list(dict.fromkeys(relative_path(path, root) for path in paths))
    if creative_quality_profile_exists(root):
        source_paths.append(relative_path(quality_path, root))
    return source_paths


def resolve_scene(root: Path, scene: Path | None) -> Path:
    path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not path.exists():
        raise FileNotFoundError(f"scene file not found: {path}")
    return path.resolve()


def resolve_draft(root: Path, scene_id: str, draft: Path | None) -> Path:
    if draft is None:
        return root / "drafts" / "scenes" / f"{scene_id}.md"
    return draft if draft.is_absolute() else root / draft


def resolve_output(root: Path, value: Path | None, *default_parts: str) -> Path:
    if value is None:
        return root.joinpath(*default_parts)
    return value if value.is_absolute() else root / value


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = ["SceneAgentReviewContext", "prepare_scene_agent_review_context"]
