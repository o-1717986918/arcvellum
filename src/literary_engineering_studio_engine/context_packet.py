from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from .context_broker import default_context_trace_path, write_context_trace
from .memory_index import build_memory_index, search_memory
from .word_budget import render_scene_word_budget_contract


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
            f"### {i}. {hit.source} (score={hit.score:.1f}, kind={hit.kind})\n\n{text}"
        )
    return "\n\n".join(sections)


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
    word_budget_contract = render_scene_word_budget_contract(root, scene_path)
    retrieval_query = _query_from_scene(scene_text, query)
    raw_hits = search_memory(root, retrieval_query, top_k=top_k)
    character_text, loaded_character_ids, restrict_character_hits = _character_section(root, scene_text)
    hits = _filter_retrieval_hits(raw_hits, loaded_character_ids, restrict_character_hits)

    scene_id = _extract_scene_id(scene_path)
    output_path = output or root / "memory" / "context_packets" / f"{scene_id}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# 场景上下文包：{scene_id}

生成时间：{datetime.now(timezone.utc).isoformat()}

## 使用规则

- 本文件是写作前工作记忆，不是正稿。
- Canon、人物档案和时间线是硬约束。
- “软记忆检索”只提供参考，不得覆盖硬事实。
- `background_story` 是人物的隐性行为因果，只能影响选择、回避、误判和语气，不应在正文中直白说明。
- 写作完成后必须输出写回计划。

## 项目配置

```yaml
{_read(root / "project.yaml")}
```

## 当前场景

来源：`{scene_path.relative_to(root).as_posix()}`

```yaml
{scene_text}
```

## 场景字数预算

{word_budget_contract}

## 硬约束：Canon 与时间线

{_first_existing(root, [
    "canon/world_rules.yaml",
    "canon/timeline.yaml",
    "canon/facts.json",
    "canon/forbidden_changes.yaml",
])}

## 人物状态

{character_text}

## 剧情状态

{_first_existing(root, [
    "plot/outline.md",
    "plot/foreshadowing.csv",
    "plot/conflict_matrix.md",
])}

## 风格约束

{_first_existing(root, [
    "style/style-profile.md",
])}

## 软记忆检索

查询依据：当前场景字段 + 用户补充 query。

{_retrieval_section(hits)}

## 写作任务

请基于以上上下文生成或推演当前场景。生成时必须：

1. 不违背硬 canon。
2. 人物行动符合 BDI 和当前信息差。
3. 人物背景故事只能作为隐性动因，不得变成解释性设定段落。
4. 场景输出必须包含状态变化。
5. 正文清洗后的可交付部分必须遵守“场景字数预算”的目标、上下限和叙事负载；不得用流程痕迹、状态候选、canon 说明或空泛重复填字数。
6. 风格遵守 profile，而不是只模仿表面词汇。
7. 若需要新增事实，写入候选，不直接确认为 canon。

## 写回清单

生成完成后输出：

- 新增事实候选。
- 人物状态变化。
- 关系变化。
- 伏笔变化。
- 需要进入软记忆索引的正文片段。
- 需要人工确认的重大变更。
"""

    output_path.write_text(content, encoding="utf-8")
    trace_path = trace_output or default_context_trace_path(output_path)
    write_context_trace(
        trace_path,
        _context_trace_payload(
            root=root,
            scene_path=scene_path,
            scene_id=scene_id,
            context_path=output_path,
            top_k=top_k,
            query=query,
            content=content,
            hits=hits,
            loaded_character_ids=loaded_character_ids,
        ),
    )
    return ContextPacketResult(project_root=root, output_path=output_path, retrieval_count=len(hits), trace_path=trace_path)


def _context_trace_payload(
    *,
    root: Path,
    scene_path: Path,
    scene_id: str,
    context_path: Path,
    top_k: int,
    query: str,
    content: str,
    hits,
    loaded_character_ids: set[str],
) -> dict[str, object]:
    project_files = _existing_rel_paths(root, ["project.yaml"])
    canon_files = _existing_rel_paths(
        root,
        [
            "canon/world_rules.yaml",
            "canon/timeline.yaml",
            "canon/facts.json",
            "canon/forbidden_changes.yaml",
        ],
    )
    plot_files = _existing_rel_paths(
        root,
        [
            "plot/outline.md",
            "plot/foreshadowing.csv",
            "plot/conflict_matrix.md",
        ],
    )
    style_files = _existing_rel_paths(root, ["style/style-profile.md", "style/style_prompt.md", "style/active_style_skill.json"])
    style_files.extend(_mounted_style_prompt_paths(root))
    word_budget_files = _existing_rel_paths(root, ["plot/word_budget/word_budget.json", "plot/word_budget/word_budget.md"])
    character_files = _loaded_character_paths(root, loaded_character_ids)
    excluded_character_files = _excluded_character_paths(root, loaded_character_ids)
    scene_rel = _rel(scene_path, root)
    summarized_files = sorted({str(getattr(hit, "source", "")) for hit in hits if str(getattr(hit, "source", "")).strip()})
    loaded_files = sorted(
        {
            *project_files,
            scene_rel,
            *canon_files,
            *plot_files,
            *style_files,
            *word_budget_files,
            *character_files,
            *summarized_files,
        }
    )
    groups = [
        _context_group("project", True, project_files, "project.yaml anchors title, genre, target length, and provider-neutral project rules."),
        _context_group("scene", True, [scene_rel] if scene_path.exists() else [], "Current scene YAML is the formal scene contract."),
        _context_group("canon", False, canon_files, "Canon files are hard constraints when present."),
        _context_group("characters", False, character_files, "Major characters plus scene-referenced secondary/cameo files."),
        _context_group("plot", False, plot_files, "Approved or working outline, foreshadowing, and conflict scaffolds."),
        _context_group("style", False, style_files, "Mounted Style Skill or project style profile."),
        _context_group("word_budget", False, word_budget_files, "Longform target-length and scene-budget evidence."),
        _context_group("retrieval", False, summarized_files, "Soft memory retrieval; never overrides hard canon."),
    ]
    missing_required = [str(group["name"]) for group in groups if group["required"] and not group["loaded"]]
    return {
        "route": "scene-development",
        "scene_id": scene_id,
        "context_packet": _rel(context_path, root),
        "scene_file": scene_rel,
        "required_context_groups": groups,
        "loaded_files": loaded_files,
        "summarized_files": summarized_files,
        "excluded_files": excluded_character_files,
        "style_mounts": style_files,
        "word_budget_source": word_budget_files[0] if word_budget_files else "",
        "character_files": character_files,
        "canon_files": canon_files,
        "previous_scene_tail": "",
        "token_or_length_budget": {
            "top_k": top_k,
            "query": query,
            "retrieval_count": len(hits),
            "context_chars": len(content),
        },
        "missing_required_context": missing_required,
    }


def _context_group(name: str, required: bool, files: list[str], notes: str) -> dict[str, object]:
    return {
        "name": name,
        "required": required,
        "loaded": bool(files),
        "files": sorted(dict.fromkeys(files)),
        "notes": notes,
    }


def _existing_rel_paths(root: Path, rels: list[str]) -> list[str]:
    existing: list[str] = []
    for rel in rels:
        path = root / rel
        if path.exists() and (path.is_dir() or _read(path)):
            existing.append(rel)
    return existing


def _mounted_style_prompt_paths(root: Path) -> list[str]:
    active = root / "style" / "active_style_skill.json"
    if not active.exists():
        return []
    text = _read(active)
    paths: list[str] = []
    for key in ("prompt", "style_skill", "mount_path"):
        match = re.search(rf'"?{re.escape(key)}"?\s*[:=]\s*["\']?([^"\'\n,}}]+)', text)
        if not match:
            continue
        value = match.group(1).strip()
        if not value:
            continue
        candidate = root / value
        if candidate.is_dir():
            for name in ("prompt.md", "STYLE.md", "style_skill.json"):
                item = candidate / name
                if item.exists():
                    paths.append(_rel(item, root))
        elif candidate.exists():
            paths.append(_rel(candidate, root))
    return sorted(dict.fromkeys(paths))


def _loaded_character_paths(root: Path, loaded_character_ids: set[str]) -> list[str]:
    paths: list[str] = []
    for character_id in sorted(loaded_character_ids):
        for suffix in (".yaml", ".yml"):
            path = root / "characters" / f"{character_id}{suffix}"
            if path.exists():
                paths.append(_rel(path, root))
                break
    return paths


def _excluded_character_paths(root: Path, loaded_character_ids: set[str]) -> list[str]:
    chars_dir = root / "characters"
    if not chars_dir.exists():
        return []
    excluded: list[str] = []
    for path in sorted(chars_dir.glob("*.y*ml")):
        if path.name.startswith("_"):
            continue
        if path.stem not in loaded_character_ids:
            excluded.append(_rel(path, root))
    return excluded


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")
