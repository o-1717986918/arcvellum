"""Small graph algorithms shared by orchestration policy and simulation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def graph_ancestors(
    node_id: str,
    dependencies: Mapping[str, Sequence[str]],
) -> set[str]:
    """Return transitive dependencies without ever including the origin."""

    found: set[str] = set()
    pending = list(dependencies.get(node_id, ()))
    while pending:
        current = pending.pop()
        if current == node_id or current in found:
            continue
        found.add(current)
        pending.extend(dependencies.get(current, ()))
    return found


def graph_descendants(
    dependencies: Mapping[str, Sequence[str]],
) -> dict[str, set[str]]:
    """Return transitive dependants for every known node."""

    result = {node_id: set() for node_id in dependencies}
    for values in dependencies.values():
        for dependency in values:
            result.setdefault(dependency, set())
    for node_id in dependencies:
        for ancestor in graph_ancestors(node_id, dependencies):
            result.setdefault(ancestor, set()).add(node_id)
    return result


def nodes_are_ordered(
    left: str,
    right: str,
    dependencies: Mapping[str, Sequence[str]],
) -> bool:
    """Return whether either node transitively depends on the other."""

    return (
        left in graph_ancestors(right, dependencies)
        or right in graph_ancestors(left, dependencies)
    )


__all__ = ["graph_ancestors", "graph_descendants", "nodes_are_ordered"]
