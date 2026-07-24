"""Story architecture, word-budget, and rhythm projections."""

from __future__ import annotations

from pathlib import Path

from ...display_cleaner import nested_scalar_from_yaml_text, read_json_file, scalar_from_yaml_text, summarize_text
from .common import (
    _apply_overrides,
    _display_hooks,
    _display_list_value,
    _display_scene_name,
    _display_text_for_path,
    _json_to_display_text,
    _read_text,
    _rel,
)
from ...display_cleaner import truncate_text

def _word_budget_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    budget = root / "plot" / "word_budget" / "word_budget.json"
    if budget.exists():
        payload = read_json_file(budget)
        totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
        body = _display_text_for_path(root / "plot" / "word_budget" / "word_budget.md")
        item = {
            "kind": "word_budget",
            "id": "word_budget",
            "title": "长篇字数预算",
            "subtitle": "目标长度与剧情库存",
            "path": _rel(budget, root),
            "status": str(payload.get("status") or "unknown"),
            "badges": [str(payload.get("status") or "unknown"), f"{totals.get('chapter_count', 0)} 章", f"{totals.get('scene_count', 0)} 场"],
            "excerpt": summarize_text(body, limit=240) or "预算文件存在，但还没有可读报告。",
            "body": truncate_text(body, 3000),
            "facts": [
                {"label": "目标字数", "value": totals.get("target_words") or "未设置"},
                {"label": "章节数", "value": totals.get("chapter_count") or 0},
                {"label": "场景数", "value": totals.get("scene_count") or 0},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    obligations = root / "plot" / "chapter_obligations"
    if obligations.exists():
        for path in sorted(obligations.glob("*.json"))[:80]:
            payload = read_json_file(path)
            if not payload:
                continue
            chapter_id = str(payload.get("chapter_id") or path.stem)
            item = {
                "kind": "word_budget",
                "id": f"chapter__{chapter_id}",
                "title": f"{chapter_id} 章节义务",
                "subtitle": "读者体验契约",
                "path": _rel(path, root),
                "status": str(payload.get("status") or "draft"),
                "badges": [str(payload.get("status") or "draft")],
                "excerpt": truncate_text(str(payload.get("chapter_function") or payload.get("ending_hook") or "章节义务等待平台 Agent 填写。"), 240),
                "facts": [
                    {"label": "章节功能", "value": payload.get("chapter_function") or "未填写"},
                    {"label": "章末钩子", "value": payload.get("ending_hook") or "未填写"},
                    {"label": "库存充分性", "value": payload.get("inventory_sufficiency") or "未填写"},
                ],
            }
            items.append(_apply_overrides(item, overrides))
    return items

def _story_architecture_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    """Project the longform spine and its independent review without promoting it."""

    candidate = root / "plot" / "story_architecture.candidate.json"
    if not candidate.exists():
        return []
    payload = read_json_file(candidate)
    review = read_json_file(root / "reviews" / "longform" / "story_architecture_review.json")
    review_status = str(review.get("verdict") or "pending") if review else "missing"
    obligations = payload.get("volume_obligations") if isinstance(payload.get("volume_obligations"), list) else []
    payoffs = payload.get("non_negotiable_payoffs") if isinstance(payload.get("non_negotiable_payoffs"), list) else []
    body = _json_to_display_text(payload)
    item = {
        "kind": "story_architecture",
        "id": "story_architecture",
        "title": "全书故事架构",
        "subtitle": "不可替代的长篇脊柱",
        "path": _rel(candidate, root),
        "status": str(payload.get("status") or "pending"),
        "badges": [f"独立审查：{review_status}", f"{len(obligations)} 卷义务", f"{len(payoffs)} 个必兑现项"],
        "excerpt": str(payload.get("central_dramatic_question") or payload.get("premise") or "故事架构尚未填写。"),
        "body": truncate_text(body, 3000),
        "facts": [
            {"label": "中心戏剧问题", "value": payload.get("central_dramatic_question") or "未填写"},
            {"label": "人物改变", "value": payload.get("change_vector") or "未填写"},
            {"label": "中点不可逆", "value": payload.get("midpoint_irreversibility") or "未填写"},
            {"label": "终局选择", "value": payload.get("endgame_choice") or "未填写"},
            {"label": "独立审查", "value": review_status},
        ],
    }
    return [_apply_overrides(item, overrides)]

def _rhythm_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in sorted((root / "drafts" / "compositions").glob("*_composition.json"))[:250]:
        payload = read_json_file(path)
        if not payload:
            continue
        scene_id = str(payload.get("scene_id") or path.stem.replace("_composition", ""))
        rhythm = payload.get("narrative_rhythm") if isinstance(payload.get("narrative_rhythm"), dict) else {}
        bridge = payload.get("scene_bridge") if isinstance(payload.get("scene_bridge"), dict) else {}
        contract = payload.get("narrative_rhythm_contract") if isinstance(payload.get("narrative_rhythm_contract"), dict) else {}
        item = {
            "kind": "rhythm",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)} 的叙事节奏",
            "subtitle": "节奏与场景衔接",
            "path": _rel(path, root),
            "status": str(contract.get("status") or "composition"),
            "badges": [str(rhythm.get("rhythm_role") or "mixed"), str(rhythm.get("pace") or "balanced"), str(contract.get("source") or "composition")],
            "excerpt": str(rhythm.get("reader_effect") or rhythm.get("scene_turn") or bridge.get("outgoing_hook") or "这个场景还没有显式节奏转折说明。"),
            "facts": [
                {"label": "场景功能", "value": _display_list_value(rhythm.get("scene_function")) or rhythm.get("rhythm_role") or "未填写"},
                {"label": "节奏定位", "value": rhythm.get("pace") or "balanced"},
                {"label": "叙事密度", "value": rhythm.get("density") or "medium"},
                {"label": "本场转折", "value": rhythm.get("scene_turn") or "未填写"},
                {"label": "读者效果", "value": rhythm.get("reader_effect") or "未填写"},
                {"label": "叙述距离", "value": rhythm.get("narrative_distance") or "medium"},
                {"label": "入场压力", "value": bridge.get("incoming_pressure") or "未填写"},
                {"label": "承接上场", "value": _display_list_value(bridge.get("incoming_from_previous")) or _display_list_value(bridge.get("carryover_from_previous")) or "未填写"},
                {"label": "出场钩子", "value": _display_hooks(bridge.get("outgoing_hooks")) or bridge.get("outgoing_hook") or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    if items:
        return items
    for path in sorted((root / "scenes").glob("*.yaml"))[:250]:
        text = _read_text(path)
        scene_id = scalar_from_yaml_text(text, "scene_id") or path.stem
        turn = nested_scalar_from_yaml_text(text, "narrative_rhythm", "scene_turn")
        hook = nested_scalar_from_yaml_text(text, "scene_bridge", "outgoing_hook")
        if not turn and not hook:
            continue
        item = {
            "kind": "rhythm",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)} 的叙事节奏",
            "subtitle": "scene.yaml 节奏字段",
            "path": _rel(path, root),
            "status": "scene",
            "badges": ["scene.yaml"],
            "excerpt": turn or hook,
            "facts": [
                {"label": "本场转折", "value": turn or "未填写"},
                {"label": "出场钩子", "value": hook or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items
