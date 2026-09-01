"""Runtime readiness checks shared by application entry points."""

from __future__ import annotations

from typing import Any

from ..runtimes import build_runtime


def runtime_readiness_error(
    config: dict[str, Any],
    runtime_id: str,
    *,
    role: str = "worker",
) -> str:
    """Return a user-facing reason when one configured runtime cannot execute."""

    normalized = str(runtime_id or "").strip().lower()
    if not normalized:
        return "尚未选择创作执行器。"
    runners = config.get("agent_runners")
    if not isinstance(runners, dict) or normalized not in runners:
        # Partial configs are used by embedders and tests. The actual Worker
        # remains fail-closed when it later resolves the runtime.
        return ""
    try:
        runtime = build_runtime(normalized, config, role=role)
        availability = runtime.availability()
        capabilities = runtime.capabilities(availability)
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        return f"{normalized} 无法初始化：{exc}"
    if capabilities.available:
        return ""
    if capabilities.readiness_state == "model-selection-required":
        return f"{normalized} 尚未为“{_role_label(role)}”选择模型。"
    detail = str(capabilities.detail or availability.detail or capabilities.readiness_state).strip()
    return f"{normalized} 尚未就绪：{detail or '请检查安装与连接配置。'}"


def require_runtime_ready(
    config: dict[str, Any],
    runtime_id: str,
    *,
    role: str = "worker",
) -> None:
    error = runtime_readiness_error(config, runtime_id, role=role)
    if error:
        raise ValueError(f"自动创作暂不可用：{error}请在“连接与模型”中完成配置后重试。")


def _role_label(role: str) -> str:
    return {
        "worker": "正文与项目任务",
        "reviewer": "审查任务",
        "planner": "规划任务",
        "steward": "全自动决策",
    }.get(str(role or "").strip().lower(), role or "当前任务")


__all__ = ["require_runtime_ready", "runtime_readiness_error"]
