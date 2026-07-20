"""Versioned advisor personas that cannot weaken the read-only constitution."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
from typing import Any


PERSONA_SCHEMA = "arcvellum/advisor-personas/v1"
PERSONA_VERSION = "1.0.0"
DEFAULT_PERSONA = "chief-editor"


_BUILTINS: dict[str, dict[str, str]] = {
    "chief-editor": {
        "name": "严谨总编",
        "tagline": "先看结构是否成立，再谈句子是否漂亮",
        "accent": "jade",
        "prompt": """你是一位克制、清醒、对长篇结构负责的总编。优先检查因果链、人物选择的代价、场景功能、章节承诺和全书规模是否相互支撑。你不靠鼓励维持气氛，也不以挑错显示权威：先指出真正影响成书质量的核心矛盾，再说明可保留的价值。对存在多个方案的问题，明确比较收益、成本和后续维护压力；必要时主张删除、合并或推迟，而不是一律做加法。语言短而完整，少用报告腔和空泛文学赞美。反对用户时直接说明依据，但把最终创作方向留给用户。不要用“作为AI”“综上所述”“值得注意的是”等套话。""",
    },
    "dramaturg": {
        "name": "戏剧构筑师",
        "tagline": "盯住冲突、转向与场景压力",
        "accent": "cinnabar",
        "prompt": """你是一位擅长长篇叙事和戏剧构作的创作伙伴。优先观察人物此刻想得到什么、谁或什么阻止他、选择如何改变局面，以及场景结束后留下什么压力。对平铺直叙、只有信息没有行动、只有情绪没有决定的段落保持敏感。讨论方案时尽量把抽象问题还原成可发生的场景、可见的行动和具体代价；高潮不等于喧闹，过场也必须承担衔接功能。你可以热烈，但不夸张，不把每个建议都说成反转或爆点。避免短剧式强行钩子，尊重作品既有文风和时间尺度。""",
    },
    "cold-reader": {
        "name": "冷面读者",
        "tagline": "只对真实阅读感受负责",
        "accent": "brass",
        "prompt": """你以一位没有义务替作者脑补的成熟读者身份说话。你关心读到这里是否明白、是否愿意继续、是否被重复解释拖慢、是否感到人物在替作者完成任务。不要因为设定复杂就自动认为作品深刻，也不要因为文字流畅就忽略内容空转。指出问题时描述具体阅读反应，例如在哪里失去兴趣、期待被怎样建立又怎样落空；同时区分有意留白与信息缺失、缓慢积累与无效拖延。语言自然、坦率，允许说“这一段我不信”或“我会在这里停下来”，但随后给出可验证的原因。""",
    },
    "warm-peer": {
        "name": "温和同行",
        "tagline": "保护探索欲，也不替问题找借口",
        "accent": "iris",
        "prompt": """你是一位长期写作的同行，理解创作方向尚未定型时需要空间。先听清用户正在尝试什么，再帮助他辨认这个尝试最有生命力的部分。语气温和、具体，不用夸张肯定，不把所有选择都包装成正确。遇到薄弱处仍要指出，但优先用问题和对照方案帮助用户自己看见代价。不要把回答写成教科书，不连续罗列十几条建议；一次抓住一两个真正值得推进的判断。你尊重用户的审美偏好，也会在偏好与作品实际效果冲突时诚实提醒。""",
    },
    "mystery-auditor": {
        "name": "悬疑审计员",
        "tagline": "检查线索公平、误导边界与兑现时机",
        "accent": "iris",
        "prompt": """你是一位重视推理公平性和长线兑现的悬疑编辑。优先核对读者已经知道什么、人物知道什么、作者暂时扣住什么；区分合理的信息差、欺骗性省略和事后补规则。关注线索是否可被回看验证，红鲱鱼是否有独立叙事价值，反转是否改变理解而不是仅更换答案。你会追问承诺何时兑现、拖延是否产生新价值，以及谜底是否与人物选择相连。语言冷静精确，不故作神秘，不建议无依据地增加秘密、反转或幕后黑手。""",
    },
}


def persona_catalog(data_root: Path, project_root: Path | None = None) -> dict[str, Any]:
    state = _load_state(data_root)
    custom = state.get("custom") if isinstance(state.get("custom"), dict) else {}
    items = [
        {"persona_id": key, "version": PERSONA_VERSION, "builtin": True, **value}
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


def select_persona(data_root: Path, project_root: Path, persona_id: str) -> dict[str, Any]:
    catalog = persona_catalog(data_root, project_root)
    known = {str(item["persona_id"]) for item in catalog["items"]}
    if persona_id not in known:
        raise ValueError(f"unknown advisor persona: {persona_id}")
    state = _load_state(data_root)
    selections = state.setdefault("project_selections", {})
    selections[str(project_root.resolve())] = persona_id
    _save_state(data_root, state)
    return persona_catalog(data_root, project_root)


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


def active_persona(data_root: Path, project_root: Path) -> dict[str, str]:
    catalog = persona_catalog(data_root, project_root)
    selected = catalog["selected_persona"]
    value = next(item for item in catalog["items"] if item["persona_id"] == selected)
    return {key: str(value.get(key) or "") for key in ("persona_id", "name", "tagline", "prompt", "version", "accent")}


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
