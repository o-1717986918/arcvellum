"""Versioned, project-level creative quality policy.

The profile controls literary preferences only. Workflow provenance, review,
promotion, canon, and export gates remain immutable elsewhere in the engine.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


CREATIVE_QUALITY_SCHEMA = "arcvellum/creative-quality-profile/v1"
CREATIVE_QUALITY_RELATIVE_PATH = Path("style") / "creative_quality_profile.json"
RULE_MODES = {"off", "note", "blocking"}


DEFAULT_RULE_MODES: dict[str, str] = {
    "mechanical-contrast-frame": "blocking",
    "contrast-evasion-frame": "blocking",
    "plain-narration-banned-expression": "note",
    "dash-prohibited-in-plain-narration": "note",
    "comma-overload-in-sentence": "blocking",
    "plain-narration-template-sentence": "note",
    "simile-dependency": "note",
    "abstract-summary-density": "blocking",
    "explanatory-psychology-overuse": "blocking",
    "slogan-like-ending": "note",
    "ascii-punctuation-in-chinese": "blocking",
    "ascii-ellipsis": "blocking",
    "ascii-dash": "note",
    "western-quotes-in-chinese": "note",
    "corner-quotes-in-horizontal-prose": "blocking",
    "punctuation-spacing": "note",
    "repeated-terminal-punctuation": "blocking",
    "repeated-punctuation": "blocking",
    "staccato-period-overuse": "blocking",
    "comma-chain-overload": "blocking",
    "dash-overuse": "blocking",
    "mechanical-transition-overuse": "blocking",
    "custom-banned-phrase": "blocking",
}

DEFAULT_THRESHOLDS: dict[str, float | int] = {
    "soft_density_per_100_units": 2.0,
    "dash_per_100_units": 2.0,
    "dash_per_paragraph": 2,
    "commas_per_sentence": 3,
    "transition_per_100_units": 4.0,
    "transition_minimum_hits": 4,
    "staccato_period_ratio": 0.85,
    "staccato_min_terminals": 8,
    "min_chars_per_terminal": 14,
    "simile_per_100_units": 2.0,
    "simile_minimum_hits": 2,
}

PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {},
    "plainspoken": {
        "thresholds": {
            "soft_density_per_100_units": 1.0,
            "dash_per_100_units": 0.5,
            "transition_per_100_units": 2.0,
            "simile_per_100_units": 1.0,
        }
    },
    "style-led": {
        "rule_modes": {
            "dash-prohibited-in-plain-narration": "note",
            "dash-overuse": "note",
            "simile-dependency": "note",
            "staccato-period-overuse": "note",
        },
        "thresholds": {
            "soft_density_per_100_units": 3.0,
            "dash_per_100_units": 4.0,
            "transition_per_100_units": 5.0,
            "simile_per_100_units": 4.0,
        },
    },
}


def default_creative_quality_profile(*, preset: str = "balanced") -> dict[str, Any]:
    preset_id = preset if preset in PRESETS else "balanced"
    profile: dict[str, Any] = {
        "schema": CREATIVE_QUALITY_SCHEMA,
        "profile_id": "creative-quality-default",
        "name": "均衡叙事",
        "preset": preset_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "updated_by": "system-default",
        "applies_from": "future-candidates",
        "rule_modes": deepcopy(DEFAULT_RULE_MODES),
        "thresholds": deepcopy(DEFAULT_THRESHOLDS),
        "punctuation": {
            "quote_style": "curly-double",
            "ellipsis": "……",
            "dash": "——",
        },
        "custom_banned_phrases": [],
        "preferred_habits": [
            "用动作、事实顺序、信息差和人物选择制造转折",
            "过场简写，高潮依靠准确细节而不是形容词堆叠",
            "情绪通过选择、语气和后果呈现",
        ],
        "exceptions": [],
    }
    _merge_preset(profile, preset_id)
    profile["digest"] = creative_quality_profile_digest(profile)
    return profile


def creative_quality_profile_path(project_root: Path) -> Path:
    return project_root.resolve() / CREATIVE_QUALITY_RELATIVE_PATH


def creative_quality_profile_exists(project_root: Path) -> bool:
    return creative_quality_profile_path(project_root).exists()


def load_creative_quality_profile(project_root: Path) -> dict[str, Any]:
    path = creative_quality_profile_path(project_root)
    if not path.exists():
        profile = default_creative_quality_profile()
        profile["implicit_default"] = True
        return profile
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"creative quality profile is invalid: {path}: {exc}") from exc
    return normalize_creative_quality_profile(payload)


def normalize_creative_quality_profile(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("creative quality profile must be an object")
    preset = str(payload.get("preset") or "balanced").strip().lower()
    profile = default_creative_quality_profile(preset=preset)
    for key in (
        "profile_id",
        "name",
        "revision",
        "created_at",
        "updated_at",
        "updated_by",
        "applies_from",
    ):
        if key in payload:
            profile[key] = payload[key]
    modes = payload.get("rule_modes") if isinstance(payload.get("rule_modes"), dict) else {}
    for rule, mode in modes.items():
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in RULE_MODES:
            raise ValueError(f"invalid creative quality rule mode for {rule}: {mode}")
        profile["rule_modes"][str(rule)] = normalized_mode
    thresholds = payload.get("thresholds") if isinstance(payload.get("thresholds"), dict) else {}
    for key, value in thresholds.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"invalid creative quality threshold for {key}: {value}")
        profile["thresholds"][str(key)] = value
    punctuation = payload.get("punctuation") if isinstance(payload.get("punctuation"), dict) else {}
    profile["punctuation"].update({str(key): str(value) for key, value in punctuation.items()})
    for key in ("custom_banned_phrases", "preferred_habits"):
        if key in payload:
            if not isinstance(payload[key], list):
                raise ValueError(f"creative quality {key} must be a list")
            profile[key] = deepcopy(payload[key])
    if "exceptions" in payload:
        profile["exceptions"] = _normalize_exceptions(payload["exceptions"])
    profile["schema"] = CREATIVE_QUALITY_SCHEMA
    profile["revision"] = max(1, int(profile.get("revision") or 1))
    profile["digest"] = creative_quality_profile_digest(profile)
    return profile


def save_creative_quality_profile(project_root: Path, payload: dict[str, Any], *, updated_by: str = "user") -> dict[str, Any]:
    path = creative_quality_profile_path(project_root)
    previous = load_creative_quality_profile(project_root)
    normalized = normalize_creative_quality_profile(payload)
    previous_digest = creative_quality_profile_digest(previous)
    next_digest = creative_quality_profile_digest(normalized)
    if path.exists() and previous_digest != next_digest:
        normalized["revision"] = int(previous.get("revision") or 1) + 1
    elif path.exists():
        normalized["revision"] = int(previous.get("revision") or 1)
    normalized["created_at"] = str(previous.get("created_at") or normalized.get("created_at") or _now())
    normalized["updated_at"] = _now()
    normalized["updated_by"] = updated_by
    normalized.pop("implicit_default", None)
    normalized["digest"] = creative_quality_profile_digest(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def creative_quality_profile_digest(profile: dict[str, Any]) -> str:
    semantic = deepcopy(profile)
    for key in ("digest", "created_at", "updated_at", "updated_by", "implicit_default", "revision"):
        semantic.pop(key, None)
    encoded = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def quality_rule_mode(
    profile: dict[str, Any] | None,
    rule: str,
    default: str = "blocking",
    *,
    scope: str = "",
) -> str:
    if not profile:
        return default
    modes = profile.get("rule_modes") if isinstance(profile.get("rule_modes"), dict) else {}
    mode = str(modes.get(rule) or default).strip().lower()
    for exception in profile.get("exceptions", []) if isinstance(profile.get("exceptions"), list) else []:
        if isinstance(exception, dict) and _exception_applies(exception, rule, scope):
            mode = str(exception.get("mode") or mode).strip().lower()
    return mode if mode in RULE_MODES else default


def quality_threshold(profile: dict[str, Any] | None, key: str, default: float | int) -> float:
    if not profile:
        return float(default)
    thresholds = profile.get("thresholds") if isinstance(profile.get("thresholds"), dict) else {}
    value = thresholds.get(key, default)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else float(default)


def apply_rule_mode(severity: str, mode: str) -> str | None:
    if mode == "off":
        return None
    if mode == "note":
        return "low"
    return severity if severity not in {"", "low"} else "medium"


def render_creative_quality_prompt(profile: dict[str, Any], *, scope: str = "") -> str:
    profile = normalize_creative_quality_profile(profile)
    thresholds = profile["thresholds"]
    modes = profile["rule_modes"]
    banned = [str(item).strip() for item in profile.get("custom_banned_phrases", []) if str(item).strip()]
    habits = [str(item).strip() for item in profile.get("preferred_habits", []) if str(item).strip()]
    active_blocking = [rule for rule, mode in modes.items() if mode == "blocking"]
    active_notes = [rule for rule, mode in modes.items() if mode == "note"]
    lines = [
        "# 本项目创作品质档案",
        "",
        f"- 名称：{profile['name']}",
        f"- 版本：r{profile['revision']}",
        f"- 摘要：{profile['digest']}",
        f"- 预设：{profile['preset']}",
        "- 本档案只调节文学表达偏好，不能关闭来源、审查、晋升、Canon、状态写回或导出门禁。",
        "",
        "## 生成时必须执行",
        "",
        f"- 风险表达软密度上限：每 100 个叙事单元 {thresholds['soft_density_per_100_units']:g} 次。",
        f"- 破折号上限：每 100 个叙事单元 {thresholds['dash_per_100_units']:g} 次，单段不超过 {int(thresholds['dash_per_paragraph'])} 次。",
        f"- 单句最多 {int(thresholds['commas_per_sentence'])} 个逗号类停顿；超过时重组句法。",
        f"- 显性转折词上限：每 100 个叙事单元 {thresholds['transition_per_100_units']:g} 次。",
        f"- 比喻风险上限：每 100 个叙事单元 {thresholds['simile_per_100_units']:g} 次。",
        f"- 直接引语样式：{profile['punctuation'].get('quote_style', 'curly-double')}；省略号：{profile['punctuation'].get('ellipsis', '……')}。",
    ]
    if habits:
        lines.extend(["", "## 偏好的表达习惯", "", *[f"- {item}" for item in habits]])
    if banned:
        lines.extend(["", "## 项目自定义禁用表达", "", *[f"- {item}" for item in banned]])
    active_exceptions = [
        item for item in profile.get("exceptions", [])
        if isinstance(item, dict) and not _exception_expired(item)
    ]
    if active_exceptions:
        lines.extend(["", "## 已登记的范围例外", ""])
        lines.extend(
            f"- {item['scope']} / {item['rule']} -> {item['mode']}：{item['reason']}"
            for item in active_exceptions
        )
    if scope:
        applied = [item for item in active_exceptions if _exception_applies(item, str(item.get("rule") or ""), scope)]
        lines.extend(["", "## 当前场景作用域", "", f"- 当前场景：{scope}"])
        if applied:
            lines.extend(f"- 本场实际应用：{item['rule']} -> {item['mode']}（{item['reason']}）" for item in applied)
        else:
            lines.append("- 本场没有适用的范围例外，执行项目通用规则。")
    lines.extend(
        [
            "",
            "## 审查强度",
            "",
            "- 阻断规则：" + ("、".join(active_blocking) if active_blocking else "无"),
            "- 提醒规则：" + ("、".join(active_notes) if active_notes else "无"),
            "- 场景例外只有在档案中登记范围、理由和有效期后才生效；不得在正文生成时临时口头豁免。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _merge_preset(profile: dict[str, Any], preset: str) -> None:
    overlay = PRESETS.get(preset, {})
    if isinstance(overlay.get("rule_modes"), dict):
        profile["rule_modes"].update(overlay["rule_modes"])
    if isinstance(overlay.get("thresholds"), dict):
        profile["thresholds"].update(overlay["thresholds"])


def _normalize_exceptions(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("creative quality exceptions must be a list")
    result: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"creative quality exception {index} must be an object")
        rule = str(item.get("rule") or "").strip()
        scope = str(item.get("scope") or "").strip()
        reason = str(item.get("reason") or "").strip()
        mode = str(item.get("mode") or "note").strip().lower()
        expires_at = str(item.get("expires_at") or "").strip()
        if not rule or not scope or not reason:
            raise ValueError(f"creative quality exception {index} requires rule, scope, and reason")
        if mode not in RULE_MODES:
            raise ValueError(f"invalid creative quality exception mode: {mode}")
        result.append({"rule": rule, "scope": scope, "reason": reason, "mode": mode, "expires_at": expires_at})
    return result


def _exception_applies(exception: dict[str, Any], rule: str, scope: str) -> bool:
    if not scope or _exception_expired(exception):
        return False
    exception_rule = str(exception.get("rule") or "")
    if exception_rule not in {"*", rule}:
        return False
    target = str(exception.get("scope") or "").strip()
    return target in {"*", "all", scope, f"scene:{scope}"}


def _exception_expired(exception: dict[str, Any]) -> bool:
    value = str(exception.get("expires_at") or "").strip()
    if not value:
        return False
    try:
        expires = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= datetime.now(timezone.utc)
    except ValueError:
        return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
