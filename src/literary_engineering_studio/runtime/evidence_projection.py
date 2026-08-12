"""Loss-preserving structured projections for Prompt v3 evidence."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import PurePosixPath
import re
from typing import Any

from ruamel.yaml import YAML


def project_evidence_body(
    path: str,
    body: str,
    *,
    fidelity: str,
    projection: str = "default",
    scene_id: str = "",
    chapter_id: str = "",
) -> str:
    """Remove empty or duplicated transport fields from structured evidence.

    Lossless evidence is never projected.  Structured projections preserve
    values and source identity while removing fields available from a higher
    fidelity source in the same Prompt Program.
    """

    if projection == "prose-context-packet":
        return _prose_context_packet_projection(body)
    if fidelity != "structured":
        return body
    suffix = PurePosixPath(path).suffix.casefold()
    try:
        if suffix == ".json":
            payload = json.loads(body)
            if projection == "prose-composition":
                payload = _prose_composition_projection(payload)
            elif projection == "prose-chapter-obligation":
                payload = _prose_chapter_obligation_projection(payload)
            elif projection == "prose-word-budget":
                payload = _prose_word_budget_projection(
                    payload,
                    scene_id=scene_id,
                    chapter_id=chapter_id,
                )
            elif path.endswith("scene_review.context.json"):
                payload = _review_context_projection(payload)
            elif path == "style/creative_quality_profile.json":
                payload = _creative_quality_projection(payload)
            return json.dumps(_prune_empty(payload), ensure_ascii=False, separators=(",", ":"))
        if suffix in {".yaml", ".yml"}:
            yaml = YAML(typ="safe")
            payload = yaml.load(body)
            if projection == "prose-scene":
                payload = _prose_scene_projection(payload)
            elif projection == "project-identity":
                payload = _project_identity_projection(payload)
            stream = StringIO()
            writer = YAML()
            writer.default_flow_style = False
            writer.allow_unicode = True
            writer.dump(_prune_empty(payload), stream)
            return stream.getvalue().rstrip()
    except (ValueError, TypeError, OSError):
        return body
    return body


def _prose_composition_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    reader = value.get("reader_experience_contract")
    reader_projection = {}
    if isinstance(reader, dict):
        reader_projection = {
            key: reader[key]
            for key in ("status", "required", "reader_experience", "issues")
            if key in reader
        }
    prose_contract = value.get("prose_execution_contract")
    prose_projection = {}
    if isinstance(prose_contract, dict):
        prose_projection = {
            key: prose_contract[key]
            for key in ("status", "errors", "input_contract_digest")
            if key in prose_contract
        }
    word_budget = _scene_word_budget_projection(value.get("word_budget_contract"))
    return {
        key: value[key]
        for key in (
            "schema",
            "scene_id",
            "selected_branch",
            "scene_facts",
            "characters",
            "beats",
            "composition_obligations",
            "subtext_map",
            "dialogue_intents",
            "sensory_palette",
            "narrative_rhythm",
            "scene_bridge",
        )
        if key in value
    } | {
        "word_budget_contract": word_budget,
        "reader_experience_contract": reader_projection,
        "prose_execution_contract": prose_projection,
    }


def _scene_word_budget_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    result = {
        key: value[key]
        for key in (
            "schema",
            "scene_id",
            "chapter_id",
            "count_unit",
            "scene_yaml_target_chinese_chars",
            "derived_target_chinese_chars",
            "tolerance",
            "narrative_load",
        )
        if key in value
    }
    target = _positive_int(value.get("target_chinese_chars")) or _positive_int(
        value.get("scene_yaml_target_chinese_chars")
    )
    minimum = _positive_int(value.get("min_chinese_chars"))
    maximum = _positive_int(value.get("max_chinese_chars"))
    if target:
        result["target_chinese_chars"] = target
    if minimum:
        result["min_chinese_chars"] = minimum
    if maximum:
        result["max_chinese_chars"] = maximum
    return result


def _positive_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _prose_context_packet_projection(body: str) -> str:
    """Keep the Broker-selected hard scene memory without its transport prose.

    The context packet is the authoritative capsule that binds formal Canon,
    scene-scoped character records, and the previous-scene handoff.  The prose
    task already receives dedicated scene, budget, composition, and style
    projections, so replaying those packet sections only creates conflicts.
    """

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
        if heading == "## 人物状态":
            section = _compact_character_context(section)
        selected.append(section.strip())
    if not selected:
        return body
    return "# 当前场景硬事实与连续性\n\n" + "\n\n".join(selected)


def _markdown_h2_section(body: str, heading: str) -> str:
    match = re.search(rf"(?m)^{re.escape(heading)}\s*$", body)
    if not match:
        return ""
    next_heading = re.search(r"(?m)^##\s+", body[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(body)
    return body[match.start() : end].strip()


def _compact_character_context(section: str) -> str:
    section = _drop_markdown_h3_section(section, "### 加载策略")
    section = _drop_markdown_h3_section(section, "### 本场景省略的次要角色")
    return re.sub(r"\n{3,}", "\n\n", section).strip()


def _compact_canon_context(section: str) -> str:
    """Remove known workflow metadata that older projects promoted as lore."""

    pattern = re.compile(
        r"(?ms)^### canon/world_rules\.yaml\s*\n(?P<body>.*?)(?=^###\s+|\Z)"
    )
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
    signatures = (
        "本候选资产",
        "写入正式 canon 前",
        "未经 schema 审查",
        "candidate_status",
        "ready_for_review",
    )
    return any(signature.casefold() in text for signature in signatures)


def _drop_markdown_h3_section(section: str, heading: str) -> str:
    match = re.search(rf"(?m)^{re.escape(heading)}\s*$", section)
    if not match:
        return section
    next_heading = re.search(r"(?m)^###\s+", section[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(section)
    return section[: match.start()].rstrip() + "\n\n" + section[end:].lstrip()


def _prose_chapter_obligation_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        key: value[key]
        for key in (
            "schema",
            "chapter_id",
            "status",
            "count_unit",
            "target_chinese_chars",
            "scene_count_target",
            "chapter_function",
            "must_payoff",
            "must_setup",
            "must_change",
            "must_not_resolve",
            "inherited_hooks",
            "ending_hook",
            "inventory_sufficiency",
            "expansion_needed",
        )
        if key in value
    }


def _prose_word_budget_projection(
    value: object,
    *,
    scene_id: str,
    chapter_id: str,
) -> object:
    if not isinstance(value, dict):
        return value
    binding = value.get("scene_inventory_binding")
    chapter_rows = binding.get("chapter_rows") if isinstance(binding, dict) else []
    chapter_id = chapter_id or _chapter_id_for_scene(scene_id, chapter_rows)
    chapter_budgets = value.get("chapter_budgets")
    current_budget = _matching_row(chapter_budgets, "chapter_id", chapter_id)
    current_binding = _matching_row(chapter_rows, "chapter_id", chapter_id)
    return {
        key: value[key]
        for key in ("schema", "target", "totals")
        if key in value
    } | {
        "current_chapter_budget": current_budget,
        "current_chapter_inventory": _planned_chapter_inventory(current_binding),
    }


def _planned_chapter_inventory(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        key: value[key]
        for key in (
            "chapter_id",
            "volume_id",
            "target_words",
            "target_scene_count",
            "avg_scene_words",
        )
        if key in value
    }


def _chapter_id_for_scene(scene_id: str, rows: object) -> str:
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            scene_ids = row.get("scene_ids")
            if isinstance(scene_ids, list) and scene_id in scene_ids:
                return str(row.get("chapter_id") or "")
    return ""


def _matching_row(rows: object, key: str, expected: str) -> object:
    if not isinstance(rows, list):
        return {}
    if expected:
        for row in rows:
            if isinstance(row, dict) and str(row.get(key) or "") == expected:
                return row
    return rows[0] if len(rows) == 1 and isinstance(rows[0], dict) else {}


def _prose_scene_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        key: value[key]
        for key in (
            "scene_id",
            "chapter_id",
            "chapter_obligation_id",
            "volume_id",
            "title",
            "word_count_target",
            "word_count_min",
            "word_count_max",
            "time",
            "location",
            "participants",
            "referenced_characters",
            "input_state",
            "scene_goal",
            "conflict",
            "actions",
            "revealed_info",
            "style_constraints",
            "reader_experience",
            "narrative_rhythm",
            "scene_bridge",
            "output_state",
            "next_hooks",
        )
        if key in value
    }


def _project_identity_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        key: value[key]
        for key in ("project", "creative_brief", "style")
        if key in value
    }


def _creative_quality_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        key: value[key]
        for key in (
            "schema",
            "profile_id",
            "name",
            "preset",
            "revision",
            "rule_modes",
            "thresholds",
            "punctuation",
            "custom_banned_phrases",
            "preferred_habits",
            "exceptions",
            "digest",
        )
        if key in value
    }


def _review_context_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    deterministic = value.get("deterministic_evidence")
    compact = dict(deterministic) if isinstance(deterministic, dict) else {}
    rhythm = compact.get("narrative_rhythm")
    if isinstance(rhythm, dict):
        compact["narrative_rhythm"] = {
            key: rhythm.get(key)
            for key in (
                "status",
                "missing_required",
                "plan_digest",
                "plan_revision",
                "source",
            )
            if key in rhythm
        }
    budget = compact.get("word_budget")
    if isinstance(budget, dict):
        compact["word_budget"] = {
            key: budget.get(key)
            for key in (
                "status",
                "budget_contract_status",
                "target_chinese_chars",
                "min_chinese_chars",
                "max_chinese_chars",
                "clean_body_chinese_chars",
                "narrative_load",
                "message",
            )
            if key in budget
        }
    return {
        key: _compact_review_schema(item) if key == "output_schema" else item
        for key, item in value.items()
        if key not in {"creative_quality_profile", "source_digests", "style_mount_snapshot"}
    } | {"deterministic_evidence": compact}


def _compact_review_schema(value: object) -> object:
    if not isinstance(value, dict):
        return value
    contract = value.get("contract")
    compact_contract = dict(contract) if isinstance(contract, dict) else {}
    compact_contract["required_type_groups"] = _required_type_groups(
        compact_contract
    )
    compact_contract.pop("recommended", None)
    compact_contract.pop("required", None)
    compact_contract.pop("types", None)
    return {
        key: item
        for key, item in value.items()
        if key != "resource_sha256"
    } | {"contract": compact_contract}


def _required_type_groups(contract: dict[str, Any]) -> dict[str, list[str]]:
    required = contract.get("required")
    field_types = contract.get("types")
    groups: dict[str, list[str]] = {}
    for field in required if isinstance(required, list) else []:
        field_type = field_types.get(field) if isinstance(field_types, dict) else None
        if isinstance(field_type, str):
            groups.setdefault(field_type, []).append(field)
    return groups


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: projected
            for key, item in value.items()
            if not _empty(projected := _prune_empty(item))
        }
    if isinstance(value, list):
        return [projected for item in value if not _empty(projected := _prune_empty(item))]
    return value


def _empty(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


__all__ = ["project_evidence_body"]
