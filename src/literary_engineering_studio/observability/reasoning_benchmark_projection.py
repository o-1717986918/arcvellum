"""Content-safe reasoning-budget projection for runtime reports."""

from __future__ import annotations

from typing import Mapping


def reasoning_budget_projection(
    manifest: Mapping[str, object],
    events: list[dict[str, object]],
    usage: Mapping[str, object],
) -> dict[str, object]:
    profile = _mapping(manifest.get("execution_profile"))
    contract = _mapping(profile.get("reasoning_budget"))
    requested = _mapping(contract.get("requested"))
    runtime = _mapping(manifest.get("runtime_metadata"))
    receipt = _mapping(runtime.get("reasoning_budget_receipt"))
    actual, actual_tokens = _actual_projection(receipt, events, usage)
    total_target = _optional_int(requested.get("total_tokens"))
    return {
        "status": str(contract.get("status") or "unavailable"),
        "provider_support": str(
            receipt.get("provider_support")
            or contract.get("provider_support")
            or "unknown"
        ),
        "receipt_status": str(receipt.get("status") or "unavailable"),
        "requested": _requested_projection(requested),
        "actual": actual,
        "comparison": {
            "reasoning_token_delta": (
                actual_tokens - total_target
                if actual_tokens is not None and total_target is not None
                else "unavailable"
            ),
        },
    }


def _requested_projection(requested: Mapping[str, object]) -> dict[str, object]:
    fields = (
        "initial_level",
        "maximum_level",
        "per_request_tokens",
        "total_tokens",
        "max_provider_requests",
        "max_escalations",
        "over_budget_action",
    )
    return {key: requested[key] for key in fields if key in requested}


def _actual_projection(
    receipt: Mapping[str, object],
    events: list[dict[str, object]],
    usage: Mapping[str, object],
) -> tuple[dict[str, object], int | None]:
    receipt_tokens = _optional_int(receipt.get("actual_tokens"))
    reasoning_reported = receipt_tokens is not None or _reasoning_usage_reported(events)
    actual_tokens = receipt_tokens
    if actual_tokens is None and reasoning_reported:
        actual_tokens = _optional_int(usage.get("reasoning_tokens"))
    receipt_requests = _optional_int(receipt.get("provider_requests"))
    event_requests = sum(
        1 for item in events if item.get("event") == "runner.provider.request.started"
    )
    requests_reported = receipt_requests is not None or event_requests > 0
    requests = receipt_requests if receipt_requests is not None else event_requests
    return (
        {
            "reasoning_tokens": actual_tokens if actual_tokens is not None else "unavailable",
            "reasoning_tokens_reported": reasoning_reported,
            "provider_requests_observed": requests if requests_reported else "unavailable",
            "provider_requests_reported": requests_reported,
        },
        actual_tokens,
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value not in {None, "", "unavailable"} else None
    except (TypeError, ValueError):
        return None


def _reasoning_usage_reported(events: list[dict[str, object]]) -> bool:
    for item in events:
        if item.get("event") != "usage.updated":
            continue
        usage = _mapping(item.get("usage"))
        if "reasoning" in usage or "reasoning_tokens" in usage:
            return True
    return False


__all__ = ["reasoning_budget_projection"]
