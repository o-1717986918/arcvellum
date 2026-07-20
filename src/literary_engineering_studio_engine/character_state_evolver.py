"""Character state evolution candidate patch builder."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_tasks import default_agent_tasks_path, write_agent_tasks
from .flow_gates import ensure_composition_ready_for_generation
from .roleplay_lab import CharacterCard, _list_after, _load_characters, _nested_list, _nested_scalar, _read, _scalar


@dataclass(frozen=True)
class CharacterStatePatchResult:
    project_root: Path
    output_path: Path
    json_path: Path
    agent_tasks_path: Path | None
    scene_id: str
    source_path: Path
    character_count: int
    unresolved_count: int


def build_character_state_patch(
    project_root: Path,
    scene: Path | None = None,
    source: Path | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
    agent_tasks: bool = False,
) -> CharacterStatePatchResult:
    """Build a reviewable character-state patch from one scene artifact."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else _resolve(root, scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    scene_text = _read(scene_path)
    scene_id = _scalar(scene_text, "scene_id") or scene_path.stem or "scene"
    participants = _list_value(scene_text, "participants")
    source_path = _resolve_source(root, scene_id, source)
    if _is_composition_source(source_path):
        ensure_composition_ready_for_generation(root, source_path)
    source_text = _read(source_path)
    if not source_text:
        raise FileNotFoundError(f"source artifact not found or empty: {source_path}")

    cards = _load_characters(root)
    active_cards = _active_cards(cards, participants)
    source_changes = _source_changes(source_path, source_text)
    patches, unresolved = _build_patches(root, active_cards or cards, active_cards, source_changes)
    default_dir = root / "characters" / "state_patches"
    output_path = _resolve(root, output, default_dir / f"{scene_id}_state_patch.md")
    json_path = _resolve(root, json_output, default_dir / f"{scene_id}_state_patch.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "literary-engineering-workbench/character-state-patch/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "source_artifact": _rel(source_path, root),
        "status": "pending_human_approval",
        "characters": patches,
        "unresolved_changes": unresolved,
        "source_changes": source_changes,
        "new_character_policy": {
            "status": "requires_platform_agent_check",
            "rule": "持久新角色必须进入 characters/candidates/，不得通过 state patch 直接写入正式角色库。",
        },
        "approval_required": [
            "确认每条人物状态变化是否由正文实际支撑。",
            "确认状态变化是否会影响 canon、人物弧光或后续场景输入。",
            "确认后续写回时只修改对应人物档案，不覆盖无关字段。",
        ],
        "guardrails": [
            "本文件是候选 patch，不会自动修改 characters/*.yaml。",
            "人物重大转折必须人工确认后才能写回。",
            "关系变化、已知事实和弧光阶段不得绕过 canon-lint 与 review-scene。",
            "正文中新出现的持久角色不得写入既有人物状态；必须进入 characters/candidates/ 并走资产审查、用户批准和晋升。",
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.write_text(_render_markdown(payload), encoding="utf-8")
    agent_tasks_path = None
    if agent_tasks:
        agent_tasks_path = _write_state_patch_agent_tasks(root, scene_path, source_path, output_path, json_path, payload)
    return CharacterStatePatchResult(
        project_root=root,
        output_path=output_path,
        json_path=json_path,
        agent_tasks_path=agent_tasks_path,
        scene_id=scene_id,
        source_path=source_path,
        character_count=len(patches),
        unresolved_count=len(unresolved),
    )


def _write_state_patch_agent_tasks(
    root: Path,
    scene_path: Path,
    source_path: Path,
    output_path: Path,
    json_path: Path,
    payload: dict[str, Any],
) -> Path:
    return write_agent_tasks(
        default_agent_tasks_path(output_path),
        title=f"state-evolve {payload['scene_id']}",
        root=root,
        source_paths=[scene_path, source_path, output_path, json_path],
        notes=[
            "state_patch.json 是候选写回契约，不能写入 AGENT_TASK 标记。",
            "状态变化只有在用户批准后才能通过 state-apply 写回 characters/*.yaml。",
        ],
        tasks=[
            (
                "审查状态变化依据",
                """逐条检查 proposed_updates 是否能从 source_artifact 的可见正文、候选正文或 composition 中找到依据。删除或标记缺少文本证据的状态变化。""",
            ),
            (
                "审查人物一致性",
                """对照人物 belief / desire / intention / fear / moral_line / background_story，判断状态变化、弧光变化和关系变化是否自然。特别检查 background_story 是否被误当作明示事实写入。""",
            ),
            (
                "审查新角色边界",
                """检查 source_artifact 是否引入 scene.yaml participants 和正式 characters/*.yaml 中没有的人物。一次性路人可在报告中说明豁免理由；有名字、会复用、推动线索/关系/主线的新角色，必须列入 unresolved_changes，并建议运行 agent-create-character 或 asset-create 生成候选角色资产。不得把新角色状态硬塞进现有人物 patch。""",
            ),
            (
                "审查写回边界",
                """确认 state-apply 只会修改 characters/*.yaml 中允许的 state、arc、relationships、memory refs，不会写 canon、plot 或 release。列出必须由用户批准的重大变化。""",
            ),
            (
                "决定下一步",
                """决定该 patch 应请求用户批准、退回重写、拆分为更小 patch，还是保持候选等待后续场景。不要自动应用。""",
            ),
        ],
    )


def _source_changes(source_path: Path, text: str) -> dict[str, list[str]]:
    if source_path.suffix.lower() == ".json":
        return _json_source_changes(text)
    return {
        "new_facts": _extract_bullets(text, "新增事实候选"),
        "character_changes": _extract_bullets(text, "人物状态变化") or _extract_writeback_values(text, "character_changes"),
        "relationship_changes": _extract_bullets(text, "关系变化") or _extract_writeback_values(text, "relationship_changes"),
        "foreshadowing_changes": _extract_bullets(text, "伏笔变化") or _extract_writeback_values(text, "foreshadowing_changes"),
        "approval_items": _extract_bullets(text, "需要人工确认"),
    }


def _json_source_changes(text: str) -> dict[str, list[str]]:
    data = json.loads(text)
    writeback = data.get("writeback_candidates", {}) if isinstance(data, dict) else {}
    if not isinstance(writeback, dict):
        writeback = {}
    return {
        "new_facts": _string_list(writeback.get("new_facts", [])),
        "character_changes": _string_list(writeback.get("character_changes", [])),
        "relationship_changes": _string_list(writeback.get("relationship_changes", [])),
        "foreshadowing_changes": _string_list(writeback.get("foreshadowing_changes", [])),
        "approval_items": _string_list(writeback.get("approval_items", [])),
    }


def _build_patches(
    root: Path,
    cards: list[CharacterCard],
    active_cards: list[CharacterCard],
    changes: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    patches: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, str]] = []
    for card in cards:
        patches[card.character_id] = {
            "character_id": card.character_id,
            "name": card.name,
            "file": _rel(card.file, root),
            "current_state": _current_state(card.file),
            "proposed_updates": {
                "state": {
                    "known_facts_add": [],
                    "resources_add": [],
                    "location_note": "",
                    "health_note": "",
                },
                "arc": {
                    "candidate_changes": [],
                },
                "relationships": {
                    "candidate_changes": [],
                },
                "notes": [],
            },
            "confidence": "candidate",
        }

    for item in changes.get("character_changes", []):
        matched = _match_cards(item, cards, active_cards)
        if not matched:
            unresolved.append({"kind": "character_changes", "text": item})
            continue
        for card in matched:
            _add_character_change(patches[card.character_id], item)

    for item in changes.get("relationship_changes", []):
        matched = _match_cards(item, cards, active_cards)
        if not matched:
            unresolved.append({"kind": "relationship_changes", "text": item})
            continue
        for card in matched:
            patches[card.character_id]["proposed_updates"]["relationships"]["candidate_changes"].append(item)

    result = [patch for patch in patches.values() if _has_updates(patch)]
    return result, unresolved


def _current_state(path: Path) -> dict[str, Any]:
    text = _read(path)
    return {
        "state": {
            "location": _nested_scalar(text, "state", "location"),
            "health": _nested_scalar(text, "state", "health"),
            "resources": _nested_list(text, "state", "resources"),
            "known_facts": _nested_list(text, "state", "known_facts"),
            "unknown_facts": _nested_list(text, "state", "unknown_facts"),
        },
        "arc": {
            "current_stage": _nested_scalar(text, "arc", "current_stage"),
            "expected_change": _nested_scalar(text, "arc", "expected_change"),
            "required_trigger_events": _nested_list(text, "arc", "required_trigger_events"),
        },
    }


def _add_character_change(patch: dict[str, Any], item: str) -> None:
    state = patch["proposed_updates"]["state"]
    arc = patch["proposed_updates"]["arc"]
    notes = patch["proposed_updates"]["notes"]
    if any(word in item for word in ["发现", "知道", "得知", "确认", "意识到"]):
        state["known_facts_add"].append(item)
    if any(word in item for word in ["受伤", "伤", "疲惫", "病", "虚弱"]):
        state["health_note"] = item
    if any(word in item for word in ["到达", "进入", "离开", "留在"]):
        state["location_note"] = item
    if any(word in item for word in ["获得", "失去", "拿到", "交出"]):
        state["resources_add"].append(item)
    arc["candidate_changes"].append(item)
    notes.append("该变化来自场景产物，写回前需人工确认。")


def _has_updates(patch: dict[str, Any]) -> bool:
    updates = patch["proposed_updates"]
    state = updates["state"]
    return bool(
        state["known_facts_add"]
        or state["resources_add"]
        or state["location_note"]
        or state["health_note"]
        or updates["arc"]["candidate_changes"]
        or updates["relationships"]["candidate_changes"]
    )


def _match_cards(text: str, cards: list[CharacterCard], active_cards: list[CharacterCard]) -> list[CharacterCard]:
    matches = [
        card
        for card in cards
        if (card.name and card.name in text) or (card.character_id and card.character_id in text)
    ]
    if matches:
        return matches
    return active_cards if len(active_cards) == 1 else []


def _resolve_source(root: Path, scene_id: str, source: Path | None) -> Path:
    if source is not None:
        return _resolve(root, source)
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if draft.exists():
        return draft
    candidates = sorted(
        (root / "drafts" / "candidates").glob(f"{scene_id}-*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    if composition.exists():
        return composition
    raise FileNotFoundError(f"no source artifact found for scene: {scene_id}")


def _is_composition_source(path: Path) -> bool:
    name = path.name.lower()
    return "_composition." in name and "drafts" in path.as_posix().lower()


def _extract_bullets(text: str, heading: str) -> list[str]:
    match = re.search(rf"(?ms)^###\s*{re.escape(heading)}\s*\n(.*?)(?=^###\s+|^##\s+|\Z)", text)
    if not match:
        return []
    return _bullet_lines(match.group(1))


def _extract_writeback_values(text: str, key: str) -> list[str]:
    match = re.search(rf"(?ms)^-\s*`{re.escape(key)}`\s*\n(.*?)(?=^-\s*`|\Z)", text)
    if not match:
        return []
    return _bullet_lines(match.group(1))


def _bullet_lines(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped.lstrip("-").strip()
        if item:
            items.append(item)
    return [item for item in items if item and item not in {"", "待真实 provider 补全。", "无。"}]


def _active_cards(cards: list[CharacterCard], participants: list[str]) -> list[CharacterCard]:
    if not participants:
        return cards
    wanted = set(participants)
    return [card for card in cards if card.character_id in wanted or card.name in wanted]


def _list_value(text: str, key: str) -> list[str]:
    inline = _scalar(text, key)
    if inline.startswith("[") and inline.endswith("]"):
        return [item.strip().strip("\"'") for item in inline.strip("[]").split(",") if item.strip()]
    return _list_after(text, key)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# 人物状态演化候选 Patch：{payload['scene_id']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 场景：`{payload['scene']}`",
        f"- 来源产物：`{payload['source_artifact']}`",
        f"- 状态：`{payload['status']}`",
        "",
        "## 使用边界",
        "",
        _md_list(payload["guardrails"]),
        "",
        "## 候选写回",
        "",
    ]
    if not payload["characters"]:
        lines.extend(["- 未生成可匹配人物的状态 patch。", ""])
    for patch in payload["characters"]:
        updates = patch["proposed_updates"]
        state = updates["state"]
        lines.extend(
            [
                f"### {patch['name']} `{patch['character_id']}`",
                "",
                f"- 人物文件：`{patch['file']}`",
                f"- 置信等级：`{patch['confidence']}`",
                "",
                "状态候选：",
                "",
                _md_list(
                    state["known_facts_add"]
                    + state["resources_add"]
                    + [item for item in [state["location_note"], state["health_note"]] if item]
                ),
                "",
                "弧光候选：",
                "",
                _md_list(updates["arc"]["candidate_changes"]),
                "",
                "关系候选：",
                "",
                _md_list(updates["relationships"]["candidate_changes"]),
                "",
            ]
        )
    lines.extend(["## 未匹配变化", ""])
    if payload["unresolved_changes"]:
        for item in payload["unresolved_changes"]:
            lines.append(f"- `{item['kind']}`：{item['text']}")
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 人工确认清单",
            "",
            _md_list(payload["approval_required"]),
            "",
            "## 后续",
            "",
            "- 审查通过后，下一阶段才允许实现受控写回命令。",
            "- 写回前应保留本 patch 作为审批证据。",
        ]
    )
    return "\n".join(lines) + "\n"


def _md_list(items: list[str]) -> str:
    if not items:
        return "- 无。"
    return "\n".join(f"- {item}" for item in items)


def _resolve(root: Path, value: Path | None, default: Path | None = None) -> Path:
    if value is None:
        if default is None:
            raise ValueError("default path is required when value is None")
        return default
    return value if value.is_absolute() else root / value


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
