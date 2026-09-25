"""Deepen only lean-planning assets that still match their generated stubs."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import character_slug
from literary_engineering_studio_engine.public.projects import atomic_write_batch
from ruamel.yaml import YAML

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

    rows: list[dict[str, Any]] = []
    for name, path in eligible.items():
        one = {name: path}
        prompt = _enrichment_prompt(root, characters, one, [])
        payload = _ask_validated(root, gateway, prompt, lambda value: _validated_rows(value, one))
        rows.extend(_validated_rows(payload, one))
    if rows:
        voices = _ask_validated(root, gateway, _voice_prompt(root, rows, characters),
                                lambda value: _validated_voices(value, {row["name"] for row in rows}))
        for row in rows:
            row["speech_style"] = voices["voices"][row["name"]]
    writes = {eligible[row["name"]]: _render_character(eligible[row["name"]], row) for row in rows}
    if enrich_world:
        prompt = _enrichment_prompt(root, characters, {}, world_facts)
        payload = _ask_validated(root, gateway, prompt, _validate_world_payload)
        writes[world_path] = _render_world(payload.get("world"))
    atomic_write_batch(writes)
    return {"background_stories_created": len(rows), "world_rules_enriched": int(enrich_world)}


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
        "你是作品主创。初始人物档案已建立；现在让人物的过去、欲望、关系和误判形成因果，让已有世界事实变成会影响场景选择的规则。语言声音下一轮单独创作。只返回 JSON 对象。",
        "characters 中每人含 name, summary, formative_events(字符串数组), hidden_wound, behavior_influences(字符串数组), reveal_policy, appearance, clothing, beliefs(字符串数组), intentions(字符串数组), fears(字符串数组), secrets(字符串数组), public_private_contrast, moral_line, relationships(字符串数组；每条可写‘对象｜公开关系｜私下张力’)。经历能在此刻选择中留下痕迹；人物底色也容得下新的亲近、争执、玩笑和出人意料的长谈。尚无根据的心理或行动字段可用空数组，尤其是不在场人物。reveal_policy 为 implicit_only 或 delayed_reveal。",
        "world 含 rules(数组), constraints(数组), open_questions(数组)；rules 可为字符串，或含 rule, condition, boundary, consequence 的对象。只深化已有世界事实，未确定的事写进 open_questions。",
        "每次只处理待补人物或世界事实：无待补人物时 characters 为 []，没有待补世界事实时 world 为 {}。",
        "## 待补人物\n" + json.dumps([row for row in characters if str(row["name"]) in eligible], ensure_ascii=False),
        "## 全部人物与关系位置\n" + json.dumps(characters, ensure_ascii=False),
        "## 已有世界事实\n" + json.dumps(world_facts, ensure_ascii=False),
        "## 用户方向\n" + ("\n".join(directions)[-5000:] or "无额外方向"),
        "## 项目约束\n" + (root / "project.yaml").read_text(encoding="utf-8")[:5000],
        "## 禁止变更\n" + (forbidden.read_text(encoding="utf-8")[:3000] if forbidden.is_file() else "无"),
    ])


def _voice_prompt(
    root: Path, rows: list[dict[str, Any]], characters: list[dict[str, object]],
) -> str:
    directions = [str(item.get("message") or "") for item in read_directions(root, limit=10)]
    return "\n".join([
        "# 人物语言声音",
        "你是作品主创。闭眼听这组人物在休息日闲谈、争吵、讲旧事：遮住姓名，仍能从他们的兴致、长短、转弯、幽默和情绪变化听出是谁。先替每个人找到工作身份以外的口头来历：家里怎样叫人，童年听过怎样的故事，在谁面前爱逞强、爱絮叨、爱开玩笑。每个人的声音先属于活过的人，再属于职业；职业词只占生活词汇的一角。为整组人物分配不同的表达幅度与展开方式：可有人平日就爱铺陈、岔题、逗弄或顶嘴，也有人在亲密或争执时终于说出完整的想法；寡言者有被特定的人和事打开话头的条件。让其中至少一人的日常话语富于兴致、口语起伏和主动追问，使全组听感拉开。vocabulary 写生活与情感的词域及说话兴致，rhythm 写同一人闲谈、亲密和争执时的舒缩，signature_patterns 写面对不同亲疏对象时会变形的言语趣味。用人物自己的欲望和关系去带动措辞，给他们谈日常、胡闹、袒露或争执的余地。",
        "只返回 JSON：{\"voices\":{\"人物姓名\":{\"vocabulary\":\"此人的词汇与表达趣味\",\"rhythm\":\"从容到动情的句法变化\",\"taboo_words\":[],\"signature_patterns\":[\"可变化的说话习惯\"]}}}。voices 覆盖待补人物，taboo_words 仅放人物自己确有理由避开的词，可以为空。",
        "## 人物经历与关系\n" + json.dumps(rows, ensure_ascii=False),
        "## 全部人物\n" + json.dumps(characters, ensure_ascii=False),
        "## 作品与用户方向\n" + (root / "project.yaml").read_text(encoding="utf-8")[:2500]
        + "\n" + ("\n".join(directions)[-2500:] or "无额外方向"),
    ])


def _ask_validated(
    root: Path, gateway: RoleConversationGateway, prompt: str,
    validator: Callable[[dict[str, Any]], object],
) -> dict[str, Any]:
    answer = gateway.run(root, prompt, role="worker", timeout=900).answer.strip()
    try:
        payload = _json_payload(answer)
        validator(payload)
        return payload
    except (json.JSONDecodeError, ValueError) as exc:
        repair = "\n".join([
            prompt,
            "## 结构返修",
            "上一份结果不完整或不符合契约。只返回一份完整、有效且更紧凑的 JSON 对象；不得省略必填字段，不写解释或代码围栏。",
            "校验错误：" + str(exc),
            "上一份结果：\n" + answer[-12000:],
        ])
        repaired = gateway.run(root, repair, role="worker", timeout=900).answer.strip()
        payload = _json_payload(repaired)
        validator(payload)
        return payload


def _json_payload(answer: str) -> dict[str, Any]:
    if answer.startswith("```"):
        answer = "\n".join(answer.splitlines()[1:-1]).strip()
    payload = json.loads(answer)
    if not isinstance(payload, dict):
        raise ValueError("asset enrichment response must be a JSON object")
    return payload


def _validate_world_payload(payload: dict[str, Any]) -> None:
    _validated_rows(payload, {})
    _render_world(payload.get("world"))


def _validated_rows(payload: dict[str, Any], eligible: dict[str, Path]) -> list[dict[str, Any]]:
    rows = payload.get("characters")
    if not isinstance(rows, list):
        raise ValueError("asset enrichment must cover each eligible character exactly once")
    # Some models answer a one-character task with the whole planned cast.
    # Treat those extra rows as untrusted surplus, never as write authority.
    selected = [row for row in rows if isinstance(row, dict) and row.get("name") in eligible]
    if {row["name"] for row in selected} != set(eligible):
        raise ValueError("asset enrichment must cover each eligible character exactly once")
    if len(selected) != len(eligible):
        raise ValueError("asset enrichment contains duplicate character names")
    for row in selected:
        _require_text(
            row, "summary", "hidden_wound", "appearance", "clothing",
            "public_private_contrast", "moral_line",
        )
        row["relationships"] = _normalize_relationships(row.get("relationships"))
        for key in ("formative_events", "behavior_influences", "beliefs", "intentions", "fears", "relationships"):
            _string_array(row, key, allow_empty=True)
        _string_array(row, "secrets", allow_empty=True)
        policy = row.get("reveal_policy")
        if policy not in {"implicit_only", "delayed_reveal"}:
            raise ValueError("background reveal_policy must be implicit_only or delayed_reveal")
    return selected


def _normalize_relationships(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("asset enrichment relationships must be a string array")
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        elif isinstance(item, dict) and item:
            parts = [f"{key}：{part.strip() if isinstance(part, str) else json.dumps(part, ensure_ascii=False)}"
                     for key, part in item.items() if str(key).strip() and part not in (None, "", [], {})]
            if not parts:
                raise ValueError("asset enrichment relationships contains an empty object")
            normalized.append("；".join(parts))
        else:
            raise ValueError("asset enrichment relationships must be a string array")
    return normalized


def _validated_voices(payload: dict[str, Any], names: set[str]) -> None:
    voices = payload.get("voices")
    if not isinstance(voices, dict) or set(voices) != names:
        raise ValueError("voices must cover the requested characters")
    for speech in voices.values():
        if not isinstance(speech, dict):
            raise ValueError("speech_style must be an object")
        _require_text(speech, "vocabulary", "rhythm")
        _string_array(speech, "taboo_words", allow_empty=True)
        _require_list(speech, "signature_patterns")


def _render_character(path: Path, row: dict[str, Any]) -> str:
    reader = YAML(typ="safe")
    original = reader.load(path.read_text(encoding="utf-8"))
    if not isinstance(original, dict):
        raise ValueError(f"generated character stub is invalid: {path.name}")
    identity = dict(original.get("identity") or {})
    identity.update({"appearance": row["appearance"], "clothing": row["clothing"]})
    bdi = dict(original.get("bdi") or {})
    bdi.update({"belief": row["beliefs"], "intention": row["intentions"]})
    ordered: dict[str, Any] = {
        key: original[key]
        for key in ("character_id", "name", "role", "importance")
        if key in original
    }
    ordered.update({
        "identity": identity,
        "background_story": {
            "summary": row["summary"],
            "formative_events": row["formative_events"],
            "hidden_wound": row["hidden_wound"],
            "behavior_influences": row["behavior_influences"],
            "reveal_policy": row["reveal_policy"],
        },
        "bdi": bdi,
        "psychology": {
            "fear": row["fears"],
            "secret": row["secrets"],
            "wound": row["hidden_wound"],
            "mask": row["public_private_contrast"],
            "moral_line": row["moral_line"],
        },
        "relationships": row["relationships"],
        "speech_style": row["speech_style"],
        "state": original.get("state") or {"known_facts": []},
    })
    for key, value in original.items():
        if key not in ordered:
            ordered[key] = value
    stream = StringIO()
    writer = YAML()
    writer.allow_unicode = True
    writer.default_flow_style = False
    writer.dump(ordered, stream)
    return stream.getvalue()


def _render_world(world: object) -> str:
    if not isinstance(world, dict):
        raise ValueError("asset enrichment world must be an object")
    rules = _world_rules(world.get("rules"))
    constraints = _string_array(world, "constraints", allow_empty=True)
    questions = _string_array(world, "open_questions", allow_empty=True)
    return "\n".join([
            f"rules: {_scalar(rules)}",
            f"constraints: {_scalar(constraints)}",
            f"open_questions: {_scalar(questions)}",
            "",
        ])


def _world_rules(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("asset enrichment rules must be a nonempty array")
    rendered: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            rendered.append(item.strip())
            continue
        if not isinstance(item, dict):
            raise ValueError("world.rules entries must be text or rule objects")
        _require_text(item, "rule", "condition", "boundary", "consequence")
        rendered.append(
            f"规则：{item['rule']}；适用条件：{item['condition']}；"
            f"边界或例外：{item['boundary']}；违反或触发后果：{item['consequence']}"
        )
    return rendered


def _require_text(row: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError(f"asset enrichment {key} must be nonempty text")


def _require_list(row: dict[str, Any], *keys: str) -> None:
    for key in keys:
        value = _string_array(row, key, allow_empty=False)
        if not value:
            raise ValueError(f"asset enrichment {key} must be a nonempty string array")


def _string_array(row: dict[str, Any], key: str, *, allow_empty: bool) -> list[str]:
    value = row.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        qualifier = "" if allow_empty else "nonempty "
        raise ValueError(f"asset enrichment {key} must be a {qualifier}string array")
    if not allow_empty and not value:
        raise ValueError(f"asset enrichment {key} must be a nonempty string array")
    return [item.strip() for item in value]


__all__ = ["enrich_lean_planning_assets"]
