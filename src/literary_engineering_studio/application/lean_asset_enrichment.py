"""Deepen only lean-planning assets that still match their generated stubs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.literary import character_slug
from literary_engineering_studio_engine.public.projects import atomic_write_batch

from .lean_assets import _character_stub, _scalar, _world_stub
from .project_manager import read_directions
from ..runtime.role_conversation import RoleConversationGateway


def enrich_lean_planning_assets(
    project_root: Path, gateway: RoleConversationGateway,
) -> dict[str, int]:
    """Create hidden histories and operational world rules after stub creation.

    Exact stub comparison is the ownership boundary: user-edited or previously
    enriched files are never replaced by a later autopilot pass.
    """
    root = project_root.expanduser().resolve()
    plan = json.loads((root / "plot" / "lean_project_plan.json").read_text(encoding="utf-8"))
    characters = plan.get("characters") or []
    eligible = _eligible_characters(root, characters)
    world_facts = plan.get("world_facts") or []
    world_path = root / "canon" / "world_rules.yaml"
    enrich_world = _is_generated_world(world_path, world_facts)
    if not eligible and not enrich_world:
        return {"background_stories_created": 0, "world_rules_enriched": 0}

    prompt = _enrichment_prompt(root, characters, eligible, world_facts if enrich_world else [])
    answer = gateway.run(root, prompt, role="worker", timeout=900).answer.strip()
    if answer.startswith("```"):
        answer = "\n".join(answer.splitlines()[1:-1]).strip()
    payload = json.loads(answer)
    if not isinstance(payload, dict):
        raise ValueError("asset enrichment response must be a JSON object")
    rows = _validated_rows(payload, eligible)
    writes = {eligible[row["name"]]: _render_character(eligible[row["name"]], row) for row in rows}
    if enrich_world:
        writes[world_path] = _render_world(payload.get("world"))
    atomic_write_batch(writes)
    return {"background_stories_created": len(eligible), "world_rules_enriched": int(enrich_world)}


def _eligible_characters(root: Path, characters: list[dict[str, object]]) -> dict[str, Path]:
    eligible: dict[str, Path] = {}
    for character in characters:
        slug = character_slug(str(character["name"]))
        path = root / "characters" / f"{slug}.yaml"
        if path.is_file() and path.read_text(encoding="utf-8") == _character_stub(slug, character):
            eligible[str(character["name"])] = path
    return eligible


def _is_generated_world(path: Path, facts: list[object]) -> bool:
    return bool(facts) and path.is_file() and path.read_text(encoding="utf-8") == _world_stub(facts)


def _enrichment_prompt(
    root: Path, characters: list[dict[str, object]], eligible: dict[str, Path], world_facts: list[object],
) -> str:
    directions = [str(row.get("message") or "") for row in read_directions(root, limit=10)]
    forbidden = root / "canon" / "forbidden_changes.yaml"
    return "\n".join([
        "# 人物隐性背景与世界规则细化",
        "你是作品主创。初始人物档案已建立；现在独立推演他们的背景故事，并把世界事实细化为可执行规则。只返回 JSON 对象。",
        "characters 每项只含 name, summary, formative_events(数组), hidden_wound, behavior_influences(数组), reveal_policy。人物名单必须与待补人物完全一致，不能新造身份。",
        "背景故事要有过去事件、形成的信念或伤口、当下选择/回避/误判的具体因果；在正文中默认只通过行为显影，不直接设定讲解。reveal_policy 为 implicit_only 或 delayed_reveal。",
        "world 只含 rules(数组), constraints(数组), open_questions(数组)。每条规则说明适用条件、边界/例外、违反代价及会造成的场景后果；制度、资源、历史压力也应有具体执行方式。",
        "不要把情节大纲改写成世界规则，不创造万能解法。现实题材只细化已有制度/现实限制，不虚构超常规则；不确定处放 open_questions，不写成确认事实。",
        "所有字符串要有实质内容；不得只把 background 或 world_facts 换一种说法。不得与已确认 canon 或最新用户方向冲突。",
        "## 待补人物\n" + json.dumps([row for row in characters if str(row["name"]) in eligible], ensure_ascii=False),
        "## 已有世界事实\n" + json.dumps(world_facts, ensure_ascii=False),
        "## 用户方向\n" + ("\n".join(directions)[-5000:] or "无额外方向"),
        "## 项目约束\n" + (root / "project.yaml").read_text(encoding="utf-8")[:5000],
        "## 禁止变更\n" + (forbidden.read_text(encoding="utf-8")[:3000] if forbidden.is_file() else "无"),
    ])


def _validated_rows(payload: dict[str, Any], eligible: dict[str, Path]) -> list[dict[str, Any]]:
    rows = payload.get("characters")
    if not isinstance(rows, list) or {row.get("name") for row in rows if isinstance(row, dict)} != set(eligible):
        raise ValueError("asset enrichment must cover each eligible character exactly once")
    if len(rows) != len(eligible):
        raise ValueError("asset enrichment contains duplicate character names")
    for row in rows:
        _require_text(row, "summary", "hidden_wound")
        _require_list(row, "formative_events", "behavior_influences")
        policy = row.get("reveal_policy")
        if policy not in {"implicit_only", "delayed_reveal"}:
            raise ValueError("background reveal_policy must be implicit_only or delayed_reveal")
    return rows


def _render_character(path: Path, row: dict[str, Any]) -> str:
    original = path.read_text(encoding="utf-8")
    block = "\n".join([
            "background_story:",
            f"  summary: {_scalar(row['summary'])}",
            f"  formative_events: {_scalar(row['formative_events'])}",
            f"  hidden_wound: {_scalar(row['hidden_wound'])}",
            f"  behavior_influences: {_scalar(row['behavior_influences'])}",
            f"  reveal_policy: {row['reveal_policy']}",
        ])
    return original.replace("bdi:\n", block + "\nbdi:\n", 1)


def _render_world(world: object) -> str:
    if not isinstance(world, dict):
        raise ValueError("asset enrichment world must be an object")
    _require_list(world, "rules", "constraints")
    questions = world.get("open_questions")
    if not isinstance(questions, list) or not all(isinstance(item, str) for item in questions):
        raise ValueError("world.open_questions must be a string array")
    return "\n".join([
            f"rules: {_scalar(world['rules'])}",
            f"constraints: {_scalar(world['constraints'])}",
            f"open_questions: {_scalar(questions)}",
            "",
        ])


def _require_text(row: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError(f"asset enrichment {key} must be nonempty text")


def _require_list(row: dict[str, Any], *keys: str) -> None:
    for key in keys:
        value = row.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            raise ValueError(f"asset enrichment {key} must be a nonempty string array")


__all__ = ["enrich_lean_planning_assets"]
