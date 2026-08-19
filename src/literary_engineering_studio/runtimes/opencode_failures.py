"""Stable OpenCode provider-error classification and public messages."""

from __future__ import annotations

import json
from typing import Any

from .base import RuntimeFailureKind


def is_transient_stream_failure(value: str) -> bool:
    normalized = str(value or "").lower()
    return any(
        marker in normalized
        for marker in (
            "streaming response failed",
            "stream interrupted",
            "stream connection",
            "connection reset",
            "messageabortederror",
            "request timed out",
            "request timeout",
            "timeouterror",
        )
    )


def classify_model_error(value: str) -> tuple[RuntimeFailureKind, bool, str]:
    normalized = str(value or "").lower()
    if any(marker in normalized for marker in _QUOTA_MARKERS):
        return RuntimeFailureKind.PROVIDER_QUOTA, False, (
            "模型供应商余额或额度不足。ArcVellum 已暂停当前任务，请补充额度或切换可用模型后继续。"
        )
    if any(marker in normalized for marker in _AUTH_MARKERS):
        return RuntimeFailureKind.AUTHENTICATION_FAILURE, False, (
            "模型连接的身份验证失败。请重新登录或更新该供应商凭据后继续。"
        )
    if is_transient_stream_failure(value):
        return RuntimeFailureKind.TRANSIENT_NETWORK, True, (
            "模型流式连接短暂中断，ArcVellum 将保留当前任务并按有界策略自动重试。"
        )
    return RuntimeFailureKind.MODEL_ERROR, False, (
        "模型未能完成当前任务。诊断信息已保留，请检查模型连接或更换模型后继续。"
    )


def public_model_error(value: str) -> str:
    return classify_model_error(value)[2]


def normalize_model_warning(
    name: str,
    data: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    if name != "runner.warning" or data.get("kind") != "session.error":
        return data
    raw_error = json.dumps(data.get("detail") or {}, ensure_ascii=False)
    errors.append(raw_error)
    kind, retryable, message = classify_model_error(raw_error)
    return {
        **data,
        "detail": message,
        "failure_kind": kind.value,
        "retryable": retryable,
        "public_message": message,
    }


_QUOTA_MARKERS = (
    "insufficient balance",
    "insufficient_balance",
    "payment required",
    "quota exceeded",
    "billing quota",
    '"statuscode":402',
    '"statuscode": 402',
    "status code 402",
    "(402)",
)
_AUTH_MARKERS = (
    "invalid api key",
    "authentication failed",
    "unauthorized",
    '"statuscode":401',
    '"statuscode": 401',
    '"statuscode":403',
    '"statuscode": 403',
)
