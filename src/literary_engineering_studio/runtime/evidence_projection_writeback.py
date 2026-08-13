"""Compact scene, state, continuity, and Canon writeback evidence."""

from __future__ import annotations

from io import StringIO
import json
import re

from ruamel.yaml import YAML

from .evidence_projection_common import positive_int


def continuity_prose(body: str) -> str:
    from literary_engineering_studio_engine.foundation.draft_text import (
        final_body_from_workbench_text,
    )

    return final_body_from_workbench_text(body)


def continuity_scene(value: object) -> object:
    return _select(
        value,
        "scene_id", "chapter_id", "scene_function", "reader_experience",
        "narrative_rhythm", "scene_bridge", "incoming_from_previous", "outgoing_hooks",
    )


def state_patch(value: object) -> object:
    if not isinstance(value, dict):
        return value
    characters = [
        _select(
            item,
            "character_id", "name", "file", "current_state", "proposed_updates", "confidence",
        )
        for item in value.get("characters", [])
        if isinstance(item, dict)
    ]
    return _select(
        value,
        "schema", "scene_id", "scene", "source_artifact", "status",
        "unresolved_changes", "source_changes", "source_change_sources", "new_character_policy",
    ) | {"characters": characters}


def state_composition(value: object) -> object:
    return _select(
        value, "schema", "scene_id", "selected_branch", "writeback_candidates", "scene_bridge"
    )


def state_character(value: object) -> object:
    if not isinstance(value, dict):
        return value
    background = _select(
        value.get("background_story"), "summary", "behavior_influences", "reveal_policy"
    )
    psychology = _select(value.get("psychology"), "fear", "moral_line")
    return _select(
        value,
        "character_id", "name", "aliases", "role", "importance", "bdi", "state", "arc", "relationships",
    ) | {"background_story": background, "psychology": psychology}


def state_scene(value: object) -> object:
    return _select(
        value,
        "scene_id", "chapter_id", "title", "participants", "referenced_characters",
        "scene_goal", "conflict", "actions", "revealed_info", "scene_bridge", "output_state",
    )


def canon_scene_review(value: object) -> object:
    return _select(
        value,
        "schema", "scene_id", "candidate", "candidate_sha256", "conclusion", "summary",
        "canon_writeback", "canon_violations", "blocking_issues", "revision_actions",
    )


def prose_composition(value: object) -> object:
    if not isinstance(value, dict):
        return value
    reader = _select(
        value.get("reader_experience_contract"), "status", "required", "reader_experience", "issues"
    )
    prose = _select(
        value.get("prose_execution_contract"), "status", "errors", "input_contract_digest"
    )
    return _select(
        value,
        "schema", "scene_id", "selected_branch", "scene_facts", "characters", "beats",
        "composition_obligations", "subtext_map", "dialogue_intents", "sensory_palette",
        "narrative_rhythm", "scene_bridge",
    ) | {
        "word_budget_contract": scene_word_budget(value.get("word_budget_contract")),
        "reader_experience_contract": reader,
        "prose_execution_contract": prose,
    }


def composition_review(value: object) -> object:
    if not isinstance(value, dict):
        return value
    compact = prose_composition(value)
    if not isinstance(compact, dict):
        return compact
    return _select(
        value,
        "schema", "scene_id", "formal_cli_provenance", "branch_manifest", "branch_selection",
        "selected_branch", "selection_source", "flow_gate", "branch", "revision_targets",
        "guardrails", "creative_quality_profile_digest",
    ) | compact


def scene_word_budget(value: object) -> object:
    if not isinstance(value, dict):
        return value
    result = _select(
        value,
        "schema", "scene_id", "chapter_id", "count_unit", "scene_yaml_target_chinese_chars",
        "derived_target_chinese_chars", "tolerance", "narrative_load",
    )
    target = positive_int(value.get("target_chinese_chars")) or positive_int(
        value.get("scene_yaml_target_chinese_chars")
    )
    for key, number in (
        ("target_chinese_chars", target),
        ("min_chinese_chars", positive_int(value.get("min_chinese_chars"))),
        ("max_chinese_chars", positive_int(value.get("max_chinese_chars"))),
    ):
        if number:
            result[key] = number
    return result


def prose_context_packet(body: str) -> str:
    selected = []
    for heading in (
        "## 硬约束：Canon 与时间线",
        "## 人物状态",
        "## 上一场正式交接",
    ):
        section = _markdown_h2_section(body, heading)
        if not section:
            continue
        if heading == "## 硬约束：Canon 与时间线":
            section = _compact_canon_context(section)
        elif heading == "## 人物状态":
            section = _compact_character_context(section)
        selected.append(section.strip())
    if not selected:
        return body
    return "# 当前场景硬事实与连续性\n\n" + "\n\n".join(selected)


def _select(value: object, *keys: str) -> dict:
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in keys if key in value}


def _markdown_h2_section(body: str, heading: str) -> str:
    match = re.search(rf"(?m)^{re.escape(heading)}\s*$", body)
    if not match:
        return ""
    next_heading = re.search(r"(?m)^##\s+", body[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(body)
    return body[match.start() : end].strip()


def _compact_character_context(section: str) -> str:
    for heading in ("### 加载策略", "### 本场景省略的次要角色"):
        section = _drop_markdown_h3_section(section, heading)
    return re.sub(r"\n{3,}", "\n\n", section).strip()


def _compact_canon_context(section: str) -> str:
    pattern = re.compile(r"(?ms)^### canon/world_rules\.yaml\s*\n(?P<body>.*?)(?=^###\s+|\Z)")
    match = pattern.search(section)
    if not match:
        return section
    try:
        payload = YAML(typ="safe").load(match.group("body").strip())
    except (ValueError, TypeError, OSError):
        return section
    if not isinstance(payload, dict):
        return section
    changed = False
    for key in ("rules", "constraints"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        filtered = [item for item in values if not _world_workflow_metadata(item)]
        if len(filtered) != len(values):
            payload[key] = filtered
            changed = True
    if not changed:
        return section
    stream = StringIO()
    writer = YAML()
    writer.default_flow_style = False
    writer.allow_unicode = True
    writer.dump(payload, stream)
    replacement = "### canon/world_rules.yaml\n\n" + stream.getvalue().rstrip() + "\n\n"
    return section[: match.start()] + replacement + section[match.end() :]


def _world_workflow_metadata(value: object) -> bool:
    if isinstance(value, dict):
        entry_id = str(value.get("id") or "").strip().casefold()
        if entry_id in {"candidate_not_confirmed", "candidate-status", "promotion-status"}:
            return True
    text = json.dumps(value, ensure_ascii=False).casefold()
    return any(
        signature.casefold() in text
        for signature in (
            "本候选资产", "写入正式 canon 前", "未经 schema 审查",
            "candidate_status", "ready_for_review",
        )
    )


def _drop_markdown_h3_section(section: str, heading: str) -> str:
    match = re.search(rf"(?m)^{re.escape(heading)}\s*$", section)
    if not match:
        return section
    next_heading = re.search(r"(?m)^###\s+", section[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(section)
    return section[: match.start()].rstrip() + "\n\n" + section[end:].lstrip()


__all__ = [
    "canon_scene_review", "composition_review", "continuity_prose", "continuity_scene",
    "prose_composition", "prose_context_packet", "scene_word_budget", "state_character",
    "state_composition", "state_patch", "state_scene",
]
