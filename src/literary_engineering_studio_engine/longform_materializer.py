from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .atomic_io import atomic_write_text


MATERIALIZATION_SCHEMA = "literary-engineering-workbench/longform-materialization/v1"


@dataclass(frozen=True)
class LongformMaterializationResult:
    project_root: Path
    manifest_path: Path
    outline_path: Path
    scene_paths: tuple[Path, ...]
    chapter_count: int


def materialize_longform_plan(project_root: Path) -> LongformMaterializationResult:
    root = project_root.expanduser().resolve()
    inventory_path = root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
    obligation_path = root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md"
    expansion_path = root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
    budget_path = root / "plot" / "word_budget" / "word_budget.json"
    required = (inventory_path, obligation_path, expansion_path, budget_path)
    missing = [str(path.relative_to(root)).replace("\\", "/") for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing reviewed longform planning inputs: " + ", ".join(missing))

    inventory_text = inventory_path.read_text(encoding="utf-8", errors="ignore")
    obligation_text = obligation_path.read_text(encoding="utf-8", errors="ignore")
    budget = _read_json(budget_path)
    scenes = _parse_scene_inventory(inventory_text)
    obligations = _parse_chapter_obligations(obligation_text)
    expected_count = int((budget.get("totals") or {}).get("scene_count") or 0)
    if expected_count and len(scenes) != expected_count:
        raise ValueError(f"scene inventory contains {len(scenes)} scenes, expected {expected_count}")

    source_digest = _source_digest(required)
    manifest_path = root / "workflow" / "longform_materialization.json"
    existing = _read_json(manifest_path) if manifest_path.is_file() else {}
    if existing.get("source_digest") == source_digest:
        existing_paths = [root / str(item) for item in existing.get("scene_paths", [])]
        outline = root / str(existing.get("outline_path") or "plot/outline.md")
        if existing_paths and all(path.is_file() for path in existing_paths) and outline.is_file():
            _repair_generated_rhythm_contracts(existing_paths, scenes)
            return LongformMaterializationResult(root, manifest_path, outline, tuple(existing_paths), len(obligations))

    scene_dir = root / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    scene_paths: list[Path] = []
    previous_scene: dict[str, object] | None = None
    for scene in scenes:
        scene_path = scene_dir / f"{scene['scene_id']}.yaml"
        if scene_path.exists() and not _is_blank_scene_scaffold(scene_path):
            raise ValueError(f"refusing to overwrite a non-scaffold formal scene: {scene_path.relative_to(root).as_posix()}")
        chapter = obligations.get(str(scene["chapter_id"]), {})
        atomic_write_text(scene_path, _render_scene_yaml(scene, chapter, previous_scene))
        scene_paths.append(scene_path)
        previous_scene = scene

    outline_path = root / "plot" / "outline.md"
    outline_text = _formal_outline(expansion_path.read_text(encoding="utf-8", errors="ignore"), inventory_text)
    atomic_write_text(outline_path, outline_text)

    manifest = {
        "schema": MATERIALIZATION_SCHEMA,
        "created_at": _now(),
        "source_digest": source_digest,
        "sources": [path.relative_to(root).as_posix() for path in required],
        "outline_path": outline_path.relative_to(root).as_posix(),
        "scene_paths": [path.relative_to(root).as_posix() for path in scene_paths],
        "scene_count": len(scene_paths),
        "chapter_count": len({str(scene["chapter_id"]) for scene in scenes}),
        "status": "materialized",
    }
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return LongformMaterializationResult(
        root,
        manifest_path,
        outline_path,
        tuple(scene_paths),
        int(manifest["chapter_count"]),
    )


def planned_longform_outputs(project_root: Path) -> list[str]:
    root = project_root.expanduser().resolve()
    inventory = root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
    if not inventory.is_file():
        return ["plot/outline.md", "workflow/longform_materialization.json"]
    scenes = _parse_scene_inventory(inventory.read_text(encoding="utf-8", errors="ignore"))
    return [
        "plot/outline.md",
        *[f"scenes/{scene['scene_id']}.yaml" for scene in scenes],
        "workflow/longform_materialization.json",
    ]


def longform_materialization_status(
    project_root: Path,
    *,
    scene_path: Path | str | None = None,
) -> tuple[bool, str]:
    """Validate a materialized longform plan.

    The default validates the entire formal inventory.  A scoped check is
    deliberately narrower: controlled task sandboxes receive one active scene
    plus the trusted materialization manifest, not hundreds of unrelated scene
    files.  It proves that the active scene is registered by that manifest; the
    full-project route gate still performs the complete inventory check.
    """
    root = project_root.expanduser().resolve()
    manifest_path = root / "workflow" / "longform_materialization.json"
    if not manifest_path.is_file():
        return False, "missing workflow/longform_materialization.json"
    payload = _read_json(manifest_path)
    if payload.get("schema") != MATERIALIZATION_SCHEMA or payload.get("status") != "materialized":
        return False, "longform materialization manifest is invalid"
    scene_relatives = [str(item).replace("\\", "/") for item in payload.get("scene_paths", [])]
    scene_paths = [root / item for item in scene_relatives]
    if not scene_paths:
        return False, "longform materialization has no formal scenes"
    if scene_path is not None:
        requested = Path(scene_path)
        if requested.is_absolute():
            try:
                requested_relative = requested.resolve().relative_to(root).as_posix()
            except ValueError:
                return False, "scoped scene is outside the materialization root"
        else:
            requested_relative = requested.as_posix()
        if requested_relative not in scene_relatives:
            return False, f"scoped scene is not registered by longform materialization: {requested_relative}"
        if not (root / requested_relative).is_file():
            return False, f"missing scoped materialized scene: {requested_relative}"
        outline_relative = str(payload.get("outline_path") or "plot/outline.md")
        if not (root / outline_relative).is_file():
            return False, f"missing materialized {outline_relative}"
        return True, f"materialized scoped scene {requested_relative} within {len(scene_paths)} formal scenes"
    missing = [path.relative_to(root).as_posix() for path in scene_paths if not path.is_file()]
    if missing:
        return False, "missing materialized scenes: " + ", ".join(missing[:8])
    if not (root / str(payload.get("outline_path") or "plot/outline.md")).is_file():
        return False, "missing materialized plot/outline.md"
    inventory = root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
    obligation = root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md"
    expansion = root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
    budget = root / "plot" / "word_budget" / "word_budget.json"
    required = (inventory, obligation, expansion, budget)
    if not all(path.is_file() for path in required):
        return False, "reviewed longform planning inputs are missing"
    if payload.get("source_digest") != _source_digest(required):
        return False, "longform planning changed after materialization"
    return True, f"materialized {len(scene_paths)} formal scenes"


def _parse_scene_inventory(text: str) -> list[dict[str, object]]:
    scenes: list[dict[str, object]] = []
    current_volume = "volume_01"
    current_chapter = "chapter_0001"
    current_chapter_title = ""
    for raw in text.splitlines():
        line = raw.strip()
        volume_match = re.match(r"^##\s+卷([一二三四五六七八九十0-9]+)", line)
        if volume_match:
            current_volume = f"volume_{_number(volume_match.group(1)):02d}"
            continue
        chapter_match = re.match(r"^###\s+Ch\s*0*(\d+)\s*[—-]\s*(.*?)\s*(?:\||$)", line, re.IGNORECASE)
        if chapter_match:
            current_chapter = f"chapter_{int(chapter_match.group(1)):04d}"
            current_chapter_title = chapter_match.group(2).strip()
            continue
        if not re.match(r"^\|\s*(?:SC|scene[_-]?)\s*-?0*\d+\s*\|", line, re.IGNORECASE):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 11:
            raise ValueError(f"invalid scene inventory row: {line[:160]}")
        scene_number = _number(cells[0])
        target = _number(cells[2])
        scenes.append(
            {
                "scene_id": f"scene_{scene_number:04d}",
                "source_scene_id": cells[0],
                "name": cells[1],
                "chapter_id": current_chapter,
                "chapter_title": current_chapter_title,
                "volume_id": current_volume,
                "target_chars": target,
                "function": cells[3],
                "participants": _split_people(cells[4]),
                "conflict": cells[5],
                "information_release": cells[6],
                "consequence": cells[7],
                "setup_payoff_role": cells[8],
                "rhythm_role": cells[9],
                "obligation": cells[10],
            }
        )
    if not scenes:
        raise ValueError("scene inventory contains no machine-readable scene rows")
    ids = [str(scene["scene_id"]) for scene in scenes]
    if len(ids) != len(set(ids)):
        raise ValueError("scene inventory contains duplicate scene ids")
    return scenes


def _parse_chapter_obligations(text: str) -> dict[str, dict[str, str]]:
    chapters: dict[str, dict[str, str]] = {}
    current = ""
    labels = {
        "读者进入问题": "reader_question",
        "承诺回报": "promised_reward",
        "暂扣信息": "withheld_information",
        "兑现/延迟": "payoff_or_delay",
        "反摘要要求": "anti_summary_requirement",
        "章末钩子": "chapter_ending_hook",
    }
    for raw in text.splitlines():
        line = raw.strip()
        match = re.match(r"^###\s+Ch\s*0*(\d+)", line, re.IGNORECASE)
        if match:
            current = f"chapter_{int(match.group(1)):04d}"
            chapters.setdefault(current, {})
            continue
        if not current or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] not in labels:
            continue
        chapters[current][labels[cells[0]]] = cells[1]
    return chapters


def _render_scene_yaml(
    scene: dict[str, object],
    chapter: dict[str, str],
    previous_scene: dict[str, object] | None = None,
) -> str:
    target = int(scene["target_chars"])
    lower = max(1, round(target * 0.9))
    upper = max(lower, round(target * 1.1))
    participants = json.dumps(scene["participants"], ensure_ascii=False)
    information = json.dumps([scene["information_release"]] if scene["information_release"] else [], ensure_ascii=False)
    function = str(scene["function"])
    rhythm = _rhythm_role(str(scene["rhythm_role"]), function)
    tension = _tension_curve_for(rhythm)
    incoming_pressure = (
        str(previous_scene.get("consequence") or previous_scene.get("conflict") or "").strip()
        if previous_scene
        else "全书开场：人物原有生活秩序即将被当前事件打破。"
    )
    withheld = _split_items(chapter.get("withheld_information", ""))
    outgoing = [str(scene["consequence"])] if scene["consequence"] else []
    return f'''scene_id: {_yaml(scene["scene_id"])}
chapter_id: {_yaml(scene["chapter_id"])}
chapter_obligation_id: {_yaml(scene["chapter_id"])}
volume_id: {_yaml(scene["volume_id"])}
title: {_yaml(scene["name"])}
status: planned
word_count_target: {target}
word_count_min: {lower}
word_count_max: {upper}

time:
  story_time: ""
  timeline_order: {int(_number(str(scene["scene_id"])))}

location: ""
participants: {participants}
referenced_characters: {participants}
context_policy:
  include_major_characters: true
  include_minor_characters: participants_and_referenced_only

input_state:
  canon_refs: []
  character_states: []
  active_foreshadowing: []

scene_goal: {_yaml(scene["obligation"] or scene["name"])}
conflict:
  external: {_yaml(scene["conflict"])}
  internal: ""

actions: [{_yaml(scene["function"])}]
revealed_info: {information}
emotional_curve: []
style_constraints: []
reader_experience:
  reader_question: {_yaml(chapter.get("reader_question", ""))}
  promised_reward: {_yaml(chapter.get("promised_reward", ""))}
  withheld_information: {json.dumps(withheld, ensure_ascii=False)}
  payoff_or_delay: {_yaml(chapter.get("payoff_or_delay", ""))}
  emotional_curve: []
  tension_source: {_yaml(scene["conflict"])}
  curiosity_hook: {_yaml(scene["setup_payoff_role"])}
  freshness_requirement: {_yaml(scene["information_release"])}
  anti_summary_requirement: {_yaml(chapter.get("anti_summary_requirement", ""))}
  reader_aftertaste: {_yaml(scene["consequence"])}

narrative_rhythm:
  rhythm_role: {_yaml(rhythm)}
  pace: {_yaml(_pace_for(rhythm))}
  density: {_yaml(_density_for(rhythm))}
  scene_function: [{_yaml(function)}]
  scene_turn: {_yaml(scene["consequence"])}
  reader_effect: {_yaml(scene["obligation"])}
  paragraph_shape: "过场简短，关键选择细写；段落推进以行动、信息差和人物选择为主。"
  density_mix:
    summary: low
    action: medium
    dialogue: medium
    reflection: low
    description: low
  dialogue_ratio: medium
  action_ratio: medium
  reflection_ratio: low
  description_ratio: low
  narrative_distance: medium
  tension_curve:
    entry: {tension["entry"]}
    peak: {tension["peak"]}
    exit: {tension["exit"]}
  texture_variety: "避免连续场景采用相同材料组织；按场景功能调整对话、动作、心理、环境与信息揭示。"
  chapter_ending_policy: {_yaml(chapter.get("chapter_ending_hook", ""))}
  slow_down_points: []
  speed_up_points: []
  avoid_flatness: "每段至少承担行动推进、信息改变、关系压力、选择代价或场景衔接之一。"

scene_bridge:
  incoming_pressure: {_yaml(incoming_pressure)}
  incoming_from_previous: []
  reader_questions_carried: {json.dumps([chapter.get("reader_question", "")] if chapter.get("reader_question") else [], ensure_ascii=False)}
  carryover_from_previous: []
  outgoing_hooks: {json.dumps(outgoing, ensure_ascii=False)}
  outgoing_hook: {_yaml(scene["consequence"])}
  promise_payoff_items: {json.dumps([str(scene["setup_payoff_role"])] if scene["setup_payoff_role"] else [], ensure_ascii=False)}
  continuity_handshake: "结尾必须把本场后果转化为下一场可接续的压力、问题、代价或未完成动作。"

output_state:
  new_facts: {information}
  character_changes: []
  relationship_changes: []
  foreshadowing_changes: []
  next_hooks: {json.dumps(outgoing, ensure_ascii=False)}

review:
  canon_test: pending
  character_test: pending
  plot_test: pending
  style_test: pending
'''


def _formal_outline(expansion_text: str, inventory_text: str) -> str:
    cleaned = []
    for line in expansion_text.splitlines():
        stripped = line.strip()
        if "阅读回执" in stripped or "未经审查" in stripped or "候选材料" in stripped:
            continue
        cleaned.append(line)
    body = "\n".join(cleaned).strip()
    if len(body) < 200:
        body = inventory_text.strip()
    return "# 正式长篇大纲\n\n" + body + "\n"


def _is_blank_scene_scaffold(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r'(?m)^scene_id:\s*["\']?\s*["\']?$', text)) and not any(
        (path.parent.parent / rel).exists()
        for rel in (
            f"drafts/scenes/{path.stem}.md",
            f"drafts/candidates/{path.stem}-platform-agent.md",
            f"reviews/agent/{path.stem}_scene_review.json",
        )
    )


def _source_digest(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _split_people(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[、,，/]+", value) if item.strip() and item.strip() not in {"无", "-"}]


def _split_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[；;]+", value) if item.strip()]


def _number(value: str) -> int:
    digits = re.search(r"\d+", value)
    if digits:
        return int(digits.group())
    chinese = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    return chinese.get(value.strip(), 1)


def _rhythm_role(value: str, function: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"setup", "escalation", "climax", "payoff", "aftermath", "bridge", "transition"}:
        return normalized
    if "consequence" in function.lower():
        return "aftermath"
    if "relationship" in function.lower():
        return "bridge"
    return "escalation"


def _pace_for(role: str) -> str:
    return {"setup": "slow_to_medium", "bridge": "balanced", "aftermath": "slow", "climax": "fast_to_slow", "payoff": "slow_to_fast"}.get(role, "fast")


def _density_for(role: str) -> str:
    return "high" if role in {"climax", "payoff", "escalation"} else "medium"


def _tension_curve_for(role: str) -> dict[str, int]:
    return {
        "setup": {"entry": 1, "peak": 3, "exit": 2},
        "bridge": {"entry": 2, "peak": 3, "exit": 2},
        "transition": {"entry": 2, "peak": 3, "exit": 2},
        "escalation": {"entry": 2, "peak": 4, "exit": 3},
        "climax": {"entry": 3, "peak": 5, "exit": 3},
        "payoff": {"entry": 3, "peak": 5, "exit": 2},
        "aftermath": {"entry": 3, "peak": 3, "exit": 1},
    }.get(role, {"entry": 2, "peak": 4, "exit": 3})


def _repair_generated_rhythm_contracts(
    scene_paths: list[Path],
    scenes: list[dict[str, object]],
) -> None:
    """Upgrade only invalid rhythm placeholders emitted by older materializers."""

    metadata = {str(scene.get("scene_id") or ""): scene for scene in scenes}
    previous_scene: dict[str, object] | None = None
    for path in scene_paths:
        scene = metadata.get(path.stem, {})
        text = path.read_text(encoding="utf-8", errors="ignore")
        role = _rhythm_role(str(scene.get("rhythm_role") or ""), str(scene.get("function") or ""))
        curve = _tension_curve_for(role)
        changed = False
        tension_pattern = re.compile(r"(?m)^  tension_curve:\s*([^\n]*)$")
        match = tension_pattern.search(text)
        if match and len(re.findall(r"[1-5]", match.group(1))) < 3:
            replacement = (
                "  tension_curve:\n"
                f"    entry: {curve['entry']}\n"
                f"    peak: {curve['peak']}\n"
                f"    exit: {curve['exit']}"
            )
            text = tension_pattern.sub(replacement, text, count=1)
            changed = True
        incoming = (
            str(previous_scene.get("consequence") or previous_scene.get("conflict") or "").strip()
            if previous_scene
            else "全书开场：人物原有生活秩序即将被当前事件打破。"
        )
        empty_incoming = re.compile(r"(?m)^  incoming_pressure:\s*(?:\"\"|'')\s*$")
        if incoming and empty_incoming.search(text):
            text = empty_incoming.sub(f"  incoming_pressure: {_yaml(incoming)}", text, count=1)
            changed = True
        if changed:
            atomic_write_text(path, text.rstrip() + "\n")
        previous_scene = scene


def _yaml(value: object) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
