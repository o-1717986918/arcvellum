"""Source-labelled continuity starter packet for a scene creator."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.literary import SceneBrief, active_style_prompt_text

from ..application.creator_persona import CreatorPersonaStore
from ..application.style.owner_directive import read_owner_style_directive
from .scene_creator_workspace import SceneCreatorWorkspace


def build_scene_creator_briefing(
    brief: SceneBrief, workspace: SceneCreatorWorkspace, persona_store: CreatorPersonaStore,
) -> dict[str, Any]:
    """Give essential evidence directly and disclose every excerpt or missing source."""
    root = workspace.archive_root
    persona = persona_store.read(root)
    versions = persona.get("versions") or []
    active = versions[-1] if versions else None
    refs = tuple(brief.source_refs)
    prior_prose = next((item for item in refs if item.startswith("drafts/scenes/")), "")
    prior_delta = next((item for item in refs if item.startswith("workflow/scene_deltas/")), "")
    fields = [
        ("whole_work_intent", "plot/lean_project_plan.json", "planning", "north_star"),
        ("latest_user_direction", "workflow/studio/user_directions.md", "user_direction", "tail"),
        ("previous_committed_prose", prior_prose, "scene_prose", "full"),
        ("previous_scene_delta", prior_delta, "mixed_continuity", "full"),
        ("current_continuity", "workflow/continuity/current.json", "mixed_continuity", "full"),
    ]
    sources = [_entry(root, name, path, status, projection) for name, path, status, projection in fields]
    sources.extend(_referenced_archive_sources(root, brief.scene_id, refs))
    style_sources = [item for item in refs if item.startswith("style/") or "style-profile" in item]
    return {
        "schema": "arcvellum/scene-creator-briefing/v1",
        "scene_id": brief.scene_id,
        "scene_brief": brief.to_dict(),
        "creator_persona": _persona_payload(active, persona),
        "canon_constraints": {"status": "from_scene_brief", "items": list(brief.canon_constraints),
                              "source_paths": [item for item in refs if item.startswith("canon/")]},
        "canon_sources": [_entry(root, "canon_source", item, "canon_mixed_source", "full")
                          for item in refs if item.startswith("canon/")],
        "continuity_delivery": "full-source-v2",
        "continuity_contract": (
            "先核对完整Canon来源、前一单元正文及其SceneDelta。Canon文件中的facts、已确认世界规则与"
            "candidates/pending_confirmation须分别判断；已提交正文证明叙述已发生，不证明其中传言为真。"
            "续写应保持既有数量、方位、人物经历与习惯来历；提议改变时说明冲突与依据。"
            "交付札记清点本场持续事实、人物变化与未兑现条件，并逐项覆盖进SceneDelta；无Canon变化时明确理由。"
            "主创写“确认入Canon”不能代替实际审核和应用回执。取材时给伙伴选入所需来源，人物的known/reference边界保持。"
        ),
        "style": scene_creator_style(root, style_sources),
        "source_entries": sources,
        "source_refs": list(refs),
        "archive_tool": "list/search/read work archive for full context",
    }


def _referenced_archive_sources(root: Path, scene_id: str, refs) -> list[dict[str, Any]]:
    sources = []
    for path in dict.fromkeys(refs):
        if path.startswith('characters/'):
            name, status = 'character_source', 'registered_character_source'
        elif path == f'scenes/{scene_id}.yaml':
            name, status = 'current_scene_source', 'scene_definition'
        else:
            continue
        sources.append(_entry(root, name, path, status, 'full'))
    return sources


def _persona_payload(active: dict[str, Any] | None, persona: dict[str, Any]) -> dict[str, Any]:
    if active and persona["status"] == "ready":
        return {"status": "ready", "version": active["version"],
                "text": active["text"], "source_digest": active["source_digest"]}
    return {"status": "missing", "version": 0, "source_digest": persona["source_digest"]}


def scene_creator_style(root: Path, style_sources=()) -> dict[str, Any]:
    mounted_style = active_style_prompt_text(root)
    owner_style = read_owner_style_directive(root)
    return {
        "mounted": {"status": "mounted" if mounted_style else "missing",
                    "content": mounted_style, "complete": True,
                    "source_paths": list(style_sources)},
        "author_directive": {"status": "active" if owner_style["active"] else "missing",
                             "content": str(owner_style["content"]),
                             "revision": owner_style["revision"]},
    }


def _entry(root: Path, name: str, relative: str, status: str, projection: str) -> dict[str, Any]:
    if not relative:
        return {"name": name, "status": "missing", "path": "", "reason": "not referenced"}
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return {"name": name, "status": "missing", "path": relative,
                "reason": "source file is unavailable"}
    raw = path.read_bytes()
    body = raw.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
    try:
        content, complete = _projection(body, projection)
    except (ValueError, TypeError):
        content, complete = body[:2000], len(body) <= 2000
    return {"name": name, "status": status, "path": relative,
            "content": content, "complete": complete,
            "projection": projection if not complete else "full",
            "file_sha256": sha256(raw).hexdigest(),
            "content_sha256": sha256(content.encode('utf-8')).hexdigest()}


def _projection(body: str, kind: str) -> tuple[str, bool]:
    if kind == "full":
        return body, True
    if kind == "tail":
        return body[-2400:], len(body) <= 2400
    if kind == "north_star":
        data = json.loads(body)
        selected = {key: data.get(key) for key in (
            "premise", "central_question", "ending_choice", "narrative_design", "chapters",
        ) if data.get(key)}
        content = json.dumps(selected, ensure_ascii=False)
        return content, len(selected) == len(data)
    if kind == "delta":
        data = json.loads(body)
        selected = {key: data.get(key) for key in (
            "next_handoff", "reader_question_updates", "promise_updates",
            "character_changes", "continuity_changes", "canon_candidates",
        ) if data.get(key)}
        content = json.dumps(selected, ensure_ascii=False)
        return content[:4500], len(content) <= 4500 and len(selected) == len(data)
    data = json.loads(body)
    entries = data.get("entries") if isinstance(data, dict) else None
    selected = {"recent_entries": entries[-8:]} if isinstance(entries, list) else data
    content = json.dumps(selected, ensure_ascii=False)
    return content[:4500], len(content) <= 4500 and (not isinstance(entries, list) or len(entries) <= 8)


__all__ = ["build_scene_creator_briefing", "scene_creator_style"]
