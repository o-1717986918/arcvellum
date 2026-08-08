"""User-facing maturity projection for production orchestration capabilities."""

from __future__ import annotations

from typing import Any

from ..orchestration.settings import OrchestrationMode, OrchestrationSettings


def orchestration_capabilities(
    settings: OrchestrationSettings,
) -> list[dict[str, Any]]:
    """Describe support maturity separately from the current enabled state."""

    adaptive_active = (
        settings.enabled
        and settings.effective_mode is not OrchestrationMode.FIXED
    )
    return [
        _capability(
            "fixed-route",
            "固定正式路线",
            "production",
            "active",
            "任务状态机、审查、晋升与写回门禁已用于正式创作，并始终可作为回退路线。",
        ),
        _capability(
            "adaptive-planning",
            "自适应创作策略",
            "preview",
            "active" if adaptive_active else "available",
            "Agent 可以在不可删除的文学门禁内调整任务顺序与推演深度。",
        ),
        _capability(
            "chapter-horizon",
            "章节前瞻",
            "preview",
            _flag_state(settings, settings.production_chapter_horizon),
            "按章节事实与风险维护短期创作视野；关闭时继续使用固定场景路线。",
        ),
        _capability(
            "serial-bundle-execution",
            "串行任务束",
            "preview",
            _flag_state(settings, settings.bundle_execution),
            "把可连续完成的任务编成有停止边界的串行任务束，不并发生成正文。",
        ),
        _capability(
            "campaign-runtime",
            "长程创作安全点",
            "preview",
            _flag_state(settings, settings.campaign_runtime),
            "以正式内容证据记录安全点，并在失败时执行有界恢复与停止。",
        ),
        _capability(
            "typed-event-streams",
            "可恢复事件流",
            "production",
            "active",
            "任务、自动创作与策略事件支持续传、心跳和明确终态。",
        ),
        _capability(
            "agent-observability",
            "Agent 执行观测",
            "production",
            "active",
            "展示真实任务、会话与审计事件，不暴露凭证、正文上下文或隐藏推理。",
        ),
        _capability(
            "cross-task-session-reuse",
            "跨任务会话复用",
            "contract",
            "unavailable",
            "当前 Runner 不能证明工作区重绑定和增量消息边界，因此保持关闭。",
            user_visible=False,
        ),
    ]
def _flag_state(settings: OrchestrationSettings, enabled: bool) -> str:
    return "active" if settings.enabled and enabled else "available"


def _capability(
    capability_id: str,
    label: str,
    maturity: str,
    state: str,
    detail: str,
    *,
    user_visible: bool = True,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "label": label,
        "maturity": maturity,
        "state": state,
        "detail": detail,
        "user_visible": user_visible,
    }
