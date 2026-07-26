"""Pure literary-chain policy checks for adaptive plan graphs."""

from __future__ import annotations

from dataclasses import dataclass

from literary_engineering_studio_engine.orchestration import PlanNodeKind

from .contracts import PlanTaskNode


@dataclass(frozen=True)
class LiteraryPolicyViolation:
    code: str
    message: str
    related: tuple[str, ...]


def literary_policy_violations(
    nodes: tuple[PlanTaskNode, ...],
    dependencies: dict[str, tuple[str, ...]],
) -> tuple[LiteraryPolicyViolation, ...]:
    node_map = {node.node_id: node for node in nodes}
    ancestors = {
        node_id: _ancestors(node_id, dependencies)
        for node_id in node_map
    }
    descendants = _descendants(dependencies)
    violations: list[LiteraryPolicyViolation] = []
    for node in nodes:
        ancestor_kinds = _kinds(ancestors[node.node_id], node_map)
        descendant_kinds = _kinds(descendants[node.node_id], node_map)
        violations.extend(
            _node_violations(node, ancestor_kinds, descendant_kinds)
        )
    return tuple(violations)


def _node_violations(
    node: PlanTaskNode,
    ancestor_kinds: set[PlanNodeKind],
    descendant_kinds: set[PlanNodeKind],
) -> tuple[LiteraryPolicyViolation, ...]:
    if node.kind == PlanNodeKind.FORMAL_PROSE:
        return _prose_violations(node, ancestor_kinds, descendant_kinds)
    if node.kind == PlanNodeKind.REVISION:
        return _revision_violations(node, ancestor_kinds, descendant_kinds)
    if (
        node.kind == PlanNodeKind.EXPORT
        and PlanNodeKind.LONGFORM_AUDIT not in ancestor_kinds
    ):
        return (
            _violation(
                "export-audit",
                "formal export requires a longform audit ancestor",
                node,
            ),
        )
    return ()


def _prose_violations(
    node: PlanTaskNode,
    ancestor_kinds: set[PlanNodeKind],
    descendant_kinds: set[PlanNodeKind],
) -> tuple[LiteraryPolicyViolation, ...]:
    prerequisites = {
        PlanNodeKind.CONTEXT_PREPARATION,
        PlanNodeKind.ROLEPLAY_SIMULATION,
        PlanNodeKind.BRANCH_SIMULATION,
        PlanNodeKind.BRANCH_SELECTION,
        PlanNodeKind.SCENE_COMPOSITION,
    }
    missing = prerequisites.difference(ancestor_kinds)
    violations: list[LiteraryPolicyViolation] = []
    if missing:
        violations.append(
            LiteraryPolicyViolation(
                code="prose-prerequisites",
                message=(
                    "formal prose is missing context, RP, branch, selection, "
                    "or composition ancestors"
                ),
                related=(node.node_id, *sorted(item.value for item in missing)),
            )
        )
    if PlanNodeKind.SEMANTIC_REVIEW not in descendant_kinds:
        violations.append(
            _violation(
                "prose-review",
                "formal prose has no independent review descendant",
                node,
            )
        )
    return tuple(violations)


def _revision_violations(
    node: PlanTaskNode,
    ancestor_kinds: set[PlanNodeKind],
    descendant_kinds: set[PlanNodeKind],
) -> tuple[LiteraryPolicyViolation, ...]:
    checks = (
        (
            PlanNodeKind.FORMAL_PROSE not in ancestor_kinds,
            "revision-base",
            "revision has no formal prose ancestor",
        ),
        (
            PlanNodeKind.SEMANTIC_REVIEW not in ancestor_kinds,
            "revision-source-review",
            "revision has no review basis",
        ),
        (
            PlanNodeKind.SEMANTIC_REVIEW not in descendant_kinds,
            "revision-review",
            "revision has no fresh review descendant",
        ),
    )
    return tuple(
        _violation(code, message, node)
        for failed, code, message in checks
        if failed
    )


def _kinds(
    node_ids: set[str],
    node_map: dict[str, PlanTaskNode],
) -> set[PlanNodeKind]:
    return {node_map[node_id].kind for node_id in node_ids if node_id in node_map}


def _ancestors(
    node_id: str,
    dependencies: dict[str, tuple[str, ...]],
) -> set[str]:
    found: set[str] = set()
    pending = list(dependencies.get(node_id, ()))
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(dependencies.get(current, ()))
    return found


def _descendants(
    dependencies: dict[str, tuple[str, ...]],
) -> dict[str, set[str]]:
    result = {node_id: set() for node_id in dependencies}
    for node_id in dependencies:
        for ancestor in _ancestors(node_id, dependencies):
            result.setdefault(ancestor, set()).add(node_id)
    return result


def _violation(
    code: str,
    message: str,
    node: PlanTaskNode,
) -> LiteraryPolicyViolation:
    return LiteraryPolicyViolation(code=code, message=message, related=(node.node_id,))
