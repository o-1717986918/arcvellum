from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from ....context_broker import default_context_trace_path, write_context_trace
from ....memory_index import SearchHit, build_memory_index, search_memory
from ....scene_handoff import scene_handoff_status
from ....word_budget import render_scene_word_budget_contract
from .rendering import (
    ContextPacketSections,
    render_context_packet,
    render_handoff,
)
from .trace import build_context_trace_payload, relative_path


@dataclass(frozen=True)
class ContextPacketResult:
    project_root: Path
    output_path: Path
    retrieval_count: int
    trace_path: Path | None = None


def _read(path: Path, missing: str = "") -> str:
    if not path.exists():
        return missing
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _first_existing(root: Path, candidates: list[str]) -> str:
    parts = []
    for rel in candidates:
        text = _read(root / rel)
        if text:
            parts.append(f"### {rel}\n\n{text}")
    return "\n\n".join(parts) if parts else "无。"


def _extract_scene_id(scene_path: Path) -> str:
    stem = scene_path.stem
    return stem or "scene"


def _query_from_scene(scene_text: str, extra_query: str) -> str:
    keys = []
    for key in [
        "scene_goal",
        "external",
        "internal",
        "location",
        "participants",
        "style_constraints",
    ]:
        pattern = rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$"
        match = re.search(pattern, scene_text)
        if match and match.group(1).strip() not in {"", "[]"}:
            keys.append(match.group(1).strip())
    if extra_query:
        keys.append(extra_query)
    keys.append(scene_text[:1200])
    return "\n".join(keys)


def _list_value(text: str, key: str) -> list[str]:
    inline = re.search(rf"(?m)^\s*{re.escape(key)}:\s*\[(.*?)\]\s*$", text)
    if inline:
        return [item.strip().strip("'\"") for item in inline.group(1).split(",") if item.strip()]
    lines = text.splitlines()
    values: list[str] = []
    in_block = False
    base_indent = 0
    for line in lines:
        if re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            in_block = True
            base_indent = len(line) - len(line.lstrip())
            continue
        if not in_block:
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped and indent <= base_indent and not stripped.startswith("-"):
            break
        if stripped.startswith("-"):
            value = stripped[1:].strip().strip("'\"")
            if value:
                values.append(value)
    scalar = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$", text)
    if not values and scalar and scalar.group(1).strip() not in {"", "[]"}:
        values.append(scalar.group(1).strip().strip("'\""))
    return values


def _scene_character_refs(scene_text: str) -> set[str]:
    refs: set[str] = set()
    for key in ("participants", "referenced_characters", "character_refs"):
        refs.update(_list_value(scene_text, key))
    return {item for item in refs if item}


def scene_character_refs(scene_text: str) -> set[str]:
    """Return the character references declared by one scene contract."""

    return _scene_character_refs(scene_text)


def _field_value(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$", text)
    if not match:
        return ""
    return match.group(1).strip().strip("'\"")


def _character_aliases(path: Path, text: str) -> set[str]:
    aliases = {path.stem}
    for key in ("character_id", "name"):
        value = _field_value(text, key)
        if value:
            aliases.add(value)
    return aliases


def _is_major_character(text: str) -> bool:
    role = _field_value(text, "role").lower()
    importance = _field_value(text, "importance").lower()
    combined = f"{role} {importance}"
    return any(marker in combined for marker in ("主角", "主要", "核心", "major", "main", "core", "protagonist"))


def _filter_retrieval_hits(hits, allowed_character_ids: set[str], restrict_characters: bool):
    if not restrict_characters:
        return hits
    filtered = []
    for hit in hits:
        source = str(hit.source)
        if not source.startswith("characters/") or not source.endswith((".yaml", ".yml")):
            filtered.append(hit)
            continue
        stem = Path(source).stem
        if stem.startswith("_") or stem in allowed_character_ids:
            filtered.append(hit)
    return filtered


def _character_section(root: Path, scene_text: str) -> tuple[str, set[str], bool]:
    chars_dir = root / "characters"
    if not chars_dir.exists():
        return "无人物档案。", set(), False
    files = [p for p in sorted(chars_dir.glob("*.yaml")) if not p.name.startswith("_")]
    if not files:
        template = _read(chars_dir / "_template.yaml")
        return "尚无正式人物档案。以下是人物模板，生成前应先补齐主要人物：\n\n```yaml\n" + template + "\n```", set(), False

    scene_refs = _scene_character_refs(scene_text)
    restrict_characters = bool(scene_refs)
    major_sections = []
    scene_sections = []
    omitted = []
    loaded_ids: set[str] = set()
    for path in files:
        text = _read(path)
        aliases = _character_aliases(path, text)
        is_major = _is_major_character(text)
        in_scene = bool(scene_refs & aliases)
        if not restrict_characters:
            major_sections.append(f"### {path.name}\n\n```yaml\n{text}\n```")
            loaded_ids.add(path.stem)
        elif is_major:
            major_sections.append(f"### {path.name}（主要角色常驻）\n\n```yaml\n{text}\n```")
            loaded_ids.add(path.stem)
        elif in_scene:
            scene_sections.append(f"### {path.name}（本场景参与/引用）\n\n```yaml\n{text}\n```")
            loaded_ids.add(path.stem)
        else:
            omitted.append(path.stem)

    parts = [
        "### 加载策略",
        "",
        "- 主要角色（`role`/`importance` 标记为主角、主要、核心、major/main/core/protagonist）默认作为长篇连续性硬约束载入。",
        "- 次要角色只在当前场景 `participants`、`referenced_characters` 或 `character_refs` 中出现时完整载入。",
        "- 未载入的次要角色仍可通过软记忆检索补充，但不能覆盖已载入硬人物档案。",
        f"- 当前场景角色引用：{', '.join(sorted(scene_refs)) if scene_refs else '未填写，临时载入全部正式人物以避免漏约束。'}",
    ]
    if major_sections:
        parts.extend(["", "### 主要角色常驻档案", "", "\n\n".join(major_sections)])
    if scene_sections:
        parts.extend(["", "### 本场景涉及次要角色档案", "", "\n\n".join(scene_sections)])
    if omitted:
        parts.extend(["", "### 本场景省略的次要角色", "", "- " + "\n- ".join(sorted(omitted))])
    if not major_sections and not scene_sections:
        parts.extend(["", "### 已载入人物档案", "", "未匹配到当前场景参与者。请补齐 `participants` 或人物 `character_id/name`。"])
    return "\n".join(parts), loaded_ids, restrict_characters


def _retrieval_section(hits) -> str:
    if not hits:
        return "未检索到相关软记忆。"
    sections = []
    for i, hit in enumerate(hits, 1):
        text = hit.text
        if len(text) > 900:
            text = text[:900] + "\n..."
        sections.append(
            f"### {i}. {hit.source} (score={hit.score:.1f}, kind={hit.kind}, tier={hit.trust_tier})\n\n{text}"
        )
    return "\n\n".join(sections)


def _plot_context(root: Path, scene_text: str) -> str:
    outline_path = root / "plot" / "outline.md"
    outline = _read(outline_path)
    supplemental = _first_existing(root, ["plot/foreshadowing.csv", "plot/conflict_matrix.md"])
    if not outline:
        return supplemental

    chapter_value = _field_value(scene_text, "chapter_id") or _field_value(scene_text, "chapter_obligation_id")
    chapter_match = re.search(r"(\d+)", chapter_value)
    chapter_number = int(chapter_match.group(1)) if chapter_match else 1
    headings = list(re.finditer(r"(?m)^###\s+Ch\s*0*(\d+)\b.*$", outline, re.IGNORECASE))
    current_index = next(
        (index for index, match in enumerate(headings) if int(match.group(1)) == chapter_number),
        None,
    )
    if current_index is None:
        return outline[:12000] + ("\n..." if len(outline) > 12000 else "") + "\n\n" + supplemental

    first_chapter = headings[0].start()
    preamble = outline[:first_chapter].strip()
    current_start = headings[current_index].start()
    volume_start = outline.rfind("\n## 卷", 0, current_start)
    volume_intro = ""
    if volume_start >= 0:
        volume_heading_end = outline.find("\n### ", volume_start)
        if volume_heading_end > volume_start:
            volume_intro = outline[volume_start:volume_heading_end].strip()

    chapter_sections: list[str] = []
    for index in range(max(0, current_index - 1), min(len(headings), current_index + 2)):
        start = headings[index].start()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(outline)
        chapter_sections.append(outline[start:end].strip())
    selected = "\n\n".join(part for part in [preamble, volume_intro, *chapter_sections] if part)
    if len(selected) > 16000:
        selected = selected[:16000] + "\n..."
    return selected + "\n\n" + supplemental


def build_context_packet(
    project_root: Path,
    scene: Path | None = None,
    query: str = "",
    top_k: int = 8,
    rebuild_index: bool = False,
    output: Path | None = None,
    trace_output: Path | None = None,
) -> ContextPacketResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = (root / "scenes" / "scene_0001.yaml") if scene is None else (scene if scene.is_absolute() else root / scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")

    index_path = root / "memory" / "index.json"
    if rebuild_index or not index_path.exists():
        build_memory_index(root)

    scene_text = _read(scene_path)
    # This packet belongs to one active scene. Full-book inventory may still
    # report ``needs_expansion`` after that scene has been materialized; using
    # the full scope here injected a stale failure into a valid prose prompt.
    word_budget_contract = render_scene_word_budget_contract(
        root,
        scene_path,
        materialization_scope="scene",
    )
    retrieval_query = _query_from_scene(scene_text, query)
    raw_hits = search_memory(root, retrieval_query, top_k=top_k)
    character_text, loaded_character_ids, restrict_character_hits = _character_section(root, scene_text)
    hits = _filter_retrieval_hits(raw_hits, loaded_character_ids, restrict_character_hits)

    scene_id = _extract_scene_id(scene_path)
    handoff_ok, handoff_message, handoff_payload = scene_handoff_status(root, scene_id)
    output_path = output or root / "memory" / "context_packets" / f"{scene_id}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = render_context_packet(
        _packet_sections(
            root=root,
            scene_path=scene_path,
            scene_id=scene_id,
            scene_text=scene_text,
            word_budget=word_budget_contract,
            character_text=character_text,
            hits=hits,
            handoff_ok=handoff_ok,
            handoff_message=handoff_message,
            handoff_payload=handoff_payload,
        )
    )

    output_path.write_text(content, encoding="utf-8")
    trace_path = trace_output or default_context_trace_path(output_path)
    write_context_trace(
        trace_path,
        build_context_trace_payload(
            root=root,
            scene_path=scene_path,
            scene_id=scene_id,
            context_path=output_path,
            top_k=top_k,
            query=query,
            content=content,
            hits=hits,
            loaded_character_ids=loaded_character_ids,
            character_context_required=bool(_scene_character_refs(scene_text)),
            handoff_ok=handoff_ok,
            handoff_message=handoff_message,
            handoff_payload=handoff_payload,
        ),
    )
    return ContextPacketResult(project_root=root, output_path=output_path, retrieval_count=len(hits), trace_path=trace_path)


def _packet_sections(
    *,
    root: Path,
    scene_path: Path,
    scene_id: str,
    scene_text: str,
    word_budget: str,
    character_text: str,
    hits: list[SearchHit],
    handoff_ok: bool,
    handoff_message: str,
    handoff_payload: dict[str, object],
) -> ContextPacketSections:
    return ContextPacketSections(
        scene_id=scene_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_config=_read(root / "project.yaml"),
        scene_relative=relative_path(scene_path, root),
        scene_text=scene_text,
        word_budget=word_budget,
        canon=_first_existing(
            root,
            [
                "canon/world_rules.yaml",
                "canon/timeline.yaml",
                "canon/facts.json",
                "canon/forbidden_changes.yaml",
                "canon/locations.yaml",
                "canon/organizations.yaml",
            ],
        ),
        characters=character_text,
        plot=_plot_context(root, scene_text),
        handoff=render_handoff(
            passed=handoff_ok,
            message=handoff_message,
            payload=handoff_payload,
        ),
        style=_first_existing(root, ["style/style-profile.md"]),
        retrieval=_retrieval_section(hits),
    )
