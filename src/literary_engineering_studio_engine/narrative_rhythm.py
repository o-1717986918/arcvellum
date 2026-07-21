"""Narrative rhythm and scene-bridge contracts for scene generation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


RHYTHM_SCHEMA = "literary-engineering-workbench/narrative-rhythm-contract/v0.1"
RHYTHM_CURVE_SCHEMA = "literary-engineering-workbench/narrative-rhythm-curve/v0.1"


DEFAULT_RHYTHM = {
    "rhythm_role": "mixed",
    "pace": "balanced",
    "density": "medium",
    "scene_turn": "",
    "scene_function": [],
    "reader_effect": "",
    "paragraph_shape": "过场简短，关键选择细写；段落推进以行动、信息差和人物选择为主。",
    "density_mix": {
        "summary": "low",
        "action": "medium",
        "dialogue": "medium",
        "reflection": "low",
        "description": "low",
    },
    "dialogue_ratio": "medium",
    "action_ratio": "medium",
    "reflection_ratio": "low",
    "description_ratio": "low",
    "narrative_distance": "medium",
    "tension_curve": "",
    "texture_variety": "避免连续场景全是同一种材料；对话、动作、心理、环境、信息揭示应按场景功能变化。",
    "chapter_ending_policy": "",
    "slow_down_points": [],
    "speed_up_points": [],
    "avoid_flatness": "每段至少承担行动推进、信息改变、关系压力、选择代价或场景衔接之一。",
}


DEFAULT_BRIDGE = {
    "incoming_pressure": "",
    "incoming_from_previous": [],
    "reader_questions_carried": [],
    "carryover_from_previous": [],
    "outgoing_hooks": [],
    "outgoing_hook": "",
    "promise_payoff_items": [],
    "continuity_handshake": "结尾必须给下一场留下可接续的压力、问题、代价或未完成动作。",
}

GENERIC_PLACEHOLDER_FRAGMENTS = (
    "未填写",
    "未显式",
    "从 context packet",
    "给下一场留下问题",
    "承接上一场未解决压力",
    "登记本场新增",
)


def narrative_rhythm_contract(
    root: Path,
    scene_path: Path,
    composition_path: Path | None = None,
) -> dict[str, Any]:
    """Return the formal rhythm/bridge contract for one scene.

    The contract is intentionally tolerant for older projects: if no explicit
    rhythm or bridge fields exist, it returns a default contract with status
    ``defaulted`` instead of blocking legacy fixtures. New composition output
    writes explicit fields so formal route gates can treat it as ready.
    """

    root = root.resolve()
    scene_path = scene_path if scene_path.is_absolute() else root / scene_path
    scene_text = _read(scene_path)
    scene_id = _scene_id(scene_path, scene_text)
    composition_payload = _read_composition_payload(root, scene_id, composition_path)
    composition_rhythm = _dict_value(composition_payload.get("narrative_rhythm"))
    composition_bridge = _dict_value(composition_payload.get("scene_bridge"))
    scene_rhythm = _block_mapping(scene_text, "narrative_rhythm")
    scene_bridge = _block_mapping(scene_text, "scene_bridge")
    plan_payload = _read_json(root / "plot" / "rhythm_plan.json")
    plan_scenes = plan_payload.get("scenes") if isinstance(plan_payload.get("scenes"), dict) else {}
    plan_rhythm = plan_scenes.get(scene_id) if isinstance(plan_scenes.get(scene_id), dict) else {}
    # Composition is a derived planning artifact. A later formal scene-contract
    # task must be able to repair it before composition is rebuilt, and a user
    # rhythm plan remains the highest authority.
    rhythm = _merge_dict(DEFAULT_RHYTHM, composition_rhythm, scene_rhythm, plan_rhythm)
    bridge = _merge_dict(DEFAULT_BRIDGE, composition_bridge, scene_bridge)
    explicit = bool(composition_rhythm or composition_bridge or scene_rhythm or scene_bridge or plan_rhythm)
    missing_required = _missing_contract_fields(rhythm, bridge) if explicit else []
    status = "pass" if explicit and not missing_required else ("incomplete" if explicit else "defaulted")
    return {
        "schema": RHYTHM_SCHEMA,
        "scene_id": scene_id,
        "status": status,
        "source": "rhythm-plan" if plan_rhythm else _source_label(composition_rhythm, composition_bridge, scene_rhythm, scene_bridge),
        "plan_revision": int(plan_payload.get("revision") or 0),
        "plan_digest": str(plan_payload.get("digest") or ""),
        "message": _contract_message(explicit, missing_required),
        "missing_required": missing_required,
        "narrative_rhythm": rhythm,
        "scene_bridge": bridge,
        "generation_required": True,
        "review_required": True,
    }


def render_narrative_rhythm_contract(
    root: Path,
    scene_path: Path,
    composition_path: Path | None = None,
) -> str:
    contract = narrative_rhythm_contract(root, scene_path, composition_path)
    rhythm = contract.get("narrative_rhythm") if isinstance(contract.get("narrative_rhythm"), dict) else {}
    bridge = contract.get("scene_bridge") if isinstance(contract.get("scene_bridge"), dict) else {}
    density = rhythm.get("density_mix") if isinstance(rhythm.get("density_mix"), dict) else {}
    lines = [
        "# 本场景叙事节奏与场景桥接硬属性",
        "",
        f"- 状态：`{contract.get('status')}`",
        f"- 来源：{contract.get('source')}",
        f"- 信息：{contract.get('message')}",
        f"- 节奏定位：{rhythm.get('pace') or 'balanced'}",
        f"- 场景功能：{_join_list(rhythm.get('scene_function')) or rhythm.get('rhythm_role') or 'mixed'}",
        f"- 叙事密度：{rhythm.get('density') or 'medium'}",
        f"- 本场转折：{rhythm.get('scene_turn') or '未显式填写，生成时需从 scene_goal/conflict/branch 中提炼'}",
        f"- 读者效果：{rhythm.get('reader_effect') or '未填写，生成时需明确读者读完后的认知或情绪变化'}",
        f"- 叙述距离：{rhythm.get('narrative_distance') or 'medium'}",
        f"- 段落形态：{rhythm.get('paragraph_shape') or DEFAULT_RHYTHM['paragraph_shape']}",
        f"- 密度配比：摘要={density.get('summary', rhythm.get('summary_ratio', 'low'))}，行动={density.get('action', rhythm.get('action_ratio', 'medium'))}，对白={density.get('dialogue', rhythm.get('dialogue_ratio', 'medium'))}，思考={density.get('reflection', rhythm.get('reflection_ratio', 'low'))}，环境={density.get('description', rhythm.get('description_ratio', 'low'))}",
        f"- 需要放慢：{_join_list(rhythm.get('slow_down_points')) or '关键选择、后果落点'}",
        f"- 需要加速：{_join_list(rhythm.get('speed_up_points')) or '过场、重复说明、已知信息'}",
        f"- 张力曲线：{_render_tension_curve(rhythm.get('tension_curve')) or '未填写（必填：entry / peak / exit，均为 1-5）'}",
        f"- 质地变化：{rhythm.get('texture_variety') or DEFAULT_RHYTHM['texture_variety']}",
        f"- 章节结尾策略：{rhythm.get('chapter_ending_policy') or '若本场是章末，避免总用警句/反转句，按情绪余波、信息落点、行动启动、关系变化、静默或 cliffhanger 选择。'}",
        f"- 防扁平化：{rhythm.get('avoid_flatness') or DEFAULT_RHYTHM['avoid_flatness']}",
        f"- 入场压力：{bridge.get('incoming_pressure') or '承接上一场未解决压力'}",
        f"- 承接信息：{_join_list(bridge.get('incoming_from_previous')) or _join_list(bridge.get('carryover_from_previous')) or '从 context packet 和 branch selection 中提取'}",
        f"- 延续读者问题：{_join_list(bridge.get('reader_questions_carried')) or '从 Reader Question Ledger / reader_experience 中提取'}",
        f"- 出场钩子组：{_join_hooks(bridge.get('outgoing_hooks')) or bridge.get('outgoing_hook') or '给下一场留下问题、代价或未完成动作'}",
        f"- 出场钩子：{bridge.get('outgoing_hook') or '给下一场留下问题、代价或未完成动作'}",
        f"- 承诺/兑现项：{_join_hooks(bridge.get('promise_payoff_items')) or '登记本场新增、延迟或兑现的承诺/伏笔/物件/台词暗示'}",
        f"- 连续性握手：{bridge.get('continuity_handshake') or DEFAULT_BRIDGE['continuity_handshake']}",
        "",
        "执行要求：正文不得只平均铺陈事件。过场用短段快速过桥；高潮围绕人物选择、信息差、代价和行动后果放慢。场景开头必须接住入场压力，结尾必须交给下一场一个可继续推进的钩子。审查时必须判断场景功能是否成立，读者问题/承诺是否被管理，叙述距离是否避免持续贴脸解释心理。",
    ]
    return "\n".join(lines).strip() + "\n"


def rhythm_review_status(payload: dict[str, Any]) -> str:
    value = payload.get("narrative_rhythm_adherence") if isinstance(payload, dict) else None
    if not isinstance(value, dict):
        return ""
    return str(value.get("status") or "").strip().lower()


def normalize_tension_curve(value: object) -> dict[str, int] | None:
    """Normalize one scene's entry/peak/exit tension to the 1-5 scale."""

    if isinstance(value, dict):
        values = [_tension_number(value.get(key)) for key in ("entry", "peak", "exit")]
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        values = [_tension_number(item) for item in value[:3]]
    else:
        text = str(value or "").strip().lower()
        tokens = re.findall(r"[1-5]|very_low|very_high|low|medium|high|低|中|高", text)
        values = [_tension_number(item) for item in tokens[:3]] if len(tokens) >= 3 else []
    if len(values) != 3 or any(item is None for item in values):
        return None
    entry, peak, exit_value = (int(item) for item in values if item is not None)
    return {"entry": entry, "peak": peak, "exit": exit_value}


def analyze_narrative_rhythm_sequence(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit a chapter sequence without pretending numbers replace editorial judgment."""

    points: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        scene_id = str(scene.get("scene_id") or f"scene_{index + 1:04d}")
        curve = normalize_tension_curve(scene.get("tension_curve"))
        points.append({
            "scene_id": scene_id,
            "pace": str(scene.get("pace") or "").strip().lower(),
            "rhythm_role": str(scene.get("rhythm_role") or "").strip().lower(),
            "scene_function": _sequence_function(scene.get("scene_function")),
            "tension": curve,
        })
        if curve is None:
            issues.append(_curve_issue("missing_tension_curve", "blocking", [scene_id], "缺少可检查的 entry / peak / exit 张力曲线。"))

    _append_repetition_issues(points, "pace", "flat_pace_run", "连续场景采用同一种推进速度", issues)
    _append_repetition_issues(points, "rhythm_role", "flat_role_run", "连续场景承担同一种节奏角色", issues)

    valid = [point for point in points if point["tension"]]
    if len(valid) >= 3:
        peaks = [int(point["tension"]["peak"]) for point in valid]
        if max(peaks) - min(peaks) <= 1:
            issues.append(_curve_issue("flat_tension_band", "warning", [point["scene_id"] for point in valid], "章节峰值长期停留在同一窄区间，缺少蓄势、抬升与回落。"))
        for start in range(len(valid) - 2):
            run = valid[start:start + 3]
            if all(int(point["tension"]["peak"]) >= 4 and int(point["tension"]["exit"]) >= 3 for point in run):
                issues.append(_curve_issue("sustained_high_pressure", "warning", [point["scene_id"] for point in run], "连续三场保持高压且没有明显回落，读者容易疲劳。"))
        for previous, current in zip(valid, valid[1:]):
            gap = abs(int(previous["tension"]["exit"]) - int(current["tension"]["entry"]))
            if gap >= 3:
                issues.append(_curve_issue("tension_handoff_gap", "warning", [previous["scene_id"], current["scene_id"]], "相邻场景的出场与入场张力跳变过大，需要用转场或因果压力解释。"))

    blocking = sum(1 for issue in issues if issue["severity"] == "blocking")
    status = "incomplete" if blocking else ("needs_attention" if issues else "pass")
    return {
        "schema": RHYTHM_CURVE_SCHEMA,
        "status": status,
        "scene_count": len(points),
        "blocking_count": blocking,
        "warning_count": len(issues) - blocking,
        "points": points,
        "issues": issues,
    }


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_composition_payload(root: Path, scene_id: str, composition_path: Path | None) -> dict[str, Any]:
    if composition_path is None:
        composition_path = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    if composition_path.suffix.lower() == ".md":
        composition_path = composition_path.with_suffix(".json")
    path = composition_path if composition_path.is_absolute() else root / composition_path
    return _read_json(path)


def _scene_id(scene_path: Path, text: str) -> str:
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    if match:
        value = match.group(1).strip().strip("\"'")
        if value:
            return value
    return scene_path.stem


def _missing_contract_fields(rhythm: dict[str, Any], bridge: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _meaningful_value(rhythm.get("scene_function")):
        missing.append("narrative_rhythm.scene_function")
    if not _meaningful_value(rhythm.get("scene_turn")):
        missing.append("narrative_rhythm.scene_turn")
    if not _meaningful_value(rhythm.get("reader_effect")):
        missing.append("narrative_rhythm.reader_effect")
    if normalize_tension_curve(rhythm.get("tension_curve")) is None:
        missing.append("narrative_rhythm.tension_curve(entry/peak/exit:1-5)")
    if not _meaningful_value(bridge.get("incoming_pressure")):
        missing.append("scene_bridge.incoming_pressure")
    if not (_meaningful_value(bridge.get("outgoing_hook")) or _meaningful_value(bridge.get("outgoing_hooks"))):
        missing.append("scene_bridge.outgoing_hook")
    return missing


def _contract_message(explicit: bool, missing_required: list[str]) -> str:
    if not explicit:
        return "未显式配置，使用默认节奏/桥接契约；新正式场景建议写入 scene.yaml 或 composition。"
    if missing_required:
        return "叙事节奏/场景桥接已出现，但缺少关键硬属性：" + "，".join(missing_required)
    return "叙事节奏/场景桥接已显式配置。"


def _meaningful_value(value: object) -> bool:
    if isinstance(value, list):
        return any(_meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return any(_meaningful_value(item) for item in value.values())
    text = str(value or "").strip()
    if not text:
        return False
    return not any(fragment in text for fragment in GENERIC_PLACEHOLDER_FRAGMENTS)


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _merge_dict(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        for key, value in item.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _merge_dict(merged[key], value)
            elif value not in ("", [], {}, None):
                merged[key] = value
            elif key not in merged:
                merged[key] = value
    return merged


def _block_mapping(text: str, key: str) -> dict[str, Any]:
    match = re.search(rf"(?m)^([ \t]*){re.escape(key)}:[ \t]*$", text)
    if not match:
        return {}
    base_indent = len(match.group(1))
    block: list[str] = []
    for line in text[match.end() :].splitlines():
        if not line.strip():
            block.append(line)
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        if indent <= base_indent:
            break
        block.append(line)
    return _parse_mapping(block, base_indent + 2)


def _parse_mapping(lines: list[str], base_indent: int) -> dict[str, Any]:
    parsed, _ = _parse_mapping_at(lines, 0, base_indent)
    return parsed


def _parse_mapping_at(lines: list[str], start: int, base_indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    index = start
    while index < len(lines):
        raw = lines[index]
        if not raw.strip():
            index += 1
            continue
        indent = _indent(raw)
        stripped = raw.strip()
        if indent < base_indent:
            break
        if indent > base_indent or stripped.startswith("-") or ":" not in stripped:
            index += 1
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = _parse_scalar_or_inline(value)
            index += 1
            continue
        child_index = _next_content_index(lines, index + 1)
        if child_index is None or _indent(lines[child_index]) <= indent:
            result[key] = ""
            index += 1
            continue
        child_indent = _indent(lines[child_index])
        if lines[child_index].strip().startswith("-"):
            result[key], index = _parse_list_at(lines, child_index, child_indent)
        else:
            result[key], index = _parse_mapping_at(lines, child_index, child_indent)
    return result, index


def _parse_list_at(lines: list[str], start: int, list_indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    index = start
    while index < len(lines):
        raw = lines[index]
        if not raw.strip():
            index += 1
            continue
        indent = _indent(raw)
        stripped = raw.strip()
        if indent < list_indent:
            break
        if indent > list_indent:
            index += 1
            continue
        if not stripped.startswith("-"):
            break
        item_text = stripped[1:].strip()
        child_index = _next_content_index(lines, index + 1)
        has_child = child_index is not None and _indent(lines[child_index]) > indent
        if not item_text and has_child:
            child_indent = _indent(lines[child_index])
            if lines[child_index].strip().startswith("-"):
                item, index = _parse_list_at(lines, child_index, child_indent)
            else:
                item, index = _parse_mapping_at(lines, child_index, child_indent)
            result.append(item)
            continue
        if ":" in item_text and not item_text.startswith(("'", '"')):
            item = _parse_inline_pair(item_text)
            index += 1
            if has_child:
                child, new_index = _parse_mapping_at(lines, child_index, _indent(lines[child_index]))
                if isinstance(item, dict):
                    item.update(child)
                index = new_index
            result.append(item)
            continue
        result.append(_parse_scalar_or_inline(item_text))
        index += 1
    return result, index


def _parse_scalar_or_inline(value: str) -> object:
    value = value.strip().strip("\"'")
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("\"'") for item in value.strip("[]").split(",") if item.strip()]
    if value.startswith("{") and value.endswith("}"):
        result: dict[str, str] = {}
        for part in value.strip("{}").split(","):
            if ":" not in part:
                continue
            key, item = part.split(":", 1)
            result[key.strip().strip("\"'")] = item.strip().strip("\"'")
        return result
    return value


def _parse_inline_pair(value: str) -> dict[str, object]:
    key, item = value.split(":", 1)
    return {key.strip().strip("\"'"): _parse_scalar_or_inline(item.strip())}


def _next_content_index(lines: list[str], start: int) -> int | None:
    for index in range(start, len(lines)):
        if lines[index].strip():
            return index
    return None


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _source_label(
    composition_rhythm: dict[str, Any],
    composition_bridge: dict[str, Any],
    scene_rhythm: dict[str, Any],
    scene_bridge: dict[str, Any],
) -> str:
    if composition_rhythm or composition_bridge:
        return "composition"
    if scene_rhythm or scene_bridge:
        return "scene.yaml"
    return "default"


def _join_list(value: object) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _join_hooks(value: object) -> str:
    if not isinstance(value, list):
        return str(value or "")
    parts: list[str] = []
    for item in value:
        if isinstance(item, dict):
            hook_type = str(item.get("type") or "").strip()
            content = str(item.get("content") or item.get("summary") or "").strip()
            if hook_type and content:
                parts.append(f"{hook_type}: {content}")
            elif content:
                parts.append(content)
        else:
            text = str(item).strip()
            if text:
                parts.append(text)
    return "；".join(parts)


def _tension_number(value: object) -> int | None:
    labels = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5, "低": 2, "中": 3, "高": 4}
    text = str(value or "").strip().lower()
    if text in labels:
        return labels[text]
    try:
        number = int(float(text))
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 5 else None


def _render_tension_curve(value: object) -> str:
    curve = normalize_tension_curve(value)
    if curve is None:
        return str(value or "")
    return f"入场 {curve['entry']} → 峰值 {curve['peak']} → 出场 {curve['exit']}"


def _sequence_function(value: object) -> str:
    if isinstance(value, list):
        return " / ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _curve_issue(code: str, severity: str, scene_ids: list[str], message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "scene_ids": scene_ids, "message": message}


def _append_repetition_issues(
    points: list[dict[str, Any]],
    key: str,
    code: str,
    message: str,
    issues: list[dict[str, Any]],
) -> None:
    start = 0
    while start < len(points):
        value = str(points[start].get(key) or "")
        end = start + 1
        while value and end < len(points) and str(points[end].get(key) or "") == value:
            end += 1
        if value and end - start >= 3:
            run = points[start:end]
            issues.append(_curve_issue(code, "warning", [point["scene_id"] for point in run], f"{message}（{value}），需要证明这是有意设计而非平均化惯性。"))
        start = end
