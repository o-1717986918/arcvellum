"""Deterministic, contract-driven rollout for bounded task context."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ..protocols.canonical_json import canonical_json_digest
from ..contracts import TaskPackage


_MODES = {"off", "shadow", "bounded"}
_BOUNDED_READY = "bounded-ready"


class ContextRolloutRejected(RuntimeError):
    """Raised when an explicit bounded request lacks a ready contract."""


@dataclass(frozen=True)
class ContextRolloutDecision:
    requested_mode: str
    effective_mode: str
    rollout_enabled: bool
    rollout_matched: bool
    route: str
    current_state: str
    contract_status: str
    reason: str
    policy_digest: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "arcvellum/context-rollout-decision/v1",
            **asdict(self),
        }


def resolve_context_rollout(
    task: TaskPackage,
    context_config: Mapping[str, Any] | None,
) -> ContextRolloutDecision:
    config = _mapping(context_config)
    requested = _mode(config.get("mode"))
    rollout = _normalized_rollout(config.get("bounded_rollout"))
    route = task.route.strip()
    state = task.current_state.strip()
    status = str(
        task.payload.get("context_contract_status") or ""
    ).strip()
    policy_digest = _digest(
        {
            "requested_mode": requested,
            "bounded_rollout": rollout,
        }
    )
    if requested == "off":
        return _decision(
            requested,
            "off",
            rollout,
            route,
            state,
            status,
            "requested-off",
            policy_digest,
        )
    if requested == "bounded":
        if status != _BOUNDED_READY:
            raise ContextRolloutRejected(
                "bounded context requires a bounded-ready task contract; "
                f"received {status or 'missing'} for {route}/{state}"
            )
        return _decision(
            requested,
            "bounded",
            rollout,
            route,
            state,
            status,
            "explicit-bounded-contract-ready",
            policy_digest,
            matched=True,
        )
    if not rollout["enabled"]:
        return _decision(
            requested,
            "shadow",
            rollout,
            route,
            state,
            status,
            "rollout-disabled",
            policy_digest,
        )
    reason = _mismatch_reason(rollout, route, state, status)
    matched = not reason
    return _decision(
        requested,
        "bounded" if matched else "shadow",
        rollout,
        route,
        state,
        status,
        "canary-contract-match" if matched else reason,
        policy_digest,
        matched=matched,
    )


def _decision(
    requested: str,
    effective: str,
    rollout: Mapping[str, object],
    route: str,
    state: str,
    status: str,
    reason: str,
    policy_digest: str,
    *,
    matched: bool = False,
) -> ContextRolloutDecision:
    return ContextRolloutDecision(
        requested_mode=requested,
        effective_mode=effective,
        rollout_enabled=bool(rollout["enabled"]),
        rollout_matched=matched,
        route=route,
        current_state=state,
        contract_status=status,
        reason=reason,
        policy_digest=policy_digest,
    )


def _mismatch_reason(
    rollout: Mapping[str, object],
    route: str,
    state: str,
    status: str,
) -> str:
    if route not in rollout["routes"]:
        return "route-not-allowlisted"
    if state not in rollout["states"]:
        return "state-not-allowlisted"
    if status not in rollout["contract_statuses"]:
        return "contract-status-not-allowlisted"
    if status != _BOUNDED_READY:
        return "contract-not-bounded-ready"
    return ""


def _normalized_rollout(value: object) -> dict[str, object]:
    config = _mapping(value)
    return {
        "enabled": config.get("enabled") is True,
        "routes": _strings(
            config.get("routes"),
            ("scene-development",),
        ),
        "states": _strings(
            config.get("states"),
            ("candidate-review",),
        ),
        "contract_statuses": _strings(
            config.get("contract_statuses"),
            (_BOUNDED_READY,),
        ),
    }


def _mode(value: object) -> str:
    normalized = str(value or "shadow").strip().lower()
    return normalized if normalized in _MODES else "shadow"


def _strings(
    value: object,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(value, list):
        return default
    normalized = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in value
            if str(item).strip()
        )
    )
    return normalized or default


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _digest(value: object) -> str:
    return canonical_json_digest(value)


__all__ = [
    "ContextRolloutDecision",
    "ContextRolloutRejected",
    "resolve_context_rollout",
]
