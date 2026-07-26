"""Parse model-authored plan candidates while removing machine-owned fields."""

from __future__ import annotations

from typing import Any, Mapping

from literary_engineering_studio_engine.orchestration import PlanNodeKind

from .contracts import (
    CANDIDATE_SCHEMA,
    CandidateParseResult,
    CreativeExecutionPlanCandidate,
    CreativeStrategy,
    FreedomBudget,
    NarrativeInterpretation,
    PlanAssumption,
    PlanContribution,
    PlanParameter,
    PlanScope,
    PlanScopeKind,
    PlanTaskNode,
    ProgressContract,
    PromisePolicy,
    ReplanRule,
    ReplanTrigger,
    RevisionPolicy,
    RoleplayDepth,
    SceneStrategy,
)


MACHINE_OWNED_FIELDS = frozenset(
    {
        "plan_id",
        "revision",
        "base_project_fingerprint",
        "constitution_version",
        "created_at",
        "compiled_graph_digest",
        "mandatory_gate_nodes",
        "approved_by",
        "lifecycle_status",
        "route_macro_id",
        "route_sequence",
    }
)
_CANDIDATE_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "objective",
        "interpretation",
        "strategy",
        "task_nodes",
        "replan_rules",
        "freedom_request",
    }
)
_TASK_NODE_FIELDS = frozenset(
    {
        "node_id",
        "kind",
        "scope_refs",
        "depends_on",
        "requested_capabilities",
        "parameters",
        "contribution",
        "progress_contract",
    }
)


def parse_plan_candidate(payload: Mapping[str, Any]) -> CandidateParseResult:
    if str(payload.get("schema") or "") != CANDIDATE_SCHEMA:
        raise ValueError(f"candidate schema must be {CANDIDATE_SCHEMA}")
    warnings = [
        f"machine-owned field ignored: {key}"
        for key in sorted(MACHINE_OWNED_FIELDS.intersection(payload))
    ]
    warnings.extend(
        f"unknown candidate field ignored: {key}"
        for key in sorted(set(payload).difference(_CANDIDATE_FIELDS, MACHINE_OWNED_FIELDS))
    )
    candidate = CreativeExecutionPlanCandidate(
        schema=CANDIDATE_SCHEMA,
        scope=_scope(_mapping(payload, "scope")),
        objective=_required_text(payload, "objective"),
        interpretation=_interpretation(_mapping(payload, "interpretation")),
        strategy=_strategy(_mapping(payload, "strategy")),
        task_nodes=tuple(_task_node(item) for item in _mapping_list(payload, "task_nodes")),
        replan_rules=tuple(_replan_rule(item) for item in _mapping_list(payload, "replan_rules")),
        freedom_request=_freedom_budget(_mapping(payload, "freedom_request")),
    )
    return CandidateParseResult(candidate=candidate, warnings=tuple(warnings))


def _scope(payload: Mapping[str, Any]) -> PlanScope:
    return PlanScope(
        kind=PlanScopeKind(_required_text(payload, "kind")),
        key=_required_text(payload, "key"),
        volume_id=str(payload.get("volume_id") or "").strip(),
        chapter_ids=_text_tuple(payload.get("chapter_ids")),
        scene_ids=_text_tuple(payload.get("scene_ids")),
    )


def _interpretation(payload: Mapping[str, Any]) -> NarrativeInterpretation:
    assumptions = tuple(
        PlanAssumption(
            statement=_required_text(item, "statement"),
            evidence_refs=_text_tuple(item.get("evidence_refs")),
        )
        for item in _mapping_list(payload, "assumptions", required=False)
    )
    return NarrativeInterpretation(
        dramatic_problem=_required_text(payload, "dramatic_problem"),
        reader_effect=_required_text(payload, "reader_effect"),
        chapter_function=_required_text(payload, "chapter_function"),
        assumptions=assumptions,
        uncertainties=_text_tuple(payload.get("uncertainties")),
    )


def _strategy(payload: Mapping[str, Any]) -> CreativeStrategy:
    inventory = tuple(
        SceneStrategy(
            scene_ref=_required_text(item, "scene_ref"),
            function=_required_text(item, "function"),
            pace=_required_text(item, "pace"),
            roleplay_depth=RoleplayDepth(_required_text(item, "roleplay_depth")),
        )
        for item in _mapping_list(payload, "scene_inventory", required=False)
    )
    promise = _mapping(payload, "promise_policy", required=False)
    return CreativeStrategy(
        scene_inventory=inventory,
        branch_count=int(payload.get("branch_count") or 3),
        revision_policy=RevisionPolicy(
            str(payload.get("revision_policy") or RevisionPolicy.TARGETED_THEN_REWRITE.value)
        ),
        narrative_distance=str(payload.get("narrative_distance") or "adaptive").strip(),
        promise_policy=PromisePolicy(
            resolve=_text_tuple(promise.get("resolve")),
            defer=_text_tuple(promise.get("defer")),
        ),
    )


def _task_node(payload: Mapping[str, Any]) -> PlanTaskNode:
    unknown = sorted(set(payload).difference(_TASK_NODE_FIELDS))
    if unknown:
        raise ValueError("task node contains unsupported fields: " + ", ".join(unknown))
    contribution = _mapping(payload, "contribution")
    progress = _mapping(payload, "progress_contract", required=False)
    parameters = _mapping(payload, "parameters", required=False)
    return PlanTaskNode(
        node_id=_required_text(payload, "node_id"),
        kind=PlanNodeKind(_required_text(payload, "kind")),
        scope_refs=_text_tuple(payload.get("scope_refs")),
        depends_on=_text_tuple(payload.get("depends_on")),
        requested_capabilities=_text_tuple(payload.get("requested_capabilities")),
        parameters=tuple(
            PlanParameter(name=str(key), value=_parameter_value(value))
            for key, value in sorted(parameters.items())
        ),
        contribution=PlanContribution(
            kind=_required_text(contribution, "kind"),
            description=_required_text(contribution, "description"),
        ),
        progress_contract=ProgressContract(
            formal_artifact_delta=_text_tuple(progress.get("formal_artifact_delta")),
            obligations_fulfilled=_text_tuple(progress.get("obligations_fulfilled")),
            obligations_deferred=_text_tuple(progress.get("obligations_deferred")),
            target_hanzi=int(progress.get("target_hanzi") or 0),
            word_tolerance=float(progress.get("word_tolerance") or 0.08),
            maximum_open_review_notes=int(progress.get("maximum_open_review_notes") or 0),
            expected_state_patch=str(progress.get("expected_state_patch") or "").strip(),
        ),
    )


def _replan_rule(payload: Mapping[str, Any]) -> ReplanRule:
    return ReplanRule(
        trigger=ReplanTrigger(_required_text(payload, "trigger")),
        action=_required_text(payload, "action"),
        threshold=int(payload.get("threshold") or 1),
    )


def _freedom_budget(payload: Mapping[str, Any]) -> FreedomBudget:
    defaults = FreedomBudget()
    return FreedomBudget(
        max_added_tasks=int(_number(payload, "max_added_tasks", defaults.max_added_tasks)),
        max_replans_per_scope=int(
            _number(payload, "max_replans_per_scope", defaults.max_replans_per_scope)
        ),
        max_parallel_read_tasks=int(
            _number(payload, "max_parallel_read_tasks", defaults.max_parallel_read_tasks)
        ),
        max_branch_count=int(_number(payload, "max_branch_count", defaults.max_branch_count)),
        max_research_tasks=int(_number(payload, "max_research_tasks", defaults.max_research_tasks)),
        max_research_cost=float(_number(payload, "max_research_cost", defaults.max_research_cost)),
        max_analysis_to_production_ratio=float(
            _number(
                payload,
                "max_analysis_to_production_ratio",
                defaults.max_analysis_to_production_ratio,
            )
        ),
        max_plan_depth=int(_number(payload, "max_plan_depth", defaults.max_plan_depth)),
        max_plan_stall_cycles=int(
            _number(payload, "max_plan_stall_cycles", defaults.max_plan_stall_cycles)
        ),
    )


def _mapping(
    payload: Mapping[str, Any],
    key: str,
    *,
    required: bool = True,
) -> Mapping[str, Any]:
    value = payload.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def _mapping_list(
    payload: Mapping[str, Any],
    key: str,
    *,
    required: bool = True,
) -> tuple[Mapping[str, Any], ...]:
    value = payload.get(key)
    if value is None and not required:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{key} must be an array of objects")
    return tuple(value)


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("expected an array of strings")
    result = tuple(str(item).strip() for item in value if str(item).strip())
    if len(result) != len(value):
        raise ValueError("array entries must be non-empty strings")
    return result


def _parameter_value(value: Any) -> str | int | float | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, int, float)):
        return value
    raise ValueError("plan parameters only allow string, number, or boolean values")


def _number(payload: Mapping[str, Any], key: str, default: int | float) -> int | float:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return value
