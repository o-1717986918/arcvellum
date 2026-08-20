"""Translate bounded Pi Worker failure receipts into Studio runtime semantics."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .base import RuntimeFailureKind
from .opencode_failures import classify_model_error


def worker_failure_result(
    worker_result: Mapping[str, Any], status: str, message: str
) -> tuple[str, dict[str, Any]]:
    detail = message.lower()
    no_progress = status == "blocked" and any(
        token in detail
        for token in ("no-progress", "budget exhausted", "budget_exhausted")
    )
    provider_error = str(worker_result.get("providerError") or "").strip()
    provider_failure_kind = str(worker_result.get("failureKind") or "").strip()
    provider_empty = provider_empty_response(worker_result)
    if provider_error:
        mapped = _PROVIDER_FAILURES.get(provider_failure_kind)
        if mapped is None:
            failure_kind, retryable, message = classify_model_error(provider_error)
            kind = failure_kind.value
        else:
            kind, default_retryable = mapped
            supplied_retryable = worker_result.get("providerFailureRetryable")
            retryable = (
                supplied_retryable
                if isinstance(supplied_retryable, bool)
                else default_retryable
            )
            message = provider_error
    else:
        retryable = not no_progress
        kind = (
            RuntimeFailureKind.TRANSIENT_NETWORK.value
            if provider_empty
            else RuntimeFailureKind.NO_PROGRESS.value
            if no_progress
            else RuntimeFailureKind.VALIDATION_FAILURE.value
        )
    if provider_empty and not provider_error:
        message = (
            "模型供应商返回了空响应，未产生文本、推理或工具调用；"
            "ArcVellum 将保留当前任务并按连接故障策略重试。"
        )
    provider_kind = provider_failure_kind if provider_error else (
        "provider_empty_response" if provider_empty else ""
    )
    return message, {
        "failure_kind": kind,
        "retryable": retryable,
        "provider_failure_kind": provider_kind,
    }


def provider_empty_response(worker_result: Mapping[str, Any]) -> bool:
    if str(worker_result.get("failureKind") or "") == "provider_empty_response":
        return True
    receipt = worker_result.get("reasoning_budget")
    provider_requests = worker_result.get("providerRequests")
    if provider_requests is None and isinstance(receipt, Mapping):
        provider_requests = receipt.get("provider_requests")
    try:
        request_count = int(provider_requests or 0)
        tool_calls = int(worker_result.get("toolCalls") or 0)
        reasoning_characters = int(worker_result.get("reasoningCharacters") or 0)
        text_characters = int(worker_result.get("textCharacters") or 0)
    except (TypeError, ValueError):
        return False
    written = worker_result.get("writtenOutputs")
    return (
        request_count > 0
        and tool_calls == 0
        and reasoning_characters == 0
        and text_characters == 0
        and (not isinstance(written, list) or not written)
    )


_PROVIDER_FAILURES: dict[str, tuple[str, bool]] = {
    "provider_quota": (RuntimeFailureKind.PROVIDER_QUOTA.value, False),
    "authentication_failure": (
        RuntimeFailureKind.AUTHENTICATION_FAILURE.value,
        False,
    ),
    "transient_network": (RuntimeFailureKind.TRANSIENT_NETWORK.value, True),
    "first_event_timeout": (RuntimeFailureKind.FIRST_EVENT_TIMEOUT.value, True),
    "idle_timeout": (RuntimeFailureKind.IDLE_TIMEOUT.value, True),
    "total_timeout": (RuntimeFailureKind.TOTAL_TIMEOUT.value, True),
    "model_error": (RuntimeFailureKind.MODEL_ERROR.value, False),
    "validation_failure": (RuntimeFailureKind.VALIDATION_FAILURE.value, False),
    "cancelled": (RuntimeFailureKind.NO_PROGRESS.value, False),
}


__all__ = ["provider_empty_response", "worker_failure_result"]
