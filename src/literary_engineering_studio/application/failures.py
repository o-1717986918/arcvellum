"""Stable user-facing projections for internal workflow failures."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


FAILURE_PRESENTATION_SCHEMA = "arcvellum/failure-presentation/v1"


@dataclass(frozen=True)
class RecoveryAction:
    action_id: str
    label: str
    kind: str = "retry"
    target: str = "overview"


@dataclass(frozen=True)
class FailurePresentation:
    code: str
    category: str
    title: str
    summary: str
    impact: str
    recovery_actions: tuple[RecoveryAction, ...]
    retryable: bool
    requires_user_action: bool
    technical_detail: str
    schema: str = FAILURE_PRESENTATION_SCHEMA

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recovery_actions"] = [asdict(item) for item in self.recovery_actions]
        return payload


@dataclass(frozen=True)
class _FailureRule:
    code: str
    category: str
    title: str
    summary: str
    impact: str
    patterns: tuple[str, ...]
    retryable: bool = True
    requires_user_action: bool = False
    actions: tuple[RecoveryAction, ...] = (
        RecoveryAction("resume", "让 ArcVellum 整理后继续"),
    )


_RULES = (
    _FailureRule(
        code="prompt_input_over_budget",
        category="task_context",
        title="本次任务携带的资料过多",
        summary="ArcVellum 在调用模型前发现任务资料超过安全上限，已阻止超长提示词继续消耗额度。",
        impact="当前任务尚未写入正式作品；已有正文和设定不会丢失。",
        patterns=("prompt v3 lint failed", "prompt hard limit", "prompt soft limit", "prompt exceeds"),
        actions=(
            RecoveryAction("compact-and-resume", "精简本次资料并继续"),
            RecoveryAction("open-diagnostics", "查看技术详情", "diagnostics", "agent-observability"),
        ),
    ),
    _FailureRule(
        code="repair_timed_out",
        category="runtime_repair",
        title="自动修订没有在时限内完成",
        summary="模型已经尝试修正产物，但修订阶段长时间没有形成可验收结果。",
        impact="系统保留原任务和候选差异，不会把未通过检查的内容写入正式作品。",
        patterns=("repair timeout", "repair timed out", "修订超时"),
        actions=(
            RecoveryAction("retry-repair", "重新连接并继续修订"),
            RecoveryAction("open-diagnostics", "查看修订记录", "diagnostics", "agent-observability"),
        ),
    ),
    _FailureRule(
        code="agent_no_progress",
        category="agent_progress",
        title="创作 Agent 连续两轮没有形成新成果",
        summary="Agent 重复了相同操作，系统已停止空转，避免继续消耗时间和额度。",
        impact="正式作品没有被破坏；当前任务仍停留在原来的门禁位置。",
        patterns=("no-progress guard", "no progress guard", "model produced no visible activity", "no visible activity"),
        actions=(
            RecoveryAction("replan-and-resume", "重新整理任务后继续"),
            RecoveryAction("open-diagnostics", "查看 Agent 活动", "diagnostics", "agent-observability"),
        ),
    ),
    _FailureRule(
        code="output_validation_failed",
        category="artifact_validation",
        title="候选成果没有通过写入前检查",
        summary="Agent 已返回内容，但缺少必要产物或格式不符合当前任务合同。",
        impact="不合格内容仍在隔离区，尚未进入正式作品。",
        patterns=("sandbox output still fails deterministic preflight", "deterministic preflight", "validation failure"),
        actions=(
            RecoveryAction("repair-and-resume", "按检查结果修订并继续"),
            RecoveryAction("open-diagnostics", "查看缺少的产物", "diagnostics", "agent-observability"),
        ),
    ),
    _FailureRule(
        code="state_writeback_needs_revision",
        category="workflow_gate",
        title="人物状态候选需要重新归属",
        summary="正文已经保留，但人物或关系变化尚未能归入明确角色，系统已停止重复审查。",
        impact="当前场景停在状态写回阶段；正文不会丢失，也不会把不确定变化写入人物档案。",
        patterns=("state patch has unresolved character or relationship changes",),
        actions=(
            RecoveryAction("refresh-task", "重建人物状态候选并继续"),
            RecoveryAction("open-workflow", "查看当前步骤", "navigate", "overview"),
        ),
    ),
    _FailureRule(
        code="workflow_evidence_pending",
        category="workflow_gate",
        title="创作流程还缺一份正式证据",
        summary="上一阶段的内容可能已经生成，但状态机还没有收到完整的审查或完成凭据。",
        impact="后续步骤暂时不会越过门禁，已完成的内容仍然保留。",
        patterns=("sidecar incomplete", "sidecar missing", "agent_tasks.md", "agent_completion", "completion marker"),
        actions=(
            RecoveryAction("complete-evidence", "补齐当前任务证据并继续"),
            RecoveryAction("open-workflow", "查看当前步骤", "navigate", "overview"),
        ),
    ),
    _FailureRule(
        code="source_contract_changed",
        category="stale_context",
        title="修订依据已经发生变化",
        summary="当前修订任务引用的正文版本不再是最新版本，系统拒绝把旧意见应用到新正文。",
        impact="正式正文保持不变，需要依据最新版本重新准备修订任务。",
        patterns=("requires the exact revision source", "candidate mismatch", "does not match"),
        actions=(RecoveryAction("refresh-task", "刷新任务依据并继续"),),
    ),
    _FailureRule(
        code="model_authentication_required",
        category="model_connection",
        title="模型连接需要重新授权",
        summary="当前模型服务没有通过身份验证，ArcVellum 暂时无法继续调用创作能力。",
        impact="项目与任务均已保存，完成模型连接后可以从原处继续。",
        patterns=("authentication", "unauthorized", "invalid api key", "model-authentication-required"),
        retryable=False,
        requires_user_action=True,
        actions=(RecoveryAction("open-connections", "打开连接与模型", "navigate", "settings"),),
    ),
    _FailureRule(
        code="provider_quota_required",
        category="model_connection",
        title="模型服务额度不足",
        summary="当前模型服务拒绝了新的请求，通常是额度、余额或频率限制所致。",
        impact="项目进度已经保存，补充额度或切换模型后可以继续。",
        patterns=("quota", "insufficient balance", "provider-billing-required", "rate limit"),
        retryable=False,
        requires_user_action=True,
        actions=(RecoveryAction("open-connections", "检查模型与额度", "navigate", "settings"),),
    ),
)


_STOP_REASON_RULES = {
    "provider-billing-required": "provider_quota_required",
    "model-authentication-required": "model_authentication_required",
    "model-connection-temporarily-unavailable": "agent_no_progress",
    "task-runtime-limit-exceeded": "repair_timed_out",
}


def present_failure(
    message: str = "",
    *,
    stop_reason: str = "",
    status: str = "",
) -> FailurePresentation | None:
    """Convert unstable implementation text into one stable product contract."""

    detail = str(message or "").strip()
    reason = str(stop_reason or "").strip()
    if not detail and not reason:
        return None
    selected_code = _STOP_REASON_RULES.get(reason)
    haystack = f"{reason}\n{detail}".lower()
    rule = next(
        (
            item
            for item in _RULES
            if item.code == selected_code
            or any(pattern in haystack for pattern in item.patterns)
        ),
        None,
    )
    if rule is None:
        paused = status in {"paused", "blocked", "failed"}
        return FailurePresentation(
            code="workflow_attention_required",
            category="workflow",
            title="创作流程需要处理",
            summary="ArcVellum 已停在当前安全节点，没有继续写入未经确认的内容。",
            impact="现有作品和任务记录均已保留，可以查看详情后从原处继续。",
            recovery_actions=(
                RecoveryAction("resume", "检查后继续"),
                RecoveryAction("open-diagnostics", "查看技术详情", "diagnostics", "agent-observability"),
            ),
            retryable=not paused or reason not in {"controller-error"},
            requires_user_action=paused,
            technical_detail=detail or reason,
        )
    return FailurePresentation(
        code=rule.code,
        category=rule.category,
        title=rule.title,
        summary=rule.summary,
        impact=rule.impact,
        recovery_actions=rule.actions,
        retryable=rule.retryable,
        requires_user_action=rule.requires_user_action,
        technical_detail=detail or reason,
    )


def present_run(run: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return an API-safe run projection while preserving the stored diagnostic."""

    if not isinstance(run, dict):
        return None
    projected = dict(run)
    failure = present_failure(
        str(run.get("last_error") or ""),
        stop_reason=str(run.get("stop_reason") or ""),
        status=str(run.get("status") or ""),
    )
    projected["failure"] = failure.as_dict() if failure else None
    if failure:
        projected["last_error"] = failure.summary
    return projected


def failure_identity(
    message: str,
    *,
    stop_reason: str = "",
    route: str = "",
    task_id: str = "",
) -> str:
    """Build a dedupe identity that survives changing counts and raw wording."""

    failure = present_failure(message, stop_reason=stop_reason)
    code = failure.code if failure else "workflow_attention_required"
    stable_task = re.sub(r"(?:[-_:]?attempt[-_:]?\d+|[-_:]?\d+)$", "", task_id.lower())
    return ":".join(part for part in (code, route.lower(), stable_task) if part)
