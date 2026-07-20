"""Agent-created candidate assets for project seeding and worldbuilding."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_provider import run_agent_task
from .agent_schema import load_schema_spec, validate_agent_run, validate_payload
from .resources import engine_path


ASSET_SCHEMA_NAMES = {
    "character": "character_profile.v1",
    "background-story": "background_story.v1",
    "relationship": "relationship_graph.v1",
    "world": "world_rules.v1",
    "location": "location.v1",
    "organization": "organization.v1",
    "outline": "plot_outline.v1",
    "chapter-plan": "plot_outline.v1",
    "scene-list": "plot_outline.v1",
}

ASSET_CANDIDATE_DIRS = {
    "character": Path("characters/candidates"),
    "background-story": Path("characters/candidates/background_stories"),
    "relationship": Path("plot/candidates/relationships"),
    "world": Path("canon/candidates/world_rules"),
    "location": Path("canon/candidates/locations"),
    "organization": Path("canon/candidates/organizations"),
    "outline": Path("plot/candidates/outlines"),
    "chapter-plan": Path("plot/candidates/outlines"),
    "scene-list": Path("plot/candidates/outlines"),
}

PROMOTABLE_GROUPS = {
    "character": {"character", "background-story", "relationship"},
    "world": {"world", "location", "organization"},
    "outline": {"outline", "chapter-plan", "scene-list"},
}

ASSET_TYPES = tuple(ASSET_SCHEMA_NAMES)


@dataclass(frozen=True)
class AssetCreationResult:
    project_root: Path
    asset_type: str
    candidate_id: str
    candidate_path: Path
    report_path: Path
    run_dir: Path
    validation_path: Path
    status: str


@dataclass(frozen=True)
class CandidateReviewResult:
    project_root: Path
    candidate_path: Path
    report_path: Path
    json_path: Path
    agent_run_dir: Path
    status: str
    error_count: int
    warning_count: int


@dataclass(frozen=True)
class AssetPromotionResult:
    project_root: Path
    candidate_path: Path
    manifest_path: Path
    report_path: Path
    output_paths: tuple[Path, ...]
    status: str


def create_asset_candidate(
    project_root: Path,
    *,
    asset_type: str,
    brief: str = "",
    provider: str = "auto",
    source: Path | None = None,
    target_id: str = "",
    output_dir: Path | None = None,
) -> AssetCreationResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    normalized = _normalize_asset_type(asset_type)
    schema_name = ASSET_SCHEMA_NAMES[normalized]
    candidate_id = _candidate_id(normalized, target_id or brief)
    source_text = _read_source(root, source)
    dry_payload = _dry_payload(normalized, candidate_id, root, brief, target_id, source)
    system_prompt = _system_prompt(normalized)
    user_prompt = _user_prompt(root, normalized, schema_name, brief, target_id, source_text)
    run_dir = output_dir or root / "agents" / "runs" / candidate_id
    run_result = run_agent_task(
        root,
        agent_id=f"{normalized}-creator",
        task=f"create-{normalized}-candidate",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        provider=provider,
        output_dir=run_dir,
        metadata={"asset_type": normalized, "schema_name": schema_name, "target_id": target_id},
        dry_run_output=dry_payload,
    )
    parsed_output_path = run_result.run_dir / "parsed_output.json"
    payload = json.loads(parsed_output_path.read_text(encoding="utf-8"))
    payload = _normalize_asset_payload_for_schema(
        payload,
        asset_type=normalized,
        schema_name=schema_name,
        candidate_id=candidate_id,
        source=source,
    )
    parsed_output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_agent_run(root, run_dir=run_result.run_dir, schema_name=schema_name)
    payload["asset_type"] = normalized
    payload["agent_run_dir"] = _rel_str(run_result.run_dir, root)
    payload["schema_validation"] = _rel_str(validation.validation_path, root)
    payload["candidate_status"] = "ready_for_review" if validation.status == "pass" else "needs_repair"
    payload["created_at"] = _now()

    candidate_path = _candidate_path(root, normalized, candidate_id)
    report_path = candidate_path.with_suffix(".md")
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_candidate_report(payload, validation.status), encoding="utf-8")
    return AssetCreationResult(root, normalized, candidate_id, candidate_path, report_path, run_result.run_dir, validation.validation_path, validation.status)


def list_asset_candidates(project_root: Path, asset_type: str = "") -> list[dict[str, object]]:
    root = project_root.resolve()
    selected = [_normalize_asset_type(asset_type)] if asset_type else list(ASSET_CANDIDATE_DIRS)
    items: list[dict[str, object]] = []
    seen: set[Path] = set()
    for item_type in selected:
        folder = root / ASSET_CANDIDATE_DIRS[item_type]
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            if path in seen:
                continue
            seen.add(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "asset_type": payload.get("asset_type", item_type),
                    "candidate_id": payload.get("candidate_id", path.stem),
                    "path": _rel_str(path, root),
                    "status": payload.get("candidate_status", ""),
                    "title": _candidate_title(payload),
                    "created_at": payload.get("created_at", ""),
                }
            )
    return items


def review_candidate_asset(project_root: Path, candidate: str | Path, provider: str = "auto") -> CandidateReviewResult:
    root = project_root.resolve()
    candidate_path = _resolve_candidate(root, candidate)
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    asset_type = _normalize_asset_type(str(payload.get("asset_type") or _infer_type_from_path(root, candidate_path)))
    schema_name = ASSET_SCHEMA_NAMES[asset_type]
    errors, warnings = validate_payload(payload, schema_name)
    candidate_id = str(payload.get("candidate_id") or candidate_path.stem)
    review_dir = root / "agents" / "runs" / f"{candidate_id}-asset-review"
    dry_review = {
        "schema": "literary-engineering-workbench/agent-output/v0.1",
        "agent_id": "asset-reviewer",
        "task": "review-candidate-asset",
        "status": "dry_run",
        "findings": [
            {
                "kind": "schema",
                "severity": "blocking" if errors else "info",
                "message": f"schema errors={len(errors)}, warnings={len(warnings)}",
            }
        ],
        "recommendations": [
            "候选资产只能在人工 approve 后晋升为正式项目文件。",
            "晋升后仍需运行 canon-lint 或相关章节审查。",
        ],
    }
    run = run_agent_task(
        root,
        agent_id="asset-reviewer",
        task="review-candidate-asset",
        system_prompt="You review candidate literary-engineering assets. Output JSON using generic_agent_output.v1.",
        user_prompt=f"""Review this candidate asset for canon safety, character logic, originality, and promotion risk.

Candidate:
```json
{json.dumps(payload, ensure_ascii=False, indent=2)[:12000]}
```
""",
        provider=provider,
        output_dir=review_dir,
        metadata={"candidate": _rel_str(candidate_path, root), "schema_name": schema_name},
        dry_run_output=dry_review,
    )
    status = "pass" if not errors else "failed"
    review_path = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    json_path = review_path.with_suffix(".json")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
        "candidate": _rel_str(candidate_path, root),
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "status": status,
        "schema_name": schema_name,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "agent_run_dir": _rel_str(run.run_dir, root),
        "reviewed_at": _now(),
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_path.write_text(_render_review(data), encoding="utf-8")
    return CandidateReviewResult(root, candidate_path, review_path, json_path, run.run_dir, status, len(errors), len(warnings))


def promote_candidate_asset(
    project_root: Path,
    candidate: str | Path,
    *,
    group: str = "",
    approval_run_id: str = "",
    allow_unapproved: bool = False,
) -> AssetPromotionResult:
    root = project_root.resolve()
    candidate_path = _resolve_candidate(root, candidate)
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    asset_type = _normalize_asset_type(str(payload.get("asset_type") or _infer_type_from_path(root, candidate_path)))
    if group:
        _validate_group(group, asset_type)
    schema_name = ASSET_SCHEMA_NAMES[asset_type]
    errors, _warnings = validate_payload(payload, schema_name)
    if errors:
        raise ValueError(f"candidate schema validation failed: {len(errors)} errors")
    candidate_id = str(payload.get("candidate_id") or candidate_path.stem)
    if not allow_unapproved and not _has_approval(root, approval_run_id or candidate_id):
        raise RuntimeError("candidate promotion requires an approve record or --allow-unapproved")
    output_paths = tuple(_write_promoted_asset(root, asset_type, payload))
    promotion_dir = root / "workflow" / "asset_promotions"
    promotion_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = promotion_dir / f"{candidate_id}_promotion.json"
    report_path = promotion_dir / f"{candidate_id}_promotion.md"
    data = {
        "schema": "literary-engineering-workbench/candidate-asset-promotion/v0.1",
        "candidate": _rel_str(candidate_path, root),
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "status": "promoted",
        "approval_run_id": approval_run_id or candidate_id,
        "allow_unapproved": allow_unapproved,
        "outputs": [_rel_str(path, root) for path in output_paths],
        "promoted_at": _now(),
    }
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_promotion(data), encoding="utf-8")
    return AssetPromotionResult(root, candidate_path, manifest_path, report_path, output_paths, "promoted")


def create_project_seed_candidates(project_root: Path, *, provider: str = "auto", brief: str = "") -> list[AssetCreationResult]:
    results = [
        create_asset_candidate(project_root, asset_type="world", brief=brief, provider=provider),
        create_asset_candidate(project_root, asset_type="character", brief=brief, provider=provider),
        create_asset_candidate(project_root, asset_type="outline", brief=brief, provider=provider),
    ]
    return results


def _normalize_asset_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "background": "background-story",
        "background_story": "background-story",
        "relationships": "relationship",
        "world-rules": "world",
        "chapter": "chapter-plan",
        "scenes": "scene-list",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ASSET_SCHEMA_NAMES:
        raise ValueError(f"unknown asset type: {value}. valid: {', '.join(ASSET_TYPES)}")
    return normalized


def _candidate_path(root: Path, asset_type: str, candidate_id: str) -> Path:
    return root / ASSET_CANDIDATE_DIRS[asset_type] / f"{candidate_id}.json"


def _candidate_id(asset_type: str, seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(seed)[:28] or "candidate"
    return f"{asset_type}-{slug}-{stamp}"


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return text or "asset"


def _read_source(root: Path, source: Path | None) -> str:
    if source is None:
        return ""
    path = source if source.is_absolute() else root / source
    if not path.exists():
        raise FileNotFoundError(f"source not found: {path}")
    return path.read_text(encoding="utf-8", errors="ignore")


def _source_paths(source: Path | None) -> list[str]:
    return [str(source)] if source else ["project_brief"]


def _normalize_asset_payload_for_schema(
    payload: dict[str, Any],
    *,
    asset_type: str,
    schema_name: str,
    candidate_id: str,
    source: Path | None,
) -> dict[str, Any]:
    """Fill system-owned candidate metadata before schema validation."""
    result = _flatten_nested_asset_payload(payload, asset_type)
    spec = load_schema_spec(schema_name)
    result["schema"] = str(spec.get("schema_value") or schema_name)
    result["candidate_id"] = candidate_id
    result["source_paths"] = _merged_source_paths(result.get("source_paths"), _source_paths(source))
    if not isinstance(result.get("promotion_notes"), str):
        result["promotion_notes"] = _promotion_notes(asset_type)
    return result


def _flatten_nested_asset_payload(payload: dict[str, Any], asset_type: str) -> dict[str, Any]:
    result = dict(payload)
    nested_keys = {
        "character": ["character"],
        "background-story": ["background_story", "background"],
        "relationship": ["relationship", "relationship_graph"],
        "world": ["world", "world_rules"],
        "location": ["location"],
        "organization": ["organization"],
        "outline": ["outline", "plot_outline", "chapter_plan", "scene_list"],
        "chapter-plan": ["outline", "plot_outline", "chapter_plan"],
        "scene-list": ["outline", "plot_outline", "scene_list"],
    }.get(asset_type, [])
    for key in nested_keys:
        nested = payload.get(key)
        if not isinstance(nested, dict):
            continue
        for field, value in nested.items():
            result.setdefault(field, value)
    return result


def _merged_source_paths(existing: Any, required: list[str]) -> list[str]:
    values: list[str] = []
    if isinstance(existing, list):
        values.extend(str(item).strip() for item in existing if str(item).strip())
    for item in required:
        value = str(item).strip()
        if value:
            values.append(value)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _promotion_notes(asset_type: str) -> str:
    if asset_type == "character":
        return "晋升后写入 characters/{character_id}.yaml。"
    if asset_type == "background-story":
        return "晋升后更新目标角色 background_story。"
    if asset_type == "relationship":
        return "晋升后写入 plot/relationship_graph.json。"
    if asset_type == "world":
        return "晋升后写入 canon/world_rules.yaml。"
    if asset_type == "location":
        return "晋升后写入 canon/locations.yaml。"
    if asset_type == "organization":
        return "晋升后写入 canon/organizations.yaml。"
    return "晋升后写入 plot/outline.md，并可生成 scene yaml。"


def _project_context(root: Path) -> str:
    parts = []
    for rel in ["project.yaml", "canon/world_rules.yaml", "plot/outline.md", "characters/_template.yaml"]:
        path = root / rel
        if path.exists():
            parts.append(f"## {rel}\n\n{path.read_text(encoding='utf-8', errors='ignore')[:4000]}")
    return "\n\n".join(parts)


def _system_prompt(asset_type: str) -> str:
    if asset_type in {"character", "background-story", "relationship"}:
        template = "character_creation_system.md"
    elif asset_type in {"world", "location", "organization"}:
        template = "worldbuilding_system.md"
    else:
        template = "outline_creation_system.md"
    path = engine_path("templates", "prompts", template)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "You create structured literary-engineering candidate assets. Output JSON only."


def _user_prompt(root: Path, asset_type: str, schema_name: str, brief: str, target_id: str, source_text: str) -> str:
    if asset_type in {"character", "background-story", "relationship"}:
        template = "character_creation_user.md"
    elif asset_type in {"world", "location", "organization"}:
        template = "worldbuilding_user.md"
    else:
        template = "outline_creation_user.md"
    path = engine_path("templates", "prompts", template)
    template_text = path.read_text(encoding="utf-8") if path.exists() else ""
    return f"""{template_text}

Asset type: {asset_type}
Schema name: {schema_name}
Target id: {target_id or "n/a"}
Creative brief: {brief or "Use the project premise and existing files."}

Project context:
```text
{_project_context(root)[:12000]}
```

Source material:
```text
{source_text[:8000] or "No extra source file provided."}
```

Return JSON only. Do not write confirmed canon. Mark risks and source_paths.
"""


def _dry_payload(asset_type: str, candidate_id: str, root: Path, brief: str, target_id: str, source: Path | None) -> dict[str, Any]:
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


def _write_promoted_asset(root: Path, asset_type: str, payload: dict[str, Any]) -> list[Path]:
    if asset_type == "character":
        character_id = _safe_id(str(payload.get("character_id") or "agent_character"))
        path = root / "characters" / f"{character_id}.yaml"
        path.write_text(_render_yaml(payload, exclude={"schema", "candidate_id", "asset_type", "agent_run_dir", "schema_validation", "candidate_status", "created_at", "risks", "source_paths", "promotion_notes"}), encoding="utf-8")
        return [path]
    if asset_type == "background-story":
        character_id = _safe_id(str(payload.get("target_character_id") or "agent_character"))
        path = root / "characters" / f"{character_id}.yaml"
        existing = path.read_text(encoding="utf-8") if path.exists() else f"character_id: {character_id}\nname: \"\"\nrole: \"\"\n"
        block = {
            "background_story": {
                "summary": payload.get("summary", ""),
                "formative_events": payload.get("formative_events", []),
                "hidden_wound": payload.get("hidden_wound", ""),
                "desire": payload.get("desire", ""),
                "fear": payload.get("fear", ""),
                "shame_or_secret": payload.get("shame_or_secret", ""),
                "behavior_influences": payload.get("behavior_influences", []),
                "reveal_policy": payload.get("reveal_policy", "implicit_only"),
            }
        }
        path.write_text(_replace_top_level_block(existing, "background_story", _render_yaml(block)), encoding="utf-8")
        return [path]
    if asset_type == "relationship":
        path = root / "plot" / "relationship_graph.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return [path]
    if asset_type == "world":
        path = root / "canon" / "world_rules.yaml"
        promoted = {
            "world_name": payload.get("world_name", ""),
            "rules": payload.get("core_rules", []),
            "constraints": payload.get("constraints", []),
            "power_sources": payload.get("power_sources", []),
            "social_order": payload.get("social_order", []),
            "taboos": payload.get("taboos", []),
            "history_pressure": payload.get("history_pressure", []),
            "open_questions": payload.get("open_questions", []),
        }
        path.write_text(_render_yaml(promoted), encoding="utf-8")
        return [path]
    if asset_type == "location":
        path = root / "canon" / "locations.yaml"
        path.write_text(_render_yaml({"locations": [_public_payload(payload)]}), encoding="utf-8")
        return [path]
    if asset_type == "organization":
        path = root / "canon" / "organizations.yaml"
        path.write_text(_render_yaml({"organizations": [_public_payload(payload)]}), encoding="utf-8")
        return [path]
    path = root / "plot" / "outline.md"
    path.write_text(_render_outline(payload), encoding="utf-8")
    outputs = [path]
    for scene in payload.get("scene_list", []) or []:
        if not isinstance(scene, dict):
            continue
        scene_id = _safe_id(str(scene.get("scene_id") or "scene_candidate"))
        scene_path = root / "scenes" / f"{scene_id}.yaml"
        scene_payload = {
            "scene_id": scene_id,
            "chapter_id": scene.get("chapter_id", "chapter_0001"),
            "location": scene.get("location", ""),
            "participants": scene.get("participants", []),
            "scene_goal": scene.get("goal", ""),
            "conflict": scene.get("conflict", ""),
            "input_state": [],
            "output_state": [],
            "review": {"status": "planned"},
        }
        scene_path.write_text(_render_yaml(scene_payload), encoding="utf-8")
        outputs.append(scene_path)
    return outputs


def _public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"schema", "candidate_id", "asset_type", "agent_run_dir", "schema_validation", "candidate_status", "created_at", "risks", "source_paths", "promotion_notes"}
    }


def _render_yaml(data: dict[str, Any], indent: int = 0, exclude: set[str] | None = None) -> str:
    lines: list[str] = []
    excluded = exclude or set()
    for key, value in data.items():
        if key in excluded:
            continue
        prefix = " " * indent
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_render_yaml(value, indent + 2).rstrip())
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            if not value:
                lines[-1] += " []"
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    lines.append(_render_yaml(item, indent + 4).rstrip())
                else:
                    lines.append(f"{prefix}  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return "\n".join(lines).rstrip() + "\n"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _replace_top_level_block(existing: str, key: str, rendered_block: str) -> str:
    lines = existing.splitlines()
    output: list[str] = []
    index = 0
    replaced = False
    while index < len(lines):
        line = lines[index]
        if line.startswith(f"{key}:"):
            output.extend(rendered_block.rstrip().splitlines())
            replaced = True
            index += 1
            while index < len(lines) and (lines[index].startswith(" ") or not lines[index].strip()):
                index += 1
            continue
        output.append(line)
        index += 1
    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.extend(rendered_block.rstrip().splitlines())
    return "\n".join(output).rstrip() + "\n"


def _render_outline(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload.get('title', '候选大纲')}",
        "",
        "## Premise",
        "",
        str(payload.get("premise", "")),
        "",
        "## Central Conflict",
        "",
        str(payload.get("central_conflict", "")),
        "",
        "## Acts",
        "",
    ]
    for item in payload.get("acts", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Chapters", ""])
    for item in payload.get("chapters", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Scene List", ""])
    for item in payload.get("scene_list", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Foreshadowing", ""])
    for item in payload.get("foreshadowing", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def _render_candidate_report(payload: dict[str, Any], validation_status: str) -> str:
    return "\n".join(
        [
            f"# Candidate Asset：{payload.get('candidate_id', '')}",
            "",
            f"- Type：`{payload.get('asset_type', '')}`",
            f"- Status：`{payload.get('candidate_status', '')}`",
            f"- Schema Validation：`{validation_status}`",
            f"- Agent Run：`{payload.get('agent_run_dir', '')}`",
            "",
            "## Summary",
            "",
            _candidate_title(payload),
            "",
            "## Risks",
            "",
            *[f"- {item}" for item in payload.get("risks", []) or ["需人工审查。"]],
            "",
            "## Promotion Boundary",
            "",
            "- 本候选资产不得自动写入正式 canon、characters 或 plot。",
            "- 晋升前必须有 schema 审查、语义审查和人工 approve 记录。",
        ]
    ) + "\n"


def _render_review(data: dict[str, Any]) -> str:
    lines = [
        f"# Candidate Asset Review：{data.get('candidate_id', '')}",
        "",
        f"- Type：`{data.get('asset_type', '')}`",
        f"- Status：`{data.get('status', '')}`",
        f"- Errors：{data.get('error_count', 0)}",
        f"- Warnings：{data.get('warning_count', 0)}",
        f"- Agent Run：`{data.get('agent_run_dir', '')}`",
        "",
        "## Errors",
        "",
    ]
    errors = data.get("errors", []) or []
    lines.extend([f"- {item}" for item in errors] or ["- 无。"])
    lines.extend(["", "## Warnings", ""])
    warnings = data.get("warnings", []) or []
    lines.extend([f"- {item}" for item in warnings] or ["- 无。"])
    return "\n".join(lines) + "\n"


def _render_promotion(data: dict[str, Any]) -> str:
    lines = [
        f"# Candidate Asset Promotion：{data.get('candidate_id', '')}",
        "",
        f"- Type：`{data.get('asset_type', '')}`",
        f"- Status：`{data.get('status', '')}`",
        f"- Approval Run：`{data.get('approval_run_id', '')}`",
        f"- Allow Unapproved：`{str(data.get('allow_unapproved', '')).lower()}`",
        "",
        "## Outputs",
        "",
    ]
    for item in data.get("outputs", []) or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines) + "\n"


def _resolve_candidate(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.exists():
        return path.resolve()
    if not path.is_absolute():
        direct = (root / path).resolve()
        if direct.exists():
            return direct
    candidate_id = str(value)
    for folder in ASSET_CANDIDATE_DIRS.values():
        candidate = root / folder / f"{candidate_id}.json"
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"candidate asset not found: {value}")


def _infer_type_from_path(root: Path, path: Path) -> str:
    rel = _rel_str(path, root)
    for asset_type, folder in ASSET_CANDIDATE_DIRS.items():
        if rel.startswith(folder.as_posix()):
            return asset_type
    return "character"


def _validate_group(group: str, asset_type: str) -> None:
    normalized = group.strip().lower()
    if normalized not in PROMOTABLE_GROUPS:
        raise ValueError(f"unknown promotion group: {group}")
    if asset_type not in PROMOTABLE_GROUPS[normalized]:
        raise ValueError(f"{asset_type} cannot be promoted through {group} group")


def _has_approval(root: Path, run_id: str) -> bool:
    if not run_id:
        return False
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return False
    for line in index.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("run_id") == run_id and record.get("decision") == "approve":
            return True
    return False


def _candidate_title(payload: dict[str, Any]) -> str:
    return str(
        payload.get("name")
        or payload.get("title")
        or payload.get("world_name")
        or payload.get("summary")
        or payload.get("candidate_id")
        or "candidate asset"
    )


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
