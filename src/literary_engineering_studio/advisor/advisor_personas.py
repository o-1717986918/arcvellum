"""Versioned advisor personas that cannot weaken the read-only constitution."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
from typing import Any, Callable

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec


PERSONA_SCHEMA = "arcvellum/advisor-personas/v1"
PERSONA_VERSION = "1.0.0"
DEFAULT_PERSONA = "chief-editor"


_BUILTINS: dict[str, dict[str, str]] = {
    "chief-editor": {
        "name": "严谨总编",
        "tagline": "先看结构是否成立，再谈句子是否漂亮",
        "accent": "jade",
    },
    "dramaturg": {
        "name": "戏剧构筑师",
        "tagline": "盯住冲突、转向与场景压力",
        "accent": "cinnabar",
    },
    "cold-reader": {
        "name": "冷面读者",
        "tagline": "只对真实阅读感受负责",
        "accent": "brass",
    },
    "warm-peer": {
        "name": "温和同行",
        "tagline": "保护探索欲，也不替问题找借口",
        "accent": "iris",
    },
    "mystery-auditor": {
        "name": "悬疑审计员",
        "tagline": "检查线索公平、误导边界与兑现时机",
        "accent": "iris",
    },
}


def persona_catalog(
    data_root: Path, project_root: Path | None = None,
    *, prompt_resolver: Callable[[str, Path | None], str] | None = None,
) -> dict[str, Any]:
    state = _load_state(data_root)
    custom = state.get("custom") if isinstance(state.get("custom"), dict) else {}
    items = [
        {"persona_id": key, "version": PERSONA_VERSION, "builtin": True, **value,
         "prompt": _persona_prompt(key, project_root, prompt_resolver)}
        for key, value in _BUILTINS.items()
    ]
    for persona_id, value in custom.items():
        if isinstance(value, dict):
            items.append({"persona_id": persona_id, "version": str(value.get("version") or PERSONA_VERSION), "builtin": False, **value})
    selected = DEFAULT_PERSONA
    if project_root:
        selections = state.get("project_selections") if isinstance(state.get("project_selections"), dict) else {}
        selected = str(selections.get(str(project_root.resolve())) or state.get("default_persona") or DEFAULT_PERSONA)
    if not any(item["persona_id"] == selected for item in items):
        selected = DEFAULT_PERSONA
    return {"ok": True, "schema": PERSONA_SCHEMA, "selected_persona": selected, "items": items}


def select_persona(
    data_root: Path, project_root: Path, persona_id: str,
    *, prompt_resolver: Callable[[str, Path | None], str] | None = None,
) -> dict[str, Any]:
    catalog = persona_catalog(data_root, project_root, prompt_resolver=prompt_resolver)
    known = {str(item["persona_id"]) for item in catalog["items"]}
    if persona_id not in known:
        raise ValueError(f"unknown advisor persona: {persona_id}")
    state = _load_state(data_root)
    selections = state.setdefault("project_selections", {})
    selections[str(project_root.resolve())] = persona_id
    _save_state(data_root, state)
    return persona_catalog(data_root, project_root, prompt_resolver=prompt_resolver)


def save_custom_persona(
    data_root: Path,
    *,
    name: str,
    tagline: str,
    prompt: str,
    persona_id: str = "",
) -> dict[str, Any]:
    clean_name = name.strip()[:40]
    clean_prompt = prompt.strip()
    if not clean_name:
        raise ValueError("顾问人格名称不能为空。")
    if len(clean_prompt) < 80:
        raise ValueError("自定义人格说明至少需要 80 个字符，才能形成稳定语气。")
    if len(clean_prompt) > 5000:
        raise ValueError("自定义人格说明不能超过 5000 个字符。")
    forbidden = re.compile(r"(?i)(shell|powershell|cmd\.exe|subagent|子代理|修改文件|删除文件|覆盖系统|忽略.{0,8}指令|api[_ -]?key|token)")
    if forbidden.search(clean_prompt):
        raise ValueError("人格说明只能描述语言风格与关注重点，不能包含工具、文件、密钥或覆盖系统的要求。")
    identifier = _slug(persona_id or clean_name)
    if identifier in _BUILTINS:
        raise ValueError("不能覆盖内置顾问人格。")
    state = _load_state(data_root)
    custom = state.setdefault("custom", {})
    custom[identifier] = {
        "name": clean_name,
        "tagline": tagline.strip()[:120],
        "accent": "iris",
        "prompt": clean_prompt,
        "version": PERSONA_VERSION,
    }
    _save_state(data_root, state)
    return {"ok": True, "persona": {"persona_id": identifier, "builtin": False, **custom[identifier]}}


def active_persona(
    data_root: Path, project_root: Path,
    *, prompt_resolver: Callable[[str, Path | None], str] | None = None,
) -> dict[str, str]:
    catalog = persona_catalog(data_root, project_root, prompt_resolver=prompt_resolver)
    selected = catalog["selected_persona"]
    value = next(item for item in catalog["items"] if item["persona_id"] == selected)
    return {key: str(value.get(key) or "") for key in ("persona_id", "name", "tagline", "prompt", "version", "accent")}


def _persona_prompt(
    persona_id: str, project_root: Path | None,
    resolver: Callable[[str, Path | None], str] | None,
) -> str:
    layer_id = f"advisor.persona.{persona_id}"
    return resolver(layer_id, project_root) if resolver is not None else prompt_layer_spec(layer_id).default_text


def _state_path(data_root: Path) -> Path:
    return data_root.expanduser().resolve() / "advisor" / "personas.json"


def _load_state(data_root: Path) -> dict[str, Any]:
    path = _state_path(data_root)
    if not path.is_file():
        return {"schema": PERSONA_SCHEMA, "default_persona": DEFAULT_PERSONA, "project_selections": {}, "custom": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        value = {}
    return value if isinstance(value, dict) else {}


def _save_state(data_root: Path, state: dict[str, Any]) -> None:
    path = _state_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["schema"] = PERSONA_SCHEMA
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"custom-{text or suffix}"[:64]
