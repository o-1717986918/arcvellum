"""User-managed, versioned narrative rhythm targets."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .narrative_rhythm import analyze_narrative_rhythm_sequence, narrative_rhythm_contract, normalize_tension_curve


RHYTHM_PLAN_SCHEMA = "literary-engineering-workbench/rhythm-plan/v0.2"
PACE_VALUES = {"slow", "slow_to_fast", "balanced", "fast_to_slow", "fast"}
ROLE_VALUES = {"setup", "transition", "information", "emotion", "conflict", "action", "turn", "aftermath", "mixed"}
DETAIL_LEVEL_VALUES = {"summary", "lean", "standard", "expanded", "set_piece"}

# The book profile is intentionally a small editorial instrument.  It tells the
# worker what kind of long-form reading experience the user wants without
# flattening the existing, scene-level rhythm contract into a template.
BOOK_PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "layered": {
        "arc": {"opening": 2, "ascent": 3, "midpoint": 4, "crisis": 3, "finale": 5},
        "breathing_interval": 3,
        "set_piece_ratio": 18,
        "narrative_distance": "varied",
        "ending_policy": "varied",
    },
    "balanced": {
        "arc": {"opening": 2, "ascent": 3, "midpoint": 4, "crisis": 4, "finale": 5},
        "breathing_interval": 2,
        "set_piece_ratio": 20,
        "narrative_distance": "balanced",
        "ending_policy": "varied",
    },
    "pulse": {
        "arc": {"opening": 3, "ascent": 4, "midpoint": 3, "crisis": 5, "finale": 5},
        "breathing_interval": 2,
        "set_piece_ratio": 26,
        "narrative_distance": "close_varied",
        "ending_policy": "momentum",
    },
    "contemplative": {
        "arc": {"opening": 2, "ascent": 2, "midpoint": 4, "crisis": 3, "finale": 4},
        "breathing_interval": 4,
        "set_piece_ratio": 14,
        "narrative_distance": "observant",
        "ending_policy": "afterglow",
    },
}
DEFAULT_BOOK_PROFILE_ID = "layered"


def rhythm_plan_path(root: Path) -> Path:
    return root.resolve() / "plot" / "rhythm_plan.json"


def load_rhythm_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    stored = _read_json(rhythm_plan_path(root))
    stored_scenes = stored.get("scenes") if isinstance(stored.get("scenes"), dict) else {}
    book_profile = normalize_book_profile(stored.get("book_profile"))
    entries: list[dict[str, Any]] = []
    for path in sorted((root / "scenes").glob("*.yaml")) if (root / "scenes").is_dir() else []:
        if path.name.startswith("_"):
            continue
        scene_id = _scalar(path.read_text(encoding="utf-8", errors="ignore"), "scene_id") or path.stem
        scene_text = path.read_text(encoding="utf-8", errors="ignore")
        chapter_id = _scalar(scene_text, "chapter_id") or "unassigned"
        volume_id = _scalar(scene_text, "volume_id") or _scalar(scene_text, "volume") or "unassigned"
        contract = narrative_rhythm_contract(root, path)
        rhythm = contract.get("narrative_rhythm") if isinstance(contract.get("narrative_rhythm"), dict) else {}
        curve = normalize_tension_curve(rhythm.get("tension_curve")) or {"entry": 2, "peak": 3, "exit": 2}
        stored_entry = stored_scenes.get(scene_id) if isinstance(stored_scenes.get(scene_id), dict) else {}
        stored_gap = stored_entry.get("spatial_time_gap_before") if stored_entry else None
        scene_gap = _scalar(scene_text, "spatial_time_gap_before")
        entries.append({
            "scene_id": scene_id,
            "volume_id": volume_id,
            "chapter_id": chapter_id,
            "title": _scalar(path.read_text(encoding="utf-8", errors="ignore"), "title") or scene_id,
            "pace": str(rhythm.get("pace") or "balanced"),
            "rhythm_role": str(rhythm.get("rhythm_role") or "mixed"),
            "scene_function": _strings(rhythm.get("scene_function")),
            "tension_curve": curve,
            "detail_level": str(rhythm.get("detail_level") or "standard"),
            "word_count_target": _integer(_scalar(scene_text, "word_count_target")),
            "timeline_order": _integer(_scalar(scene_text, "timeline_order")),
            "story_time": _scalar(scene_text, "story_time"),
            "spatial_time_gap_before": _positive_number(stored_gap if stored_gap not in (None, "") else scene_gap),
            "source": "rhythm-plan" if scene_id in stored_scenes else str(contract.get("source") or "default"),
        })
    chapters: dict[str, dict[str, Any]] = {}
    for chapter_id in sorted({str(entry["chapter_id"]) for entry in entries}):
        chapter_entries = [entry for entry in entries if entry["chapter_id"] == chapter_id]
        chapters[chapter_id] = analyze_narrative_rhythm_sequence(chapter_entries)
    volumes: dict[str, dict[str, Any]] = {}
    for volume_id in sorted({str(entry["volume_id"]) for entry in entries}):
        volume_entries = [entry for entry in entries if entry["volume_id"] == volume_id]
        volumes[volume_id] = analyze_narrative_rhythm_sequence(volume_entries)
    book_audit = analyze_narrative_rhythm_sequence(entries)
    macro = _book_macro(entries, book_profile)
    book_audit["macro"] = macro
    book_audit["issues"] = [*book_audit.get("issues", []), *macro["issues"]]
    if book_audit.get("status") == "pass" and macro["issues"]:
        book_audit["status"] = "needs_attention"
        book_audit["warning_count"] = int(book_audit.get("warning_count") or 0) + len(macro["issues"])
    return {
        "schema": RHYTHM_PLAN_SCHEMA,
        "revision": int(stored.get("revision") or 0),
        "digest": str(stored.get("digest") or ""),
        "updated_at": str(stored.get("updated_at") or ""),
        "entries": entries,
        "chapters": chapters,
        "volumes": volumes,
        "book": book_audit,
        "book_profile": book_profile,
        "stored": bool(stored),
    }


def save_rhythm_plan(
    root: Path,
    entries: list[dict[str, Any]],
    updated_by: str = "studio-user",
    book_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    known = {_scalar(path.read_text(encoding="utf-8", errors="ignore"), "scene_id") or path.stem for path in (root / "scenes").glob("*.yaml")}
    normalized: dict[str, dict[str, Any]] = {}
    for entry in entries:
        scene_id = str(entry.get("scene_id") or "").strip()
        if not scene_id or scene_id not in known:
            raise ValueError(f"unknown rhythm-plan scene: {scene_id or 'missing'}")
        pace = str(entry.get("pace") or "balanced").strip().lower()
        role = str(entry.get("rhythm_role") or "mixed").strip().lower()
        curve = normalize_tension_curve(entry.get("tension_curve"))
        if pace not in PACE_VALUES:
            raise ValueError(f"unsupported scene pace: {pace}")
        if role not in ROLE_VALUES:
            raise ValueError(f"unsupported rhythm role: {role}")
        detail_level = str(entry.get("detail_level") or "standard").strip().lower()
        if detail_level not in DETAIL_LEVEL_VALUES:
            raise ValueError(f"unsupported scene detail level: {detail_level}")
        if curve is None:
            raise ValueError(f"scene {scene_id} requires entry/peak/exit tension values from 1 to 5")
        time_gap = _positive_number(entry.get("spatial_time_gap_before"))
        normalized[scene_id] = {
            "pace": pace,
            "rhythm_role": role,
            "scene_function": _strings(entry.get("scene_function")),
            "tension_curve": curve,
            "detail_level": detail_level,
            # This is a projection-only editorial adjustment. It controls the
            # visual breathing room before the scene without rewriting the
            # project's authored story time or its reading order.
            "spatial_time_gap_before": time_gap,
        }
    previous = _read_json(rhythm_plan_path(root))
    normalized_profile = normalize_book_profile(book_profile if book_profile is not None else previous.get("book_profile"))
    digest = hashlib.sha256(json.dumps({"scenes": normalized, "book_profile": normalized_profile}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    previous_digest = str(previous.get("digest") or "")
    revision = int(previous.get("revision") or 0) + (1 if digest != previous_digest else 0)
    payload = {
        "schema": RHYTHM_PLAN_SCHEMA,
        "revision": revision,
        "digest": digest,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": updated_by,
        "book_profile": normalized_profile,
        "scenes": normalized,
    }
    _write_json_atomic(rhythm_plan_path(root), payload)
    return load_rhythm_plan(root)


def normalize_book_profile(value: object) -> dict[str, Any]:
    """Return a bounded, backward-compatible full-book rhythm intent."""

    supplied = value if isinstance(value, dict) else {}
    profile_id = str(supplied.get("profile_id") or DEFAULT_BOOK_PROFILE_ID).strip().lower()
    if profile_id not in BOOK_PROFILE_PRESETS:
        profile_id = DEFAULT_BOOK_PROFILE_ID
    defaults = BOOK_PROFILE_PRESETS[profile_id]
    raw_arc = supplied.get("arc") if isinstance(supplied.get("arc"), dict) else {}
    arc = {
        key: _tension(raw_arc.get(key), int(defaults["arc"][key]))
        for key in ("opening", "ascent", "midpoint", "crisis", "finale")
    }
    breathing_interval = _whole_number(supplied.get("breathing_interval"), int(defaults["breathing_interval"]), 1, 8)
    set_piece_ratio = _whole_number(supplied.get("set_piece_ratio"), int(defaults["set_piece_ratio"]), 5, 45)
    distance = str(supplied.get("narrative_distance") or defaults["narrative_distance"]).strip().lower()
    if distance not in {"balanced", "varied", "close_varied", "observant"}:
        distance = str(defaults["narrative_distance"])
    ending = str(supplied.get("ending_policy") or defaults["ending_policy"]).strip().lower()
    if ending not in {"varied", "momentum", "afterglow", "quiet"}:
        ending = str(defaults["ending_policy"])
    directive = str(supplied.get("directive") or "").strip()[:500]
    return {
        "profile_id": profile_id,
        "arc": arc,
        "breathing_interval": breathing_interval,
        "set_piece_ratio": set_piece_ratio,
        "narrative_distance": distance,
        "ending_policy": ending,
        "directive": directive,
    }


def _book_macro(entries: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    chapter_ids = _ordered_unique(entry.get("chapter_id") for entry in entries)
    expected = _interpolate_arc(profile["arc"], len(chapter_ids))
    actual: list[int] = []
    issues: list[dict[str, Any]] = []
    for chapter_id in chapter_ids:
        chapter_entries = [entry for entry in entries if entry.get("chapter_id") == chapter_id]
        peaks = [int((entry.get("tension_curve") or {}).get("peak") or 3) for entry in chapter_entries]
        actual.append(max(peaks, default=3))
    if len(actual) >= 4:
        mismatch = [chapter_ids[index] for index, value in enumerate(actual) if abs(value - expected[index]) >= 2]
        if len(mismatch) >= max(2, len(actual) // 3):
            issues.append(_macro_issue("macro_curve_drift", mismatch, "实际章节峰值长期偏离全书意图曲线；请确认是有意反转，还是需要调整重点场和张力分布。"))
        run = max(_high_pressure_run(actual), default=0)
        if run >= profile["breathing_interval"] + 2:
            issues.append(_macro_issue("macro_breathing_gap", chapter_ids, "高压章节连续过长，未按设定保留叙事呼吸与后果落点。"))
    scene_count = len(entries)
    set_pieces = sum(1 for entry in entries if entry.get("detail_level") == "set_piece")
    actual_ratio = round((set_pieces / scene_count) * 100) if scene_count else 0
    if scene_count >= 5 and abs(actual_ratio - int(profile["set_piece_ratio"])) >= 14:
        issues.append(_macro_issue("macro_detail_distribution", [], "重点场比例与全书详略设定差异较大；请检查是否把过场写得过重，或把关键代价压缩掉。"))
    return {
        "expected_curve": expected,
        "actual_curve": actual,
        "chapter_ids": chapter_ids,
        "scene_count": scene_count,
        "set_piece_count": set_pieces,
        "set_piece_ratio": actual_ratio,
        "issues": issues,
    }


def _interpolate_arc(arc: dict[str, Any], count: int) -> list[int]:
    if count <= 0:
        return []
    keys = ("opening", "ascent", "midpoint", "crisis", "finale")
    anchors = [_tension(arc.get(key), 3) for key in keys]
    if count == 1:
        return [anchors[0]]
    values: list[int] = []
    for index in range(count):
        position = index / (count - 1)
        scaled = position * (len(anchors) - 1)
        left = min(len(anchors) - 1, int(scaled))
        right = min(len(anchors) - 1, left + 1)
        ratio = scaled - left
        values.append(max(1, min(5, round(anchors[left] + (anchors[right] - anchors[left]) * ratio))))
    return values


def _ordered_unique(values: Any) -> list[str]:
    unique = {str(value or "unassigned") for value in values}
    return sorted(unique, key=_natural_key)


def _natural_key(value: str) -> tuple[Any, ...]:
    import re
    return tuple(int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value))


def _high_pressure_run(values: list[int]) -> list[int]:
    runs: list[int] = []
    length = 0
    for value in values:
        if value >= 4:
            length += 1
        else:
            if length:
                runs.append(length)
            length = 0
    if length:
        runs.append(length)
    return runs


def _macro_issue(code: str, scene_ids: list[str], message: str) -> dict[str, Any]:
    return {"code": code, "severity": "warning", "scene_ids": scene_ids, "message": message}


def _tension(value: object, default: int) -> int:
    try:
        return min(5, max(1, int(value)))
    except (TypeError, ValueError):
        return default


def _whole_number(value: object, default: int, low: int, high: int) -> int:
    try:
        return min(high, max(low, int(value)))
    except (TypeError, ValueError):
        return default


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _scalar(text: str, key: str) -> str:
    import re
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    return match.group(1).strip().strip("\"'") if match else ""


def _integer(value: object) -> int:
    try:
        return max(0, int(str(value or "").replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _positive_number(value: object) -> float:
    try:
        return max(0.0, float(str(value or "").replace(",", "")))
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
