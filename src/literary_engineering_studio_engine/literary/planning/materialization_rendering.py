"""Formal scene-contract rendering for reviewed longform plans."""

from __future__ import annotations

import json
from pathlib import Path
import re

from literary_engineering_studio_engine.foundation.atomic_io import atomic_write_text
from .lean_plan import normalize_rhythm_role
from .materialization_parser import number


_SCENE_TEMPLATE = '''scene_id: {scene_id}
chapter_id: {chapter_id}
chapter_obligation_id: {chapter_id}
volume_id: {volume_id}
title: {title}
narrative_strategy: {narrative_strategy}
chapter_literary_task: {chapter_literary_task}
status: planned
word_count_target: {target}
word_count_min: {lower}
word_count_max: {upper}

time:
  story_time: {story_time}
  timeline_order: {timeline_order}

location: ""
participants: {participants}
referenced_characters: {participants}
context_policy:
  include_major_characters: {include_major_characters}
  include_minor_characters: participants_and_referenced_only

input_state:
  canon_refs: []
  character_states: []
  active_foreshadowing: []

scene_goal: {scene_goal}
conflict:
  external: {conflict}
  internal: ""

actions: [{function}]
revealed_info: {information}
emotional_curve: []
style_constraints: []
reader_experience:
  reader_question: {reader_question}
  promised_reward: {promised_reward}
  withheld_information: {withheld}
  payoff_or_delay: {payoff_or_delay}
  emotional_curve: []
  tension_source: {conflict}
  curiosity_hook: {setup_payoff_role}
  freshness_requirement: {information_release}
  anti_summary_requirement: {anti_summary_requirement}
  reader_aftertaste: {consequence}

narrative_rhythm:
  rhythm_role: {rhythm}
  pace: {pace}
  density: {density}
  scene_function: [{function}]
  scene_turn: {consequence}
  reader_effect: {obligation}
  paragraph_shape: {paragraph_shape}
  density_mix: {{}}
  narrative_distance: "由本段文学任务与叙述声音选择"
{tension_curve}
  texture_variety: "按章节文学任务选择世界、风俗、思想、情感、群体、现场与时间的组织。"
  chapter_ending_policy: {chapter_ending_hook}
  slow_down_points: []
  speed_up_points: []
  avoid_flatness: "发展本段值得读者经历的趣味、认识、情感与语言。"

scene_bridge:
  incoming_pressure: {incoming_pressure}
  incoming_from_previous: []
  reader_questions_carried: {reader_questions}
  carryover_from_previous: []
  outgoing_hooks: {outgoing}
  outgoing_hook: {consequence}
  promise_payoff_items: {promise_payoff}
  continuity_handshake: "依据本段叙述方式记录后续可接续的事实、时间、认识、经验与余味。"

output_state:
  new_facts: {information}
  character_changes: []
  relationship_changes: []
  foreshadowing_changes: []
  next_hooks: {outgoing}

review:
  canon_test: pending
  character_test: pending
  plot_test: pending
  style_test: pending
'''


def render_scene_yaml(
    scene: dict[str, object],
    chapter: dict[str, str],
    previous_scene: dict[str, object] | None = None,
) -> str:
    target = int(scene["target_chars"])
    rhythm = rhythm_role(str(scene["rhythm_role"]), str(scene["function"]))
    tension = tension_curve_for(rhythm)
    consequence = str(scene["consequence"] or "")
    information = [scene["information_release"]] if scene["information_release"] else []
    incoming = (
        str(previous_scene.get("consequence") or previous_scene.get("conflict") or "").strip()
        if previous_scene
        else "全书开场：按作品方向建立读者进入这部作品的经验。"
    )
    values = {
        "scene_id": yaml_text(scene["scene_id"]),
        "chapter_id": yaml_text(scene["chapter_id"]),
        "volume_id": yaml_text(scene["volume_id"]),
        "title": yaml_text(scene["name"]),
        "narrative_strategy": yaml_text(scene.get("narrative_strategy", "")),
        "paragraph_shape": yaml_text(scene.get("narrative_strategy") or "按本段文学任务选择段落、时间尺度与叙述声音"),
        "chapter_literary_task": yaml_text(chapter.get("literary_task", "")),
        "target": target,
        "lower": max(1, round(target * 0.9)),
        "upper": max(1, round(target * 1.1)),
        "timeline_order": int(number(str(scene["scene_id"]))),
        "story_time": yaml_text(scene.get("story_time", "")),
        "participants": json.dumps(scene["participants"], ensure_ascii=False),
        "include_major_characters": "true" if scene["participants"] else "false",
        "scene_goal": yaml_text(scene["obligation"] or scene["name"]),
        "conflict": yaml_text(scene["conflict"]),
        "function": yaml_text(scene["function"]),
        "information": json.dumps(information, ensure_ascii=False),
        "reader_question": yaml_text(chapter.get("reader_question", "")),
        # Chapter promises remain visible through chapter_ending_policy and the
        # obligation asset.  The per-scene reader contract must describe only
        # the event assigned to this scene; copying the whole chapter payoff
        # here lets an earlier scene consume a later scene's unique turn.
        "promised_reward": yaml_text(scene.get("obligation", "")),
        "withheld": json.dumps(_split_items(chapter.get("withheld_information", "")), ensure_ascii=False),
        "payoff_or_delay": yaml_text(
            scene.get("consequence") or scene.get("setup_payoff_role", "")
        ),
        "setup_payoff_role": yaml_text(scene["setup_payoff_role"]),
        "information_release": yaml_text(scene["information_release"]),
        "anti_summary_requirement": yaml_text(chapter.get("anti_summary_requirement", "")),
        "consequence": yaml_text(consequence),
        "rhythm": yaml_text(rhythm),
        "pace": yaml_text("按本段叙述策略选择" if scene.get("narrative_strategy") else pace_for(rhythm)),
        "density": yaml_text("按本段文学任务选择" if scene.get("narrative_strategy") else density_for(rhythm)),
        "obligation": yaml_text(scene["obligation"]),
        "tension_curve": _render_rhythm_strategy(scene, tension),
        "tension_entry": tension["entry"],
        "tension_peak": tension["peak"],
        "tension_exit": tension["exit"],
        "chapter_ending_hook": yaml_text(chapter.get("chapter_ending_hook", "")),
        "incoming_pressure": yaml_text(incoming),
        "reader_questions": json.dumps([chapter["reader_question"]] if chapter.get("reader_question") else [], ensure_ascii=False),
        "outgoing": json.dumps([consequence] if consequence else [], ensure_ascii=False),
        "promise_payoff": json.dumps([str(scene["setup_payoff_role"])] if scene["setup_payoff_role"] else [], ensure_ascii=False),
    }
    values["upper"] = max(int(values["lower"]), int(values["upper"]))
    return _SCENE_TEMPLATE.format(**values)


def repair_generated_rhythm_contracts(
    scene_paths: list[Path],
    scenes: list[dict[str, object]],
) -> None:
    metadata = {str(scene.get("scene_id") or ""): scene for scene in scenes}
    previous: dict[str, object] | None = None
    for path in scene_paths:
        scene = metadata.get(path.stem, {})
        text = path.read_text(encoding="utf-8", errors="ignore")
        role = rhythm_role(
            str(scene.get("rhythm_role") or ""), str(scene.get("function") or "")
        )
        text, changed = (text, False) if scene.get("narrative_strategy") else _repair_tension(text, tension_curve_for(role))
        incoming = (
            str(previous.get("consequence") or previous.get("conflict") or "").strip()
            if previous
            else "全书开场：按文学任务建立读者进入作品的经验。"
        )
        text, bridge_changed = _repair_incoming(text, incoming)
        if changed or bridge_changed:
            atomic_write_text(path, text.rstrip() + "\n")
        previous = scene


def rhythm_role(value: str, function: str) -> str:
    return normalize_rhythm_role(value, function)


def pace_for(role: str) -> str:
    return {
        "setup": "slow_to_medium",
        "bridge": "balanced",
        "aftermath": "slow",
        "climax": "fast_to_slow",
        "payoff": "slow_to_fast",
    }.get(role, "fast")


def density_for(role: str) -> str:
    return "high" if role in {"climax", "payoff", "escalation"} else "medium"


def tension_curve_for(role: str) -> dict[str, int]:
    return {
        "setup": {"entry": 1, "peak": 3, "exit": 2},
        "bridge": {"entry": 2, "peak": 3, "exit": 2},
        "transition": {"entry": 2, "peak": 3, "exit": 2},
        "escalation": {"entry": 2, "peak": 4, "exit": 3},
        "climax": {"entry": 3, "peak": 5, "exit": 3},
        "payoff": {"entry": 3, "peak": 5, "exit": 2},
        "aftermath": {"entry": 3, "peak": 3, "exit": 1},
    }.get(role, {"entry": 2, "peak": 4, "exit": 3})


def yaml_text(value: object) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def _repair_tension(text: str, curve: dict[str, int]) -> tuple[str, bool]:
    pattern = re.compile(r"(?m)^  tension_curve:\s*([^\n]*)$")
    match = pattern.search(text)
    if not match or len(re.findall(r"[1-5]", match.group(1))) >= 3:
        return text, False
    replacement = (
        "  tension_curve:\n"
        f"    entry: {curve['entry']}\n"
        f"    peak: {curve['peak']}\n"
        f"    exit: {curve['exit']}"
    )
    return pattern.sub(replacement, text, count=1), True


def _repair_incoming(text: str, incoming: str) -> tuple[str, bool]:
    pattern = re.compile(r"(?m)^  incoming_pressure:\s*(?:\"\"|'')\s*$")
    if not incoming or not pattern.search(text):
        return text, False
    return pattern.sub(f"  incoming_pressure: {yaml_text(incoming)}", text, count=1), True


def _split_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[；;]+", value) if item.strip()]


__all__ = ["render_scene_yaml", "repair_generated_rhythm_contracts"]


def _render_rhythm_strategy(scene, tension):
    if scene.get("narrative_strategy"):
        return "  tension_curve: " + json.dumps({"mode": "literary", "strategy": scene["narrative_strategy"]}, ensure_ascii=False)
    return "  tension_curve:\n" + "\n".join(f"    {key}: {value}" for key, value in tension.items())
