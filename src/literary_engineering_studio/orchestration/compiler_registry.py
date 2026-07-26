"""Read-only bindings from plan node kinds to the Engine task catalog."""

from __future__ import annotations

from literary_engineering_studio_engine.orchestration import (
    DEFAULT_ROUTE_ORDER,
    FormalTaskCapability,
    PlanNodeKind,
    formal_task_capabilities,
)

from .contracts import PlanTaskNode, TaskBinding


_ALLOWED_PARAMETERS = {
    "builtin:none/v1": frozenset(),
    "builtin:creative-analysis/v1": frozenset({"depth", "focus", "question"}),
    "builtin:asset-candidate/v1": frozenset({"asset_kind", "asset_id"}),
    "builtin:roleplay-depth/v1": frozenset({"roleplay_depth", "participants"}),
    "builtin:branch-simulation/v1": frozenset({"branch_count", "scoring_profile"}),
    "builtin:formal-prose/v1": frozenset(
        {"narrative_distance", "style_version", "target_hanzi"}
    ),
    "builtin:revision-policy/v1": frozenset(
        {"base_revision", "revision_policy", "fallback_level"}
    ),
}


class CompilerRegistry:
    def __init__(
        self,
        capabilities: tuple[FormalTaskCapability, ...] | None = None,
    ) -> None:
        catalog = capabilities or formal_task_capabilities()
        self._by_kind = {item.node_kind: item for item in catalog}
        if len(self._by_kind) != len(catalog):
            raise ValueError("compiler registry contains duplicate node kinds")

    def resolve(self, node: PlanTaskNode) -> TaskBinding:
        try:
            capability = self._by_kind[node.kind]
        except KeyError as exc:
            raise ValueError(f"no formal task binding for node kind: {node.kind.value}") from exc
        allowed = _ALLOWED_PARAMETERS.get(capability.parameter_schema)
        if allowed is None:
            raise ValueError(f"unsupported parameter schema: {capability.parameter_schema}")
        unknown = sorted(item.name for item in node.parameters if item.name not in allowed)
        if unknown:
            raise ValueError(
                f"parameters are not allowed by {capability.parameter_schema}: "
                + ", ".join(unknown)
            )
        return _binding(capability)

    @property
    def routes(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                [*DEFAULT_ROUTE_ORDER, *(item.route for item in self._by_kind.values())]
            )
        )

    def catalog_projection(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "capability_id": item.capability_id,
                "node_kind": item.node_kind.value,
                "route": item.route,
                "allowed_task_types": list(item.allowed_task_types),
                "supported_scopes": list(item.supported_scopes),
                "agent_role": item.agent_role,
                "parameter_schema": item.parameter_schema,
                "required_gate_ids": list(item.mandatory_gate_ids),
                "resource_templates": list(item.resource_templates),
                "progress_kind": item.progress_kind,
            }
            for item in sorted(self._by_kind.values(), key=lambda value: value.node_kind.value)
        )


def _binding(capability: FormalTaskCapability) -> TaskBinding:
    return TaskBinding(
        capability_id=capability.capability_id,
        node_kind=capability.node_kind,
        route=capability.route,
        allowed_task_types=capability.allowed_task_types,
        supported_scopes=capability.supported_scopes,
        agent_role=capability.agent_role,
        parameter_schema=capability.parameter_schema,
        required_gate_ids=capability.mandatory_gate_ids,
        resource_templates=capability.resource_templates,
        progress_kind=capability.progress_kind,
    )
