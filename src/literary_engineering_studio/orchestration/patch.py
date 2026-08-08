"""Scene-scoped, revision-preserving Plan Patch evaluation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Callable, Mapping

from ..protocols.canonical_json import canonical_json_digest
from .candidate import parse_plan_candidate, parse_task_node_candidate
from .contracts import (
    PLAN_PATCH_SCHEMA,
    CompiledTaskGraph,
    CreativeExecutionPlan,
    CreativeExecutionPlanPatch,
    PlanPatchOperation,
    PlanPatchOperationKind,
    PlanScope,
    PlanScopeKind,
    ReplanTrigger,
    to_primitive,
)
from .lint import PlanLintContext
from .normalizer import NormalizationContext, candidate_digest
from .shadow import ShadowPlanEvaluation, evaluate_shadow_candidate
from .simulator import PlanSimulationContext


_STRATEGY_PATHS = frozenset(
    {
        "/strategy/branch_count",
        "/strategy/revision_policy",
        "/strategy/fallback_level",
        "/strategy/narrative_distance",
    }
)
@dataclass(frozen=True)
class PlanPatchDiff:
    operation: str
    target: str
    before: object
    after: object


@dataclass(frozen=True)
class ScenePlanPatchEvaluation:
    patch: CreativeExecutionPlanPatch
    candidate_payload: dict[str, Any]
    evaluation: ShadowPlanEvaluation
    base_plan_digest: str
    new_plan_digest: str
    diffs: tuple[PlanPatchDiff, ...]

    @property
    def passed(self) -> bool:
        return self.evaluation.passed


def parse_scene_plan_patch(payload: Mapping[str, Any]) -> CreativeExecutionPlanPatch:
    if str(payload.get("schema") or "") != PLAN_PATCH_SCHEMA:
        raise ValueError(f"plan patch schema must be {PLAN_PATCH_SCHEMA}")
    scope = _parse_scope(_mapping(payload, "scope"))
    if scope.kind is not PlanScopeKind.SCENE or not scope.key:
        raise ValueError("Plan Patch scope must identify one scene")
    operations = tuple(
        _parse_operation(item) for item in _mapping_list(payload, "operations")
    )
    if not operations:
        raise ValueError("Plan Patch requires at least one operation")
    affected_outputs = _text_tuple(payload.get("affected_outputs"))
    for path in affected_outputs:
        _safe_project_path(path)
    base_revision = _positive_int(payload.get("base_revision"), "base_revision")
    base_digest = str(payload.get("base_plan_digest") or "").strip()
    if not _is_sha256(base_digest):
        raise ValueError("base_plan_digest must be lowercase sha256")
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ValueError("Plan Patch reason is required")
    return CreativeExecutionPlanPatch(
        schema=PLAN_PATCH_SCHEMA,
        plan_id=_required_text(payload, "plan_id"),
        base_revision=base_revision,
        base_plan_digest=base_digest,
        scope=scope,
        trigger=ReplanTrigger(_required_text(payload, "trigger")),
        reason=reason,
        operations=operations,
        affected_outputs=affected_outputs,
    )


def evaluate_scene_plan_patch(
    base_candidate_payload: Mapping[str, Any],
    *,
    base_plan: CreativeExecutionPlan,
    patch: CreativeExecutionPlanPatch,
    normalization_context: NormalizationContext,
    lint_context: PlanLintContext,
    simulation_context_factory: Callable[[CompiledTaskGraph], PlanSimulationContext],
    used_replans: int = 0,
) -> ScenePlanPatchEvaluation:
    _validate_patch_base(
        base_candidate_payload,
        base_plan=base_plan,
        patch=patch,
        normalization_context=normalization_context,
        lint_context=lint_context,
        used_replans=used_replans,
    )
    candidate_payload, diffs = _apply_operations(
        deepcopy(dict(base_candidate_payload)),
        patch,
        max_added_tasks=base_plan.freedom_budget.max_added_tasks,
    )
    evaluation = evaluate_shadow_candidate(
        candidate_payload,
        normalization_context=replace(
            normalization_context,
            base_project_fingerprint=base_plan.base_project_fingerprint,
            plan_id=base_plan.plan_id,
            revision=base_plan.revision + 1,
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
        lint_context=replace(
            lint_context,
            current_project_fingerprint=base_plan.base_project_fingerprint,
        ),
        simulation_context_factory=simulation_context_factory,
    )
    return ScenePlanPatchEvaluation(
        patch=patch,
        candidate_payload=candidate_payload,
        evaluation=evaluation,
        base_plan_digest=creative_plan_digest(base_plan),
        new_plan_digest=creative_plan_digest(evaluation.plan),
        diffs=diffs,
    )


def creative_plan_digest(plan: CreativeExecutionPlan) -> str:
    return _digest(to_primitive(plan))


def _validate_patch_base(
    candidate_payload: Mapping[str, Any],
    *,
    base_plan: CreativeExecutionPlan,
    patch: CreativeExecutionPlanPatch,
    normalization_context: NormalizationContext,
    lint_context: PlanLintContext,
    used_replans: int,
) -> None:
    if patch.plan_id != base_plan.plan_id:
        raise RuntimeError("Plan Patch belongs to a different plan")
    if patch.base_revision != base_plan.revision:
        raise RuntimeError("Plan Patch base revision is stale")
    if patch.base_plan_digest != creative_plan_digest(base_plan):
        raise RuntimeError("Plan Patch base plan digest is stale")
    if base_plan.base_project_fingerprint != normalization_context.base_project_fingerprint:
        raise RuntimeError("Plan Patch normalization context is stale")
    if base_plan.base_project_fingerprint != lint_context.current_project_fingerprint:
        raise RuntimeError("Plan Patch lint context is stale")
    if used_replans < 0 or used_replans >= base_plan.freedom_budget.max_replans_per_scope:
        raise RuntimeError("Plan Patch exceeds the scope replan budget")
    if patch.scope.key not in _plan_scene_refs(base_plan):
        raise ValueError("Plan Patch scene is outside the base plan scope")
    parsed = parse_plan_candidate(candidate_payload)
    if candidate_digest(parsed.candidate) != base_plan.candidate_digest:
        raise RuntimeError("base candidate does not match the current plan revision")


def _apply_operations(
    payload: dict[str, Any],
    patch: CreativeExecutionPlanPatch,
    *,
    max_added_tasks: int,
) -> tuple[dict[str, Any], tuple[PlanPatchDiff, ...]]:
    diffs: list[PlanPatchDiff] = []
    added = 0
    for operation in patch.operations:
        if operation.kind is PlanPatchOperationKind.REPLACE_STRATEGY:
            diffs.append(_replace_strategy(payload, patch.scope.key, operation))
        elif operation.kind is PlanPatchOperationKind.ADD_NODE:
            added += 1
            if added > max_added_tasks:
                raise ValueError("Plan Patch adds more nodes than the Freedom Budget allows")
            diffs.append(_add_node(payload, patch.scope.key, operation))
        elif operation.kind is PlanPatchOperationKind.REPLACE_DEPENDENCY:
            diffs.append(_replace_dependency(payload, operation))
        else:  # Enum parsing makes this defensive branch unreachable.
            raise ValueError(f"unsupported Plan Patch operation: {operation.kind.value}")
    return payload, tuple(diffs)


def _replace_strategy(
    payload: dict[str, Any],
    scene_id: str,
    operation: PlanPatchOperation,
) -> PlanPatchDiff:
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        raise ValueError("base candidate strategy is missing")
    path = operation.path
    if path in _STRATEGY_PATHS:
        key = path.rsplit("/", 1)[-1]
        before = strategy.get(key)
        strategy[key] = operation.value
        return PlanPatchDiff(operation.kind.value, path, before, operation.value)
    expected = f"/strategy/scene_inventory/{scene_id}/roleplay_depth"
    if path != expected:
        raise ValueError(f"Plan Patch strategy path is not allowed: {path}")
    inventory = strategy.get("scene_inventory")
    if not isinstance(inventory, list):
        raise ValueError("base candidate scene inventory is missing")
    for item in inventory:
        if isinstance(item, dict) and str(item.get("scene_ref") or "") == scene_id:
            before = item.get("roleplay_depth")
            item["roleplay_depth"] = operation.value
            return PlanPatchDiff(operation.kind.value, path, before, operation.value)
    raise ValueError("Plan Patch scene strategy does not exist")


def _add_node(
    payload: dict[str, Any],
    scene_id: str,
    operation: PlanPatchOperation,
) -> PlanPatchDiff:
    node = operation.node
    if node is None:
        raise ValueError("add_node operation lacks a node")
    raise ValueError(
        "add_node is reserved until the formal Scheduler can bind dynamic nodes; "
        f"AO-4 cannot add {node.kind.value} without creating a second task lifecycle"
    )


def _replace_dependency(
    payload: dict[str, Any],
    operation: PlanPatchOperation,
) -> PlanPatchDiff:
    nodes = payload.get("task_nodes")
    if not isinstance(nodes, list):
        raise ValueError("base candidate task_nodes is missing")
    for item in nodes:
        if isinstance(item, dict) and str(item.get("node_id") or "") == operation.node_id:
            before = list(item.get("depends_on") or [])
            item["depends_on"] = list(operation.depends_on)
            return PlanPatchDiff(
                operation.kind.value,
                operation.node_id,
                before,
                list(operation.depends_on),
            )
    raise ValueError(f"Plan Patch dependency target does not exist: {operation.node_id}")


def _parse_operation(payload: Mapping[str, Any]) -> PlanPatchOperation:
    kind = PlanPatchOperationKind(_required_text(payload, "op"))
    if kind is PlanPatchOperationKind.REPLACE_STRATEGY:
        path = _required_text(payload, "path")
        value = payload.get("value")
        if value is None or isinstance(value, (dict, list)):
            raise ValueError("replace_strategy value must be a scalar")
        return PlanPatchOperation(kind=kind, path=path, value=value)
    if kind is PlanPatchOperationKind.ADD_NODE:
        return PlanPatchOperation(
            kind=kind,
            node=parse_task_node_candidate(_mapping(payload, "node")),
        )
    return PlanPatchOperation(
        kind=kind,
        node_id=_required_text(payload, "node_id"),
        depends_on=_text_tuple(payload.get("depends_on")),
    )


def _parse_scope(payload: Mapping[str, Any]) -> PlanScope:
    scene_ids = _text_tuple(payload.get("scene_ids"))
    key = _required_text(payload, "key")
    if scene_ids and scene_ids != (key,):
        raise ValueError("Plan Patch scope key and scene_ids must identify the same scene")
    return PlanScope(
        kind=PlanScopeKind(_required_text(payload, "kind")),
        key=key,
        volume_id=str(payload.get("volume_id") or "").strip(),
        chapter_ids=_text_tuple(payload.get("chapter_ids")),
        scene_ids=scene_ids or (key,),
    )


def _plan_scene_refs(plan: CreativeExecutionPlan) -> set[str]:
    refs = set(plan.scope.scene_ids)
    refs.update(item.scene_ref for item in plan.strategy.scene_inventory)
    refs.update(
        ref
        for node in plan.task_nodes
        for ref in node.scope_refs
        if ref.startswith("scene_")
    )
    if plan.scope.kind is PlanScopeKind.SCENE:
        refs.add(plan.scope.key)
    return refs


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def _mapping_list(payload: Mapping[str, Any], key: str) -> tuple[Mapping[str, Any], ...]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{key} must be an array of objects")
    return tuple(value)


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("expected an array of strings")
    result = tuple(str(item).strip() for item in value if str(item).strip())
    if len(result) != len(value):
        raise ValueError("array entries must be non-empty strings")
    return result


def _safe_project_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value.replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError(f"Plan Patch affected output is unsafe: {value}")
    return path


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed < 1:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _digest(value: object) -> str:
    return canonical_json_digest(value)
