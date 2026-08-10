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
    reasoning_reported = _reasoning_usage_reported(events)
    actual_tokens = _optional_int(usage.get("reasoning_tokens")) if reasoning_reported else None
    provider_requests = sum(
        1 for item in events if item.get("event") == "runner.provider.request.started"
    )
    provider_requests_reported = provider_requests > 0
    total_target = _optional_int(requested.get("total_tokens"))
    return {
        "status": str(contract.get("status") or "unavailable"),
        "provider_support": str(contract.get("provider_support") or "unknown"),
        "requested": {
            key: requested[key]
            for key in (
                "initial_level",
                "maximum_level",
                "per_request_tokens",
                "total_tokens",
                "max_provider_requests",
                "max_escalations",
                "over_budget_action",
            )
            if key in requested
        },
        "actual": {
            "reasoning_tokens": actual_tokens if actual_tokens is not None else "unavailable",
            "reasoning_tokens_reported": reasoning_reported,
            "provider_requests_observed": (
                provider_requests if provider_requests_reported else "unavailable"
            ),
            "provider_requests_reported": provider_requests_reported,
        },
        "comparison": {
            "reasoning_token_delta": (
                actual_tokens - total_target
                if actual_tokens is not None and total_target is not None
                else "unavailable"
            ),
        },
    }


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
