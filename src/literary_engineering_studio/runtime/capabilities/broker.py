"""Policy-enforced capability invocation with bounded results and audit."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from .audit import CapabilityAuditWriter
from .context import CapabilityContext
from .contracts import (
    CapabilityPolicyError,
    CapabilityRequest,
    CapabilityResult,
    CapabilityStatus,
    HandlerOutput,
    result_digest,
)
from .handlers import build_default_registry
from .policy import CapabilityPolicy
from .registry import CapabilityRegistry


class CapabilityBroker:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry | None = None,
        policy: CapabilityPolicy | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.policy = policy or CapabilityPolicy()

    def invoke(self, context: CapabilityContext, request: CapabilityRequest) -> CapabilityResult:
        started = time.monotonic()
        try:
            self.policy.authorize(context.manifest, request)
            handler = self.registry.resolve(request.capability_id)
            output = handler(context, request.arguments)
            if not isinstance(output, HandlerOutput):
                raise TypeError("capability handler returned an invalid result")
            result = self._completed(context, request, output, started)
        except CapabilityPolicyError as exc:
            result = self._error_result(
                request,
                started,
                status=CapabilityStatus.DENIED,
                code=exc.code,
                message=str(exc),
            )
        except (LookupError, ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            result = self._error_result(
                request,
                started,
                status=CapabilityStatus.FAILED,
                code=_error_code(exc),
                message=str(exc),
            )
        CapabilityAuditWriter(context.run_root).record(request, result)
        return result

    def _completed(
        self,
        context: CapabilityContext,
        request: CapabilityRequest,
        output: HandlerOutput,
        started: float,
    ) -> CapabilityResult:
        full_payload = {"summary": output.summary, "data": output.data}
        digest = result_digest(full_payload)
        serialized = json.dumps(full_payload, ensure_ascii=False, sort_keys=True, default=str)
        artifact = ""
        data = output.data
        truncated = len(serialized) > context.manifest.max_result_chars
        if truncated:
            artifact_path = context.run_root / "capabilities" / "artifacts" / f"{request.request_id}.json"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                json.dumps(full_payload, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            artifact = artifact_path.relative_to(context.run_root).as_posix()
            data = {
                "artifact_summary": output.summary,
                "top_level_keys": sorted(str(key) for key in output.data),
                "serialized_characters": len(serialized),
            }
        return CapabilityResult(
            request_id=request.request_id,
            task_id=request.task_id,
            capability_id=request.capability_id,
            status=CapabilityStatus.COMPLETED.value,
            summary=output.summary,
            data=data,
            result_digest=digest,
            duration_ms=_duration_ms(started),
            artifact=artifact,
            truncated=truncated,
        )

    @staticmethod
    def _error_result(
        request: CapabilityRequest,
        started: float,
        *,
        status: CapabilityStatus,
        code: str,
        message: str,
    ) -> CapabilityResult:
        safe_message = message[:500]
        return CapabilityResult(
            request_id=request.request_id,
            task_id=request.task_id,
            capability_id=request.capability_id,
            status=status.value,
            summary="capability request was not completed",
            data={},
            result_digest=result_digest({"status": status.value, "code": code, "message": safe_message}),
            duration_ms=_duration_ms(started),
            error_code=code,
            error_message=safe_message,
        )


def _duration_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


def _error_code(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "source-not-found"
    if isinstance(exc, UnicodeError):
        return "source-encoding-error"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid-json"
    if isinstance(exc, LookupError):
        return "handler-not-registered"
    return "invalid-capability-request"


__all__ = ["CapabilityBroker", "CapabilityContext"]
