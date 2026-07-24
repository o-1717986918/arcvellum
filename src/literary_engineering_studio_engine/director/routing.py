"""Deterministic routing, normalization, and policy defaults for director turns."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import DIRECTOR_SCHEMA_VALUE, DIRECTOR_WORKFLOWS
from .helpers import _trim_text

def _deterministic_decision(root: Path, direction: str, run_id: str, project_status: dict[str, Any]) -> dict[str, Any]:
    intent, workflow, rationale = _route_direction(root, direction, project_status)
    if intent == "conversation":
        actions = ["record_project_direction", "summarize_project_status", "write_director_report"]
        delegated = ["creative-director"]
    elif workflow == "none":
        actions = ["summarize_project_status"]
        delegated = ["director-status"]
    else:
        actions = [f"run_{workflow}", "schema_gate_specialist_outputs", "write_director_report"]
        delegated = _delegates(workflow)
    return {
        "schema": DIRECTOR_SCHEMA_VALUE,
        "run_id": run_id,
        "user_direction": direction,
        "intent": intent,
        "chosen_workflow": workflow,
        "rationale": rationale,
        "actions": actions,
        "delegated_to": delegated,
        "director_tools": _director_tools(workflow, project_status, intent=intent, direction=direction),
        "conversation_headline": "我已记住这个创作方向" if intent == "conversation" else "",
        "conversation_reply": _conversation_memory_reply(direction) if intent == "conversation" else "",
        "secondary_decisions": _secondary_decisions("conversation" if intent == "conversation" else workflow),
        "user_visible_decisions": [
            "你只需要继续给出创作大方向、偏好的题材气质、人物重心或剧情推进目标。",
            "候选资产、审查、分支选择和工作流调度由创作总监记录并执行。",
        ],
        "constraints": [
            "新增设定先作为候选资产，不直接写入正式 canon。",
            "角色背景故事作为隐性行为因果，不在正文中直接说明，除非剧情明确揭示。",
            "所有模型输出必须保留运行记录、schema 校验记录和总监报告。",
        ],
        "risks": _risks(workflow),
        "fallback_policy": "如果模型输出未通过 director_decision.v1 校验，使用可复现的安全路由并记录原因。",
        "confidence": 0.78 if workflow != "none" else 0.9,
        "status": "planned",
    }


def _route_direction(root: Path, direction: str, project_status: dict[str, Any]) -> tuple[str, str, str]:
    text = direction.lower()
    if _has_any(text, ["状态", "摘要", "进度", "看一下", "总览", "status", "summary"]):
        return "status", "none", "用户在询问项目状态，因此只读取总监状态，不触发创作写入。"
    if _is_freeform_project_direction(text):
        return "conversation", "none", "用户正在自由表达偏好、禁忌或长期创作方向，先写入总监记忆并用于后续项目管理。"
    if _has_any(text, ["角色", "人物", "背景故事", "关系", "character", "backstory", "relationship"]):
        return "character-lab", "character-lab", "用户方向集中在人物、隐性背景或关系网，适合角色实验室。"
    if _has_any(text, ["世界观", "地点", "组织", "设定", "canon", "world", "location", "organization"]):
        return "worldbuilding-lab", "worldbuilding-lab", "用户方向集中在世界规则、地点或组织，适合世界观实验室。"
    if _has_any(text, ["大纲", "章节", "场景列表", "主线", "剧情框架", "outline", "chapter", "scene list"]):
        return "outline-lab", "outline-lab", "用户方向集中在主线结构、章节或场景列表，适合大纲实验室。"
    if _has_any(text, ["场景", "续写", "推进", "审查", "草稿", "scene", "review", "draft", "workflow"]):
        return "scene-loop", "scene-loop", "用户要求推进或审查具体创作链路，适合场景循环。"
    counts = project_status.get("counts", {}) if isinstance(project_status, dict) else {}
    if not counts.get("candidate_assets"):
        return "project-seeding", "project-seeding", "项目候选资产仍少，先从大方向孵化世界观、角色和大纲候选。"
    if not counts.get("characters"):
        return "character-lab", "character-lab", "项目缺少正式人物档案，先补充人物候选和关系压力。"
    return "scene-loop", "scene-loop", "项目已有基础资产，默认把大方向转入场景推演与审查链路。"


def _usable_decision(parsed: dict[str, Any], fallback: dict[str, Any], validation_status: str) -> dict[str, Any]:
    if validation_status == "pass":
        decision = dict(parsed)
        decision["run_id"] = str(decision.get("run_id") or fallback["run_id"])
        return decision
    decision = dict(fallback)
    decision["secondary_decisions"] = list(decision["secondary_decisions"]) + [
        "顶层模型输出未通过 director_decision.v1，已回退到确定性安全路由。"
    ]
    decision["risks"] = list(decision["risks"]) + ["本轮真实模型决策不可用，需要检查 agent_decision/schema_validation.json。"]
    return decision


def _normalize_director_decision(parsed: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    result = _unwrap_director_payload(parsed)
    route_value = str(result.get("chosen_workflow") or result.get("workflow") or result.get("route") or result.get("intent") or "").strip()
    workflow = _safe_workflow(
        "none" if route_value == "conversation" else route_value,
        str(fallback.get("chosen_workflow") or "none"),
    )
    intent = _safe_intent(result.get("intent") or result.get("route") or workflow, str(fallback.get("intent") or "status"))
    result["schema"] = DIRECTOR_SCHEMA_VALUE
    result["run_id"] = str(result.get("run_id") or fallback.get("run_id") or "")
    result["user_direction"] = str(result.get("user_direction") or fallback.get("user_direction") or "")
    result["intent"] = intent
    result["chosen_workflow"] = workflow
    result["rationale"] = str(result.get("rationale") or result.get("reasoning") or fallback.get("rationale") or "")
    result["actions"] = _list_value(result.get("actions")) or _default_actions(workflow)
    result["delegated_to"] = _delegated_value(result) or list(fallback.get("delegated_to", []))
    result["director_tools"] = _tool_value(result.get("director_tools") or result.get("tools")) or list(fallback.get("director_tools", []))
    result["conversation_headline"] = str(result.get("conversation_headline") or result.get("headline") or "")
    result["conversation_reply"] = str(result.get("conversation_reply") or result.get("reply") or result.get("assistant_reply") or "")
    result["secondary_decisions"] = _list_value(result.get("secondary_decisions")) or list(fallback.get("secondary_decisions", []))
    result["user_visible_decisions"] = (
        _list_value(result.get("user_visible_decisions"))
        or _list_value(result.get("user_visible_choices"))
        or _list_value(result.get("user_choices"))
        or list(fallback.get("user_visible_decisions", []))
    )
    result["constraints"] = _list_value(result.get("constraints")) or list(fallback.get("constraints", []))
    result["risks"] = _list_value(result.get("risks")) or list(fallback.get("risks", []))
    result["fallback_policy"] = str(result.get("fallback_policy") or fallback.get("fallback_policy") or "")
    result["confidence"] = _confidence_value(result.get("confidence"), fallback.get("confidence", 0.5))
    result["status"] = _safe_status(result.get("status"), str(fallback.get("status") or "planned"))
    return result


def _unwrap_director_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    for key in ["director_decision", "decision", "route_decision"]:
        nested = parsed.get(key)
        if isinstance(nested, dict):
            result = dict(parsed)
            result.update(nested)
            return result
    return dict(parsed)


def _default_actions(workflow: str) -> list[str]:
    if workflow == "none":
        return ["summarize_project_status"]
    return [f"run_{workflow}", "schema_gate_specialist_outputs", "write_director_report"]


def _safe_intent(value: Any, fallback: str) -> str:
    intent = str(value or "").strip()
    if intent == "none":
        return "status"
    allowed = {"status", "conversation", *DIRECTOR_WORKFLOWS}
    if intent in allowed:
        return intent
    return fallback if fallback in allowed else "status"


def _safe_status(value: Any, fallback: str) -> str:
    status = str(value or "").strip()
    allowed = {"planned", "executed", "needs_user_direction", "failed"}
    if status in allowed:
        return status
    return fallback if fallback in allowed else "planned"


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_stringify_list_item(item) for item in value if _stringify_list_item(item)]
    if isinstance(value, dict):
        return [f"{key}: {_stringify_list_item(item)}" for key, item in value.items() if _stringify_list_item(item)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _delegated_value(payload: dict[str, Any]) -> list[str]:
    for key in ["delegated_to", "delegated_specialist_agents", "delegated_agents", "specialist_agents"]:
        value = payload.get(key)
        if isinstance(value, list):
            items: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    agent = str(item.get("agent") or item.get("agent_id") or item.get("name") or "").strip()
                    task = str(item.get("task") or item.get("role") or "").strip()
                    if agent and task:
                        items.append(f"{agent}: {task}")
                    elif agent:
                        items.append(agent)
                    elif task:
                        items.append(task)
                else:
                    text = _stringify_list_item(item)
                    if text:
                        items.append(text)
            return items
        normalized = _list_value(value)
        if normalized:
            return normalized
    return []


def _tool_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        tools: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                tool = str(item.get("tool") or item.get("name") or item.get("action") or "").strip()
                if not tool:
                    continue
                normalized = dict(item)
                normalized["tool"] = tool
                tools.append(normalized)
            else:
                text = _stringify_list_item(item)
                if text:
                    tools.append({"tool": text})
        return tools
    if isinstance(value, dict):
        tool = str(value.get("tool") or value.get("name") or value.get("action") or "").strip()
        return [dict(value, tool=tool)] if tool else []
    return []


def _stringify_list_item(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = [f"{key}={item}" for key, item in value.items()]
        return "; ".join(parts).strip()
    if value is None:
        return ""
    return str(value).strip()


def _confidence_value(value: Any, fallback: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(fallback)
        except (TypeError, ValueError):
            return 0.5


def _safe_workflow(value: Any, fallback: str) -> str:
    workflow = str(value or "").strip()
    if workflow == "none" or workflow in DIRECTOR_WORKFLOWS:
        return workflow
    return fallback if fallback == "none" or fallback in DIRECTOR_WORKFLOWS else "none"


def _turn_status(decision: dict[str, Any], auto_execute: bool, workflow: str, workflow_result: Any, workflow_error: str) -> str:
    if workflow_error:
        return "failed"
    if not auto_execute or workflow == "none":
        return "planned" if workflow != "none" else "executed"
    if workflow_result is None:
        return str(decision.get("status") or "planned")
    return "executed" if workflow_result.status not in {"failed"} else "failed"



def _delegates(workflow: str) -> list[str]:
    mapping = {
        "project-seeding": ["worldbuilding-creator", "character-creator", "outline-creator", "asset-reviewer"],
        "character-lab": ["character-creator", "background-story-creator", "relationship-creator", "asset-reviewer"],
        "worldbuilding-lab": ["worldbuilding-creator", "location-creator", "organization-creator", "asset-reviewer"],
        "outline-lab": ["outline-creator", "chapter-plan-creator", "scene-list-creator", "asset-reviewer"],
        "scene-loop": ["memory-retriever", "roleplay-simulator", "branch-simulator", "scene-composer", "scene-reviewer", "canon-reviewer"],
    }
    return mapping.get(workflow, ["director-status"])


def _director_tools(workflow: str, project_status: dict[str, Any], *, intent: str = "", direction: str = "") -> list[dict[str, str]]:
    if intent == "conversation":
        return [
            {
                "tool": "record_project_direction",
                "summary": _conversation_memory_summary(direction),
                "preferences": [direction.strip()] if direction.strip() else [],
                "reason": "用户正在自由表达长期创作方向，需要进入总监记忆而不是暴露项目细节。",
            },
            {"tool": "summarize_project_status", "reason": "记录偏好后刷新项目状态，供下一轮自由对话继续使用。"},
            {"tool": "write_director_report", "reason": "收束本轮对话与项目记忆变更。"},
        ]
    if workflow == "none":
        return [{"tool": "summarize_project_status", "reason": "用户需要状态或方向确认。"}]
    tools: list[dict[str, str]] = []
    if not bool(project_status.get("has_project")):
        tools.append({"tool": "init_project", "reason": "先建立可维护的文学工程目录。"})
    tools.append({"tool": "run_workflow", "mode": workflow, "reason": "把用户的大方向交给对应创作链路推进。"})
    tools.append({"tool": "write_director_report", "reason": "记录本轮判断、工具计划、产物和风险。"})
    return tools


def _secondary_decisions(workflow: str) -> list[str]:
    mapping = {
        "project-seeding": [
            "先同时生成世界观、角色和大纲候选，避免单点设定过早固化。",
            "候选生成后立即进行 schema 与资产审查，不直接晋升。",
        ],
        "character-lab": [
            "优先补齐显性角色档案、隐性背景故事和关系压力。",
            "背景故事只作为行为因果，不作为默认正文说明。",
        ],
        "worldbuilding-lab": [
            "优先明确规则边界、地点压力和组织资源限制。",
            "新增能力、制度或资源只能以候选形式进入审查。",
        ],
        "outline-lab": [
            "优先建立主线、章节节奏和场景列表之间的可追踪关系。",
            "大纲候选不覆盖正式 plot，等待审查与批准。",
        ],
        "scene-loop": [
            "先构建上下文，再进行角色推演、分支推演、场景编排与 Agent 审查。",
            "场景候选可以生成，但正式发布仍走审查与审批链路。",
        ],
        "conversation": [
            "把用户自由表达的偏好、禁忌和长期方向写入总监记忆。",
            "本轮不强行触发创作工作流，下一轮可基于这些方向继续推进。",
        ],
        "none": ["只读取状态，不进行创作写入。"],
    }
    return mapping.get(workflow, mapping["none"])


def _risks(workflow: str) -> list[str]:
    if workflow == "scene-loop":
        return ["如果当前场景草稿未准备好，工作流可能只产出上下文、推演和审查提示。"]
    if workflow in DIRECTOR_WORKFLOWS:
        return ["候选资产数量可能增加，需要后续统一筛选和人工批准后再晋升。"]
    return ["本轮无写入风险。"]


def _has_any(text: str, tokens: list[str]) -> bool:
    return any(token.lower() in text for token in tokens)


def _is_freeform_project_direction(text: str) -> bool:
    preference_tokens = [
        "记住",
        "以后",
        "整体",
        "基调",
        "气质",
        "风格",
        "文风",
        "偏向",
        "更偏",
        "不要",
        "不能",
        "避免",
        "必须",
        "希望",
        "我想",
        "我喜欢",
        "我不想",
        "先聊",
        "聊聊",
        "想法",
        "方向",
        "口味",
        "偏好",
        "tone",
        "style",
        "preference",
    ]
    action_tokens = [
        "生成角色",
        "创建角色",
        "写角色",
        "生成世界观",
        "创建世界观",
        "生成大纲",
        "写大纲",
        "推进场景",
        "续写",
        "审查",
        "从零",
        "孵化",
        "完整文学项目",
        "生成一个完整",
        "创建一个",
        "写一个",
        "长篇",
    ]
    return _has_any(text, preference_tokens) and not _has_any(text, action_tokens)


def _conversation_memory_summary(direction: str) -> str:
    text = re.sub(r"\s+", " ", direction.strip())
    if not text:
        return "记录用户本轮创作偏好，供后续总监对话与项目调度使用。"
    return f"用户表达了项目长期方向或创作偏好：{_trim_text(text, 240)}"


def _conversation_memory_reply(direction: str) -> str:
    text = _trim_text(direction, 120)
    if text:
        return f"可以，我会把「{text}」作为后续判断的项目方向记忆。它不会直接改写正式设定，但会影响我接下来怎样筛选人物压力、叙事气质、冲突节奏和文风约束。你可以继续像聊天一样给我偏好；需要推进时直接说“继续”就行。"
    return "可以，我会把这轮偏好写入项目方向记忆。它不会直接改写正式设定，但会影响我后续怎样筛选人物、剧情节奏和文风约束。"
