"""Pure single-writer policy checks for adaptive plan graphs."""

from __future__ import annotations

from literary_engineering_studio_engine.public.orchestration import PlanNodeKind

from ..protocols.violations import RelatedContractViolation
from .contracts import PlanTaskNode
from .graph_algorithms import nodes_are_ordered


WriterPolicyViolation = RelatedContractViolation


def writer_policy_violations(
    nodes: tuple[PlanTaskNode, ...],
    dependencies: dict[str, tuple[str, ...]],
) -> tuple[WriterPolicyViolation, ...]:
    violations: list[WriterPolicyViolation] = []
    writers_by_scope: dict[str, list[PlanTaskNode]] = {}
    for node in nodes:
        if node.kind in {PlanNodeKind.FORMAL_PROSE, PlanNodeKind.REVISION}:
            for scope in node.scope_refs:
                writers_by_scope.setdefault(scope, []).append(node)
    for scope, writers in writers_by_scope.items():
        prose_ids = [
            node.node_id for node in writers if node.kind == PlanNodeKind.FORMAL_PROSE
        ]
        if len(prose_ids) > 1:
            violations.append(
                WriterPolicyViolation(
                    code="multiple-prose-writers",
                    message=f"scope {scope} has multiple formal prose writers",
                    related=tuple(prose_ids),
                )
            )
        for index, left in enumerate(writers):
            for right in writers[index + 1 :]:
                if _unordered(left.node_id, right.node_id, dependencies):
                    violations.append(
                        WriterPolicyViolation(
                            code="parallel-creative-writers",
                            message=(
                                "formal prose and revisions for one scope "
                                "must be serialized"
                            ),
                            related=(left.node_id, right.node_id),
                        )
                    )
    return tuple(violations)


def _unordered(
    left: str,
    right: str,
    dependencies: dict[str, tuple[str, ...]],
) -> bool:
    return not nodes_are_ordered(left, right, dependencies)
