"""Immutable Prompt v3 intermediate representation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Mapping


PROMPT_PROGRAM_SCHEMA = "arcvellum/prompt-program/v3"


@dataclass(frozen=True)
class PromptEvidence:
    evidence_id: str
    source_ref: str
    source_sha256: str
    projection_sha256: str
    role: str
    tier: str
    fidelity: str
    body: str

    def identity(self) -> dict[str, str]:
        value = asdict(self)
        value.pop("body", None)
        return value


@dataclass(frozen=True)
class OnDemandEvidence:
    evidence_id: str
    source_ref: str
    source_sha256: str
    role: str
    reason: str


@dataclass(frozen=True)
class PromptProgram:
    schema: str
    recipe_id: str
    task_identity: Mapping[str, str]
    objective: str
    decisions: tuple[str, ...]
    constraints: tuple[str, ...]
    output_contract: Mapping[str, Any]
    evidence: tuple[PromptEvidence, ...]
    exact_on_demand: tuple[OnDemandEvidence, ...]
    stop_contract: tuple[str, ...]
    compile_metrics: Mapping[str, object]
    digest: str
    literary_brief: Mapping[str, object] = field(default_factory=dict)

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "recipe_id": self.recipe_id,
            "task_identity": dict(self.task_identity),
            "evidence": [item.identity() for item in self.evidence],
            "exact_on_demand": [asdict(item) for item in self.exact_on_demand],
            "constraint_count": len(self.constraints),
            "decision_count": len(self.decisions),
            "output_count": len(self.output_contract.get("outputs", [])),
            "literary_brief": dict(self.literary_brief),
            "compile_metrics": dict(self.compile_metrics),
            "digest": self.digest,
        }


def prompt_program_digest(
    *,
    recipe_id: str,
    task_identity: Mapping[str, str],
    objective: str,
    decisions: tuple[str, ...],
    constraints: tuple[str, ...],
    output_contract: Mapping[str, Any],
    evidence: tuple[PromptEvidence, ...],
    exact_on_demand: tuple[OnDemandEvidence, ...],
    stop_contract: tuple[str, ...],
    literary_brief: Mapping[str, object] | None = None,
) -> str:
    payload = {
        "schema": PROMPT_PROGRAM_SCHEMA,
        "recipe_id": recipe_id,
        "task_identity": dict(task_identity),
        "objective_sha256": _sha256(objective),
        "decisions": list(decisions),
        "constraints": list(constraints),
        "output_contract": output_contract,
        "evidence": [item.identity() for item in evidence],
        "exact_on_demand": [asdict(item) for item in exact_on_demand],
        "stop_contract": list(stop_contract),
        "literary_brief": dict(literary_brief or {}),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256(serialized)


def resolve_prompt_program_rollout(
    config: Mapping[str, Any] | None,
    *,
    runtime_id: str,
    task_kind: str,
    route: str = "",
    current_state: str = "",
) -> dict[str, object]:
    settings = config if isinstance(config, Mapping) else {}
    mode = str(settings.get("mode") or "off").strip().lower()
    if mode not in {"off", "shadow", "enforced"}:
        mode = "off"
    enforcement = settings.get("enforcement")
    rules = enforcement if isinstance(enforcement, Mapping) else {}
    matched = _matches_enforcement(
        rules, runtime_id, task_kind, route=route, current_state=current_state
    )
    enforced = mode == "enforced" and matched
    return {
        "schema": "arcvellum/prompt-program-rollout/v1",
        "requested_mode": mode,
        "formal_version": "v3" if enforced else "v2",
        "emit_shadow": mode == "shadow" or (mode == "enforced" and not matched),
        "matched": matched,
        "fallback": str(settings.get("fallback") or "v2"),
        "reason": (
            "prompt-v3-enforced"
            if enforced
            else "prompt-v3-shadow"
            if mode == "shadow"
            else "enforcement-not-matched"
            if mode == "enforced"
            else "prompt-v3-disabled"
        ),
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _matches_enforcement(
    rules: Mapping[str, Any],
    runtime_id: str,
    task_kind: str,
    *,
    route: str,
    current_state: str,
) -> bool:
    runtimes = _strings(rules.get("runtimes"))
    kinds = _strings(rules.get("task_kinds"))
    routes = _strings(rules.get("routes"))
    states = _strings(rules.get("states"))
    return (
        rules.get("enabled") is True
        and (not runtimes or runtime_id in runtimes)
        and (not kinds or task_kind in kinds)
        and (not routes or route in routes)
        and (not states or current_state in states)
    )


__all__ = [
    "OnDemandEvidence",
    "PROMPT_PROGRAM_SCHEMA",
    "PromptEvidence",
    "PromptProgram",
    "prompt_program_digest",
    "resolve_prompt_program_rollout",
]
