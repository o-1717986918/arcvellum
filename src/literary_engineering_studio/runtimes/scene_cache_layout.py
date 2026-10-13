"""New frozen layout: dynamic literary context follows an immutable role identity."""
from copy import deepcopy
from hashlib import sha256
import json
from ..runtime.conversation_sessions import ConversationSessionRef
from .scene_natural_output import creator_style, briefing_for_natural_context
from .source_repair_budget import SourceRepairBudget
from pathlib import Path

CACHE_LAYOUT = "stable-prefix-v2"
LEGACY_LAYOUT = "stable-prefix-v1"


def cached_layout(snapshot):
    return snapshot.get("creator_prompt_layout") == CACHE_LAYOUT


def cached_runtime(runtime, transaction_id):
    provider = getattr(runtime, "_v2_prompt_snapshot", None)
    return cached_layout(provider(transaction_id)) if provider else False


def book_style(briefing):
    style = briefing.get("style") or {}
    return "\n\n".join(str((style.get(key) or {}).get("content") or "")
                       for key in ("author_directive","mounted"))


def cached_context(briefing):
    value = briefing_for_natural_context(briefing)
    value["style"] = deepcopy(value.get("style") or {})
    for item in value["style"].values():
        if isinstance(item,dict) and item.get("delivered_via") == "system_prompt":
            item["delivered_via"] = "current_style_direction"
    return value


def scene_session(runtime, transaction_id, role, scope=""):
    path = runtime._cache_path(transaction_id,"prompt_assembly_v2.json")
    if not path.is_file():
        return None
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if not cached_layout(snapshot):
        return None
    briefing = runtime._cache_path(transaction_id,"scene_creator_briefing_v2.json")
    binding = {"prompt":snapshot.get("digest"),"models":snapshot.get("runtime_model_binding"),
               "briefing":sha256(briefing.read_bytes()).hexdigest() if briefing.is_file() else ""}
    return ConversationSessionRef.bound([transaction_id,role,scope],binding).to_dict()


def source_scope(runtime, transaction_id, prompt):
    try:
        task = json.loads(prompt)
    except ValueError:
        marker = "本次审读资料：\n"
        if marker not in prompt:
            return ""
        task = json.loads(prompt.split(marker,1)[1])
    context = task.get("context") or task
    if (context.get("prose_source") or {}).get("sha256"):
        return "body:" + context["prose_source"]["sha256"]
    prose = context.get("prose")
    if prose:
        return "body:" + sha256(str(prose).encode()).hexdigest()
    source = task.get("source_sha256") or task.get("parent_source_sha256") or (task.get("source_index") or {}).get("sha256")
    if source:
        operation = task.get("operation","creator")
        origin = SourceRepairBudget(runtime._cache_path(transaction_id,"v2"),operation,source).origin
        return str(operation) + ":" + origin
    return str(task.get("operation",""))


CONTEXT_RULE = "本次文风以用户消息 current_style_direction 的完整当前值为准；后续带版本的授权上下文更新替代对应旧字段。旧稿、素材候选与 Canon 提议不是已发生或已应用的事实。指定字段补交按 response_contract 交回 JSON patches，正文与未授权字段冻结。"


def validate_frozen_sources(briefing, root, brief):
    if briefing.get("scene_brief") != brief.to_dict():
        raise RuntimeError("scene source revision changed: frozen scene brief changed; create a new transaction")
    for row in [*briefing.get("source_entries", []), *briefing.get("canon_sources", [])]:
        relative = row.get("path")
        if not relative:
            continue
        path = (Path(root) / relative).resolve()
        if not path.is_relative_to(Path(root).resolve()):
            raise RuntimeError("frozen source escaped its work boundary")
        actual = sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != row.get("file_sha256"):
            raise RuntimeError("scene source revision changed: frozen Canon, continuity or user direction changed; create a new transaction")


def review_layout(layers, briefing, context, snapshot):
    from .scene_natural_output import render_style
    if not cached_layout(snapshot):
        return render_style(layers["scene.v2.review"], creator_style(briefing)), context
    system = render_style(layers["scene.v2.review"], book_style(briefing)) + "\n" + CONTEXT_RULE
    return system, {**context, "briefing":cached_context(briefing), "current_style_direction":creator_style(briefing)}
