"""Compile a traceable, precedence-ordered generation constraint set.

Prompt assembly used to concatenate every available rule.  This small compiler
does not pretend to solve literary judgment; it makes the active constraints,
their source, and obvious precedence suppressions inspectable before prose is
written.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..narrative_rhythm import narrative_rhythm_contract


PRIORITY = ("hard_facts", "scene_causality", "mounted_style", "reader_rhythm_budget", "surface_quality", "revision")


def compile_active_constraints(root: Path, scene_path: Path, *, style_text: str = "", revision_text: str = "") -> dict[str, Any]:
    root = root.resolve()
    scene = scene_path if scene_path.is_absolute() else root / scene_path
    scene_text = _read(scene)
    scene_id = _scalar(scene_text, "scene_id") or scene.stem
    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    rhythm = narrative_rhythm_contract(root, scene, composition if composition.exists() else None)
    entries: list[dict[str, str]] = []
    _append(entries, "hard_facts", "canon", "canon/world_rules.yaml", _read(root / "canon" / "world_rules.yaml"), 2800)
    _append(entries, "hard_facts", "forbidden_changes", "canon/forbidden_changes.yaml", _read(root / "canon" / "forbidden_changes.yaml"), 1600)
    _append(entries, "hard_facts", "scene_contract", _rel(scene, root), scene_text, 3400)
    _append(entries, "scene_causality", "composition", _rel(composition, root), _read(composition), 4800)
    _append(entries, "mounted_style", "style", "style/style_prompt.md", style_text or _read(root / "style" / "style_prompt.md"), 2600)
    _append(entries, "reader_rhythm_budget", "rhythm", "plot/rhythm_plan.json", json.dumps(rhythm, ensure_ascii=False), 2400)
    _append(entries, "reader_rhythm_budget", "budget", "plot/word_budget/word_budget.json", _read(root / "plot" / "word_budget" / "word_budget.json"), 1800)
    _append(entries, "surface_quality", "creative_quality", "style/creative_quality_profile.json", _read(root / "style" / "creative_quality_profile.json"), 1800)
    _append(entries, "revision", "review", f"reviews/agent/{scene_id}_scene_review.json", revision_text or _read(root / "reviews" / "agent" / f"{scene_id}_scene_review.json"), 2000)

    active: list[dict[str, str]] = []
    suppressed: list[dict[str, str]] = []
    seen: dict[str, dict[str, str]] = {}
    for entry in entries:
        normalized = _normalize(entry["text"])
        if not normalized:
            continue
        key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if key in seen:
            suppressed.append({"source": entry["source"], "reason": f"duplicate of {seen[key]['source']}", "text": entry["text"][:240]})
            continue
        seen[key] = entry
        active.append(entry)
    conflicts = _detect_conflicts(active)
    return {
        "schema": "literary-engineering-workbench/prompt-compiler/v1",
        "scene_id": scene_id,
        "priority_order": list(PRIORITY),
        "active_constraints": active,
        "suppressed_constraints": suppressed,
        "conflicts": conflicts,
        "justified_exceptions": [],
        "digest": hashlib.sha256(json.dumps(active, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
    }


def render_compiled_constraints(compiled: dict[str, Any]) -> str:
    lines = [
        "# 已编译创作约束",
        "",
        "以下约束按优先级生效；冲突不得静默忽略。每一项都来自当前项目文件，正文必须服从其内容，而不只是读取标题。",
        "",
    ]
    for entry in compiled.get("active_constraints", []):
        if isinstance(entry, dict):
            lines.extend(
                [
                    f"## [{entry.get('priority')}] {entry.get('kind')}",
                    "",
                    f"来源：`{entry.get('source')}`",
                    "",
                    str(entry.get("text") or "").strip(),
                    "",
                ]
            )
    conflicts = compiled.get("conflicts") if isinstance(compiled.get("conflicts"), list) else []
    lines.extend(["", "## 冲突", ""])
    lines.extend(f"- {item.get('message')}" for item in conflicts if isinstance(item, dict))
    if not conflicts:
        lines.append("- 未检出确定性优先级冲突；仍须在写作中服从 Canon 与人物因果。")
    return "\n".join(lines) + "\n"


def _append(entries: list[dict[str, str]], priority: str, kind: str, source: str, text: str, limit: int) -> None:
    if not text.strip():
        return
    entries.append({"priority": priority, "kind": kind, "source": source, "text": text.strip()[:limit]})


def _detect_conflicts(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    hard = "\n".join(entry["text"] for entry in entries if entry["priority"] == "hard_facts").lower()
    style = "\n".join(entry["text"] for entry in entries if entry["priority"] == "mounted_style").lower()
    conflicts: list[dict[str, str]] = []
    if any(token in hard for token in ("禁止破折号", "do not use em dash")) and any(token in style for token in ("高破折号", "大量破折号", "em dash heavy")):
        conflicts.append({"severity": "warning", "message": "Mounted style requests frequent dashes while a higher-priority hard rule forbids them; use sentence rhythm instead and record any exception."})
    if "第一人称" in hard and "全知" in style:
        conflicts.append({"severity": "warning", "message": "Narrative-person conflict: canon/scene first-person constraint overrides style request for omniscience."})
    return conflicts


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""


def _scalar(text: str, key: str) -> str:
    import re
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*['\"]?([^'\"\n#]+)", text)
    return match.group(1).strip().strip("'\"") if match else ""


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
