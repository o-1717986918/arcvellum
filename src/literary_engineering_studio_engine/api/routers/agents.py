"""Agent-run and director-conversation endpoints for the legacy Engine API."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ...agent_provider import run_agent_task
from ...director_agent import (
    DirectorBootstrapResult,
    bootstrap_project_from_direction,
    build_director_status,
    director_project_slug,
    run_director_turn,
)
from ...model_config import load_config, redacted_effective_config, save_config
from ..common import ensure_target_allowed, is_relative_to, rel_str, require_api_token, safe_agent_run_dir, safe_project_root
from ..models import AssistantChatRequest, DirectorChatRequest, RunAgentRequest

try:
    from fastapi import APIRouter, HTTPException, Request
except ImportError:  # pragma: no cover - optional HTTP dependency
    APIRouter = None
    HTTPException = None
    Request = object


def build_agent_router(*, api_token: str, allowed_roots: list[Path]):
    router = APIRouter()

    @router.post("/agent/run")
    def agent_run(payload: RunAgentRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = run_agent_task(root, agent_id=payload.agent_id, task=payload.task, system_prompt=payload.system_prompt, user_prompt=payload.user_prompt, provider=payload.provider, output_dir=Path(payload.out_dir) if payload.out_dir else None)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"run_id": result.run_id, "status": result.status, "parse_status": result.parse_status, "run_dir": rel_str(result.run_dir, root), "input": rel_str(result.input_path, root), "raw_output": rel_str(result.raw_output_path, root), "parsed_output": rel_str(result.parsed_output_path, root), "validation": rel_str(result.validation_path, root)}

    @router.get("/agent/runs/{run_id}")
    def agent_run_state(run_id: str, project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        run_dir = safe_agent_run_dir(root, run_id)
        parsed_path = run_dir / "parsed_output.json"
        validation_path = run_dir / "validation_report.md"
        if not parsed_path.exists():
            raise HTTPException(status_code=404, detail=f"agent run not found: {run_id}")
        return {"run_id": run_id, "run_dir": rel_str(run_dir, root), "parsed_output": json.loads(parsed_path.read_text(encoding="utf-8")), "validation_report": validation_path.read_text(encoding="utf-8") if validation_path.exists() else ""}

    @router.post("/assistant/chat")
    def assistant_chat(payload: AssistantChatRequest, http_request: Request):
        require_api_token(http_request, api_token)
        project_root_value = payload.project_root.strip()
        root = safe_project_root(project_root_value, allowed_roots) if project_root_value else None
        try:
            return handle_assistant_message(payload.message.strip(), root)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/director/chat")
    def director_chat(payload: DirectorChatRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root, bootstrap = resolve_director_root(payload, allowed_roots)
        try:
            result = run_director_turn(root, payload.message, provider=payload.provider, auto_execute=payload.auto_execute, agent_tasks=payload.agent_tasks)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if bootstrap:
            result.decision["project_created"] = True
            result.decision["project_title"] = bootstrap.title
            result.decision["project_bootstrap"] = rel_str(bootstrap.bootstrap_path, root)
            result.artifacts["project_bootstrap"] = rel_str(bootstrap.bootstrap_path, root)
        return director_response(result, root, bootstrap=bootstrap)

    @router.get("/director/status")
    def director_status(project_root: str, http_request: Request, limit: int = 8):
        require_api_token(http_request, api_token)
        return build_director_status(safe_project_root(project_root, allowed_roots), limit=limit)

    return router


def resolve_director_root(payload: DirectorChatRequest, allowed_roots: list[Path]) -> tuple[Path, DirectorBootstrapResult | None]:
    requested = payload.project_root.strip()
    message = payload.message.strip()
    wants_new = message_requests_new_project(message)
    if requested:
        requested_path = Path(requested).resolve()
        if requested_path.is_dir() and not wants_new:
            return safe_project_root(requested_path, allowed_roots), None
        if requested_path.exists() and not requested_path.is_dir():
            raise HTTPException(status_code=400, detail=f"project root is not a directory: {requested_path}")
        if not payload.create_project_if_missing and not wants_new:
            return safe_project_root(requested_path, allowed_roots), None
        target = requested_path if not requested_path.exists() else unique_director_project_target(requested_path.parent, message, payload.project_title)
        ensure_target_allowed(target, allowed_roots)
        bootstrap = bootstrap_director_project(target, payload)
        remember_default_project_root(bootstrap.root)
        return bootstrap.root, bootstrap
    configured = str(load_config().get("defaults", {}).get("project_root", "") or "").strip()
    if configured and Path(configured).resolve().is_dir() and not wants_new:
        return safe_project_root(configured, allowed_roots), None
    if not payload.create_project_if_missing:
        raise HTTPException(status_code=400, detail="project_root is required when create_project_if_missing is false")
    base = director_project_parent(payload.project_parent, allowed_roots)
    target = unique_director_project_target(base, message, payload.project_title)
    ensure_target_allowed(target, allowed_roots)
    bootstrap = bootstrap_director_project(target, payload)
    remember_default_project_root(bootstrap.root)
    return bootstrap.root, bootstrap


def director_project_parent(project_parent: str, allowed_roots: list[Path]) -> Path:
    parent = Path(project_parent).resolve() if project_parent.strip() else (allowed_roots[0] / "director-projects" if allowed_roots else Path.cwd() / "director-projects")
    if allowed_roots and not any(is_relative_to(parent, allowed) or parent == allowed for allowed in allowed_roots):
        raise HTTPException(status_code=403, detail=f"project parent is outside allowed roots: {parent}")
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def unique_director_project_target(base: Path, message: str, title: str = "") -> Path:
    slug = director_project_slug(title.strip() or message.strip() or "literary-project")
    target = (base / slug).resolve()
    if not target.exists():
        return target
    for index in range(2, 1000):
        candidate = (base / f"{slug}-{index}").resolve()
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=409, detail=f"could not allocate project target under: {base}")


def bootstrap_director_project(target: Path, payload: DirectorChatRequest) -> DirectorBootstrapResult:
    try:
        return bootstrap_project_from_direction(target, payload.message, title=payload.project_title)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def message_requests_new_project(message: str) -> bool:
    return any(token in message.lower() for token in ["新建项目", "创建项目", "创建一个项目", "新项目", "完整文学项目", "生成一个完整", "一句话生成", "start a new project", "create a new project"])


def remember_default_project_root(root: Path) -> None:
    config = load_config()
    defaults = dict(config.get("defaults", {}) if isinstance(config.get("defaults", {}), dict) else {})
    defaults["project_root"] = str(root)
    config["defaults"] = defaults
    save_config(config)


def handle_assistant_message(message: str, root: Path | None) -> dict[str, object]:
    lowered = message.lower()
    if any(token in lowered for token in ["测试模型", "连接", "connection", "api test"]):
        if root is None:
            raise ValueError("project_root is required for model connection test")
        result = run_agent_task(root, agent_id="ui-connection-test", task="connection-test", system_prompt="You are a connection test assistant.", user_prompt="请只回复：模型连接成功。", provider="http-chat")
        return {"reply": "已发起模型连接测试。", "action": "agent-run", "data": {"run_id": result.run_id, "parsed_output": rel_str(result.parsed_output_path, root)}}
    if any(token in lowered for token in ["配置", "config", "provider", "模型", "deepseek"]):
        return {"reply": "已读取当前全局配置。密钥可来自环境变量，也可来自本机全局配置中保存的 profile api_key。", "action": "config", "data": redacted_effective_config()}
    if root is None:
        raise ValueError("project_root is required for project actions")
    return director_response(run_director_turn(root, message, provider="auto", auto_execute=True), root)


def director_response(result, root: Path, *, bootstrap: DirectorBootstrapResult | None = None) -> dict[str, object]:
    return {"reply": result.reply, "action": result.action, "conversation": director_conversation(result, root), "data": {"project_root": str(root), "project_created": bool(bootstrap), "project_title": bootstrap.title if bootstrap else str(result.decision.get("project_title") or ""), "project_bootstrap": rel_str(bootstrap.bootstrap_path, root) if bootstrap else str(result.decision.get("project_bootstrap") or ""), "run_id": result.run_id, "status": result.status, "decision": rel_str(result.decision_path, root), "report": rel_str(result.report_path, root), "agent_run": rel_str(result.agent_run_dir, root), "validation": rel_str(result.validation_path, root), "workflow_state": rel_str(result.workflow_state_path, root) if result.workflow_state_path else "", "tool_loop": str(result.decision.get("tool_loop") or result.artifacts.get("tool_loop") or ""), "artifacts": result.artifacts, "decision_payload": result.decision}}


def director_conversation(result, root: Path) -> dict[str, object]:
    decision = result.decision
    artifacts = getattr(result, "artifacts", {}) if isinstance(getattr(result, "artifacts", {}), dict) else {}
    workflow = str(decision.get("chosen_workflow") or "none")
    custom_headline = safe_conversation_text(decision.get("conversation_headline"), limit=80)
    custom_message = safe_conversation_text(decision.get("conversation_reply"), limit=700)
    if custom_headline:
        headline = custom_headline
    elif bool(decision.get("project_created")):
        headline = f"我已经为你建立「{decision.get('project_title') or '新文学项目'}」"
    elif result.status == "failed":
        headline = "我接住了你的方向，但后台执行遇到阻塞"
    elif workflow == "none":
        headline = "我先帮你看项目状态"
    elif bool(decision.get("auto_execute")):
        headline = f"我已把方向推进到「{workflow_label(workflow)}」"
    else:
        headline = f"我建议下一步先做「{workflow_label(workflow)}」"
    if custom_message:
        message = custom_message
    elif bool(decision.get("project_created")):
        message = "我已经把这句话整理成可持续维护的文学工程项目，并会从设定、人物、主线和后续任务开始推进。"
    elif result.status == "failed":
        message = "这轮方向我已经接住了。接下来我会先处理阻塞点，再把真正影响创作走向的选择带回来给你。"
    elif workflow == "none":
        message = "这一轮我不会改动项目。你可以继续告诉我想强化的题材气质、人物压力或剧情方向。"
    elif bool(decision.get("auto_execute")):
        message = "我会沿着这个方向继续推进；你只需要判断人物压力、题材气质和剧情节奏是否符合预期。"
    else:
        message = "我会把你的大方向转成下一轮创作推进。你只需要继续用自然语言确认、修正或追加偏好。"
    return {"speaker": "创作总监", "headline": headline, "message": message, "next_questions": director_next_questions(decision, workflow), "will_handle": director_will_handle(workflow, decision), "audit": {"run_id": result.run_id, "status": result.status, "workflow": workflow, "provider": str(decision.get("provider") or ""), "project_root": str(root), "report": rel_str(result.report_path, root), "validation": rel_str(result.validation_path, root), "workflow_state": rel_str(result.workflow_state_path, root) if result.workflow_state_path else "", "tool_loop": str(decision.get("tool_loop") or artifacts.get("tool_loop") or "")}}


def workflow_label(workflow: str) -> str:
    return {"none": "项目状态确认", "project-seeding": "项目孵化", "character-lab": "人物与关系梳理", "worldbuilding-lab": "世界观与场域梳理", "outline-lab": "主线与章节规划", "scene-loop": "场景推进与审查"}.get(workflow, workflow or "项目状态确认")


def director_next_questions(decision: dict[str, object], workflow: str) -> list[str]:
    polished = [strip_list_marker(item) for item in visible_list(decision.get("user_visible_decisions"), limit=4) if is_safe_user_facing_item(item)]
    if polished:
        return polished[:3]
    if str(decision.get("intent") or "") == "conversation":
        return ["你可以继续补充题材气质、人物口味、叙事禁忌或节奏偏好。", "也可以直接说继续，我会按已记录的方向推进后台创作。"]
    return {"project-seeding": ["这部作品下一步更想先强化题材气质、人物压力，还是主线结构？", "也可以直接说继续，我会先把方向整理成一版可讨论的初步方案。"], "character-lab": ["人物部分你更想先压住主角困境、对手动机，还是关系冲突？", "也可以只给一句感觉，我来把背景故事和行为逻辑补齐。"], "worldbuilding-lab": ["世界观更偏现实冷硬、超常悬疑，还是组织和制度压力更强？", "你只需要确认氛围方向，其余规则我会在后台推演。"], "outline-lab": ["主线更想先确定结局方向、阶段反转，还是人物长期代价？", "也可以说继续，我会把大方向拆成章节推进方案。"], "scene-loop": ["下一场更想推进冲突、揭示信息，还是强化人物选择？", "如果没有新偏好，我会沿当前方向继续推进并自检。"], "none": ["你可以继续告诉我想强化的题材气质、人物重心或剧情方向。"]}.get(workflow, ["你可以继续告诉我想强化的题材气质、人物重心或剧情方向。"])


def director_will_handle(workflow: str, decision: dict[str, object] | None = None) -> list[str]:
    if str((decision or {}).get("intent") or "") == "conversation":
        return ["把这轮偏好写入创作总监记忆。", "后续调度人物、剧情、文风和审查时优先参考这些方向。"]
    tools = visible_director_tools(workflow)
    if tools:
        return tools
    return ["读取项目状态和最近记录。", "把需要你关注的创作方向整理成简短回复。"] if workflow == "none" else [f"把你的创作方向拆给「{workflow_label(workflow)}」相关节点处理。", "让生成、审查和取舍记录在后台完成。", "只把真正需要你判断的创作方向带回对话里。"]


def is_safe_user_facing_item(item: str) -> bool:
    text = item.strip()
    blocked = ["approve", "reject", "candidate", "schema", "workflow", "run_", "json", "yaml", "canon", "agent", "候选", "审批", "批准", "拒绝", "工作流", "校验", "审计", "文件", "路径"]
    return bool(text and re.search(r"[\u4e00-\u9fff]", text) and not any(token in text.lower() for token in blocked))


def safe_conversation_text(value: object, *, limit: int) -> str:
    text = str(value or "").strip()
    blocked = ["decision_payload", "project_yaml", "schema", "workflow", "run_", "yaml", "json", "approve", "reject"]
    return text[:limit] if text and re.search(r"[\u4e00-\u9fff]", text) and not any(token in text.lower() for token in blocked) else ""


def visible_director_tools(workflow: str) -> list[str]:
    return {"project-seeding": ["建立或补齐作品骨架。", "整理世界观、人物和主线的第一批候选方向。", "把后续需要你判断的创作取舍带回对话里。"], "character-lab": ["梳理人物困境、隐性背景故事和关系压力。", "检查人物行为是否能支撑后续剧情。", "把真正影响走向的关系选择带回对话里。"], "worldbuilding-lab": ["梳理世界规则、关键地点和组织压力。", "检查设定边界是否会限制或推动剧情。", "把需要你确认的氛围和规则取舍带回对话里。"], "outline-lab": ["整理主线结构、阶段反转和章节推进。", "检查人物代价与剧情节奏是否匹配。", "把关键走向选择带回对话里。"], "scene-loop": ["读取上下文并推进下一场创作。", "让角色推演、分支推演和审查在后台完成。", "把需要你判断的场景效果带回对话里。"]}.get(workflow, [])


def strip_list_marker(item: str) -> str:
    return re.sub(r"^\s*[-*0-9.、)）]+", "", item).strip()


def visible_list(value: object, *, limit: int) -> list[str]:
    return [str(item) for item in value[:limit] if str(item).strip()] if isinstance(value, list) else []
