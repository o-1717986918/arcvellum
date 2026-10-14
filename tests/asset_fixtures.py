"""Synthetic candidate fixtures used only by gate tests; never shipped in the Engine."""
from pathlib import Path
import re
from typing import Any

def _source_paths(source: Path | None) -> list[str]:
    return [str(source)] if source else ["project_brief"]

def candidate_fixture(asset_type: str, candidate_id: str, root: Path, brief: str, target_id: str, source: Path | None) -> dict[str, Any]:
    title = _project_title(root)
    source_paths = _source_paths(source)
    if asset_type == "character":
        character_id = _safe_id(target_id or "agent_character")
        return {
            "schema": "literary-engineering-workbench/character-profile-candidate/v1",
            "candidate_id": candidate_id,
            "character_id": character_id,
            "name": "候选角色",
            "role": "主角候选",
            "identity": {"age": "", "gender": "", "occupation": "待定", "background": brief or "由 Agent 候选生成。"},
            "background_story": {
                "summary": "一次早年的失误让此人习惯在关键选择前先确认他人会付出的代价。",
                "formative_events": ["早年误判导致重要关系受损。"],
                "behavior_influences": ["遇到风险时先保护同伴。", "对旧线索保持异常克制。"],
                "reveal_policy": "implicit_only",
            },
            "bdi": {"belief": ["真相总会留下结构性痕迹。"], "desire": ["找到被隐藏的因果链。"], "intention": ["在不破坏同伴安全的前提下推进调查。"]},
            "psychology": {"fear": ["牵连无辜者。"], "secret": ["曾经接触过关键线索。"], "wound": "害怕自己的判断再次伤人。", "mask": "冷静克制。", "moral_line": "不牺牲无辜者。"},
            "relationships": [],
            "speech_style": {"vocabulary": "克制、具体。", "rhythm": "短句较多。", "taboo_words": [], "signature_patterns": []},
            "arc": {"current_stage": "回避卷入", "expected_change": "主动承担代价", "required_trigger_events": ["同伴受到现实威胁。"]},
            "state": {"location": "", "health": "正常", "resources": [], "known_facts": [], "unknown_facts": []},
            "risks": ["需要人工确认是否适合正式角色阵容。"],
            "source_paths": source_paths,
            "promotion_notes": "晋升后写入 characters/{character_id}.yaml。",
        }
    if asset_type == "background-story":
        return {
            "schema": "literary-engineering-workbench/background-story-candidate/v1",
            "candidate_id": candidate_id,
            "target_character_id": _safe_id(target_id or "agent_character"),
            "summary": "旧日失误形成了持续的保护性控制欲。",
            "formative_events": ["误读一次求助信号，导致同伴承担后果。"],
            "hidden_wound": "害怕自己越主动，别人越危险。",
            "desire": "证明自己能在不伤害他人的情况下接近真相。",
            "fear": "再次因为判断过快而伤害重要关系。",
            "shame_or_secret": "他知道一个尚未公开的关键线索。",
            "behavior_influences": ["说话前会观察对方反应。", "危险中优先切断牵连。"],
            "reveal_policy": "implicit_only",
            "risks": ["不得在正文中整段解释背景故事。"],
            "source_paths": source_paths,
            "promotion_notes": "晋升后更新目标角色 background_story。",
        }
    if asset_type == "relationship":
        return {
            "schema": "literary-engineering-workbench/relationship-graph-candidate/v1",
            "candidate_id": candidate_id,
            "relationships": [{"from": "agent_character", "to": "ally", "type": "mutual_guarded_trust"}],
            "tensions": ["信任存在，但双方都隐瞒关键信息。"],
            "alliances": ["共同调查同一条被遮蔽的线索。"],
            "hidden_links": ["过去事件把两人的恐惧连在一起。"],
            "risks": ["关系图晋升后仍需人物档案同步。"],
            "source_paths": source_paths,
            "promotion_notes": "晋升后写入 plot/relationship_graph.json。",
        }
    if asset_type == "world":
        return {
            "schema": "literary-engineering-workbench/world-rules-candidate/v1",
            "candidate_id": candidate_id,
            "world_name": title,
            "core_rules": ["公开记录并不等于真实历史。", "资源流向决定角色能否接近真相。"],
            "constraints": ["不能通过随意新增技术或权力解决冲突。"],
            "power_sources": ["档案控制权", "公共叙事权", "稀缺通行资源"],
            "social_order": ["表层秩序稳定，底层信息被分级封存。"],
            "taboos": ["直接询问旧事件会触发组织性回避。"],
            "history_pressure": ["一次未被公开解释的旧事件仍在影响当下制度。"],
            "open_questions": ["旧事件由谁主动掩盖。"],
            "risks": ["世界规则不能覆盖已有 canon。"],
            "source_paths": source_paths,
            "promotion_notes": "晋升后写入 canon/world_rules.yaml。",
        }
    if asset_type == "location":
        location_id = _safe_id(target_id or "agent_location")
        return {
            "schema": "literary-engineering-workbench/location-candidate/v1",
            "candidate_id": candidate_id,
            "location_id": location_id,
            "name": "候选地点",
            "type": "关键场景地点",
            "description": brief or "一个能承载线索、误读和压力选择的地点。",
            "rules": ["进入此地会暴露角色的真实优先级。"],
            "resources": ["旧档案", "受限通道"],
            "story_functions": ["制造选择压力", "暴露关系裂痕"],
            "risks": ["地点规则需与世界观候选一致。"],
            "source_paths": source_paths,
            "promotion_notes": "晋升后写入 canon/locations.yaml。",
        }
    if asset_type == "organization":
        organization_id = _safe_id(target_id or "agent_organization")
        return {
            "schema": "literary-engineering-workbench/organization-candidate/v1",
            "candidate_id": candidate_id,
            "organization_id": organization_id,
            "name": "候选组织",
            "type": "压力来源",
            "public_goal": "维护表层秩序。",
            "hidden_goal": "控制旧事件解释权。",
            "resources": ["档案", "通行许可", "舆论渠道"],
            "conflicts": ["与主角追索真相的目标冲突。"],
            "risks": ["组织动机不能成为万能解释。"],
            "source_paths": source_paths,
            "promotion_notes": "晋升后写入 canon/organizations.yaml。",
        }
    return {
        "schema": "literary-engineering-workbench/plot-outline-candidate/v1",
        "candidate_id": candidate_id,
        "title": title,
        "premise": brief or _project_premise(root),
        "central_conflict": "角色追索被遮蔽的因果链，同时必须保护被牵连的人。",
        "acts": ["建立异常秩序", "揭开旧事件压力", "付出代价并重排关系"],
        "chapters": [{"chapter_id": "chapter_0001", "goal": "建立主角与核心谜团。"}],
        "scene_list": [
            {
                "scene_id": "scene_0001",
                "chapter_id": "chapter_0001",
                "goal": "让主角第一次主动接近核心线索。",
                "participants": ["agent_character"],
                "conflict": "真相与同伴安全不可兼得。",
            }
        ],
        "character_arcs": ["主角从回避承担转向主动选择代价。"],
        "foreshadowing": ["旧档案中的缺页将在第二阶段回收。"],
        "risks": ["大纲晋升后需重新运行 canon-lint。"],
        "source_paths": source_paths,
        "promotion_notes": "晋升后写入 plot/outline.md，并可生成 scene yaml。",
    }

def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", value.strip()).strip("_")
    return cleaned or "asset"

def _project_title(root: Path) -> str:
    text = (root / "project.yaml").read_text(encoding="utf-8", errors="ignore") if (root / "project.yaml").exists() else ""
    match = re.search(r"title:\s*(.+)", text)
    return match.group(1).strip().strip('"') if match else root.name

def _project_premise(root: Path) -> str:
    text = (root / "project.yaml").read_text(encoding="utf-8", errors="ignore") if (root / "project.yaml").exists() else ""
    match = re.search(r"premise:\s*(.+)", text)
    return match.group(1).strip().strip('"') if match else ""
