"""Pure deterministic validation for normalized creative plans."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from literary_engineering_studio_engine.public.orchestration import (
    PlanNodeKind,
    formal_task_capability,
    mandatory_gates_for,
)

from ..protocols.canonical_json import canonical_json_digest
from .budget_policy import budget_range_errors
from .constitution import constitution_v1
from .contracts import CreativeExecutionPlan, FreedomBudget, PlanTaskNode, to_primitive
from .literary_policy import literary_policy_violations
from .scene_strategy_policy import scene_strategy_violations
from .writer_policy import writer_policy_violations


class PlanIssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(frozen=True)
class PlanIssue:
    code: str
    severity: PlanIssueSeverity
    message: str
    node_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanLintContext:
    current_project_fingerprint: str
    known_scope_refs: frozenset[str]
    allowed_capability_ids: frozenset[str]
    authorized_budget: FreedomBudget


@dataclass(frozen=True)
class PlanLintResult:
    status: str
    issues: tuple[PlanIssue, ...]
    digest: str
    plan_digest: str

    @property
    def passed(self) -> bool:
        return not any(issue.severity == PlanIssueSeverity.ERROR for issue in self.issues)


def lint_plan(plan: CreativeExecutionPlan, *, context: PlanLintContext) -> PlanLintResult:
    issues: list[PlanIssue] = []
    _lint_identity(plan, context, issues)
    node_map = {node.node_id: node for node in plan.task_nodes}
    dependencies = _lint_graph(plan.task_nodes, node_map, issues)
    _lint_budget(plan, context, issues)
    _lint_nodes(plan, context, node_map, dependencies, issues)
    for violation in scene_strategy_violations(plan):
        _error(issues, violation.code, violation.message, violation.node_ids)
    for violation in literary_policy_violations(plan.task_nodes, dependencies):
        _error(issues, violation.code, violation.message, violation.related)
    ordered = tuple(
        sorted(
            issues,
            key=lambda item: (
                _severity_order(item.severity),
                item.code,
                item.node_ids,
                item.message,
            ),
        )
    )
    status = "fail" if any(item.severity == PlanIssueSeverity.ERROR for item in ordered) else (
        "warn" if ordered else "pass"
    )
    return PlanLintResult(
        status=status,
        issues=ordered,
        digest=_digest(ordered),
        plan_digest=_digest(plan),
    )


def _lint_identity(
    plan: CreativeExecutionPlan,
    context: PlanLintContext,
    issues: list[PlanIssue],
) -> None:
    if plan.constitution_version != constitution_v1().version:
        _error(issues, "constitution-version", "plan constitution version is unsupported")
    if plan.base_project_fingerprint != context.current_project_fingerprint:
        _error(issues, "stale-project-revision", "plan base project fingerprint is stale")
    if plan.revision < 1:
        _error(issues, "revision", "plan revision must be positive")
    if plan.route_macro_id == "fixed-formal-route.v1" and plan.task_nodes:
        _error(issues, "fixed-macro-nodes", "fixed route macro cannot carry adaptive task nodes")
    if plan.route_macro_id == "explicit-task-graph.v1" and plan.route_sequence:
        _error(issues, "explicit-route-sequence", "explicit task graph cannot declare a route sequence")


def _lint_graph(
    nodes: tuple[PlanTaskNode, ...],
    node_map: dict[str, PlanTaskNode],
    issues: list[PlanIssue],
) -> dict[str, tuple[str, ...]]:
    if len(node_map) != len(nodes):
        _error(issues, "duplicate-node-id", "plan node IDs must be unique")
    dependencies = {node.node_id: node.depends_on for node in nodes}
    for node in nodes:
        missing = tuple(dep for dep in node.depends_on if dep not in node_map)
        if missing:
            _error(
                issues,
                "missing-dependency",
                "node references dependencies that do not exist",
                (node.node_id, *missing),
            )
        if node.node_id in node.depends_on:
            _error(issues, "self-dependency", "node cannot depend on itself", (node.node_id,))
    cycle = _cycle_path(dependencies)
    if cycle:
        _error(issues, "dag-cycle", "plan task graph contains a cycle", cycle)
    if len(nodes) > 1:
        depended_on = {dependency for values in dependencies.values() for dependency in values}
        for node in nodes:
            if not node.depends_on and node.node_id not in depended_on:
                _error(issues, "orphan-node", "plan node is isolated from the task graph", (node.node_id,))
    return dependencies


def _lint_budget(
    plan: CreativeExecutionPlan,
    context: PlanLintContext,
    issues: list[PlanIssue],
) -> None:
    budget = plan.freedom_budget
    approved = context.authorized_budget
    for name, message in budget_range_errors(budget):
        _error(issues, "freedom-budget-range", f"{name} {message}")
    for name in FreedomBudget.__dataclass_fields__:
        if getattr(budget, name) > getattr(approved, name):
            _error(issues, "freedom-budget", f"plan exceeds authorized budget: {name}")
    if len(plan.task_nodes) > budget.max_plan_depth:
        _error(issues, "plan-depth", "plan contains more nodes than its depth budget")
    added = sum(
        node.kind in {PlanNodeKind.CREATIVE_ANALYSIS, PlanNodeKind.ASSET_CANDIDATE}
        for node in plan.task_nodes
    )
    if added > budget.max_added_tasks:
        _error(issues, "added-task-budget", "plan adds too many optional analysis or asset tasks")
    if len(plan.replan_rules) > budget.max_replans_per_scope:
        _error(issues, "replan-budget", "plan declares more replan rules than authorized")
    if plan.strategy.branch_count > budget.max_branch_count:
        _error(issues, "branch-budget", "strategy branch count exceeds Freedom Budget")
    production = sum(
        node.kind
        in {
            PlanNodeKind.FORMAL_PROSE,
            PlanNodeKind.REVISION,
            PlanNodeKind.STATE_EVOLUTION,
            PlanNodeKind.CANON_EVOLUTION,
            PlanNodeKind.EXPORT,
        }
        for node in plan.task_nodes
    )
    analysis = sum(
        node.kind in {PlanNodeKind.CREATIVE_ANALYSIS, PlanNodeKind.ROLEPLAY_SIMULATION}
        for node in plan.task_nodes
    )
    if production and analysis / production > budget.max_analysis_to_production_ratio:
        _error(issues, "analysis-ratio", "analysis task ratio exceeds the authorized plan budget")


def _lint_nodes(
    plan: CreativeExecutionPlan,
    context: PlanLintContext,
    node_map: dict[str, PlanTaskNode],
    dependencies: dict[str, tuple[str, ...]],
    issues: list[PlanIssue],
) -> None:
    gate_map = {binding.node_id: set(binding.gate_ids) for binding in plan.mandatory_gate_nodes}
    for node in plan.task_nodes:
        _lint_node_scope(node, context, issues)
        _lint_node_capabilities(node, context, gate_map, issues)
        _lint_node_progress(node, issues)
    if set(gate_map).difference(node_map):
        _error(issues, "gate-orphan", "mandatory Gate binding references an unknown node")
    if set(node_map).difference(gate_map):
        _error(issues, "gate-binding", "every plan node requires a machine Gate binding")
    for violation in writer_policy_violations(plan.task_nodes, dependencies):
        _error(issues, violation.code, violation.message, violation.related)


def _lint_node_scope(
    node: PlanTaskNode,
    context: PlanLintContext,
    issues: list[PlanIssue],
) -> None:
    if not node.scope_refs:
        _error(issues, "scope", "plan node has no scope reference", (node.node_id,))
    unknown_scopes = tuple(ref for ref in node.scope_refs if ref not in context.known_scope_refs)
    if context.known_scope_refs and unknown_scopes:
        _error(issues, "unknown-scope", "plan node references unknown scope", (node.node_id, *unknown_scopes))
    if not node.contribution.kind or not node.contribution.description:
        _error(issues, "progress-contribution", "plan node has no verifiable contribution", (node.node_id,))


def _lint_node_capabilities(
    node: PlanTaskNode,
    context: PlanLintContext,
    gate_map: dict[str, set[str]],
    issues: list[PlanIssue],
) -> None:
    unknown = tuple(
        item for item in node.requested_capabilities if item not in context.allowed_capability_ids
    )
    if unknown:
        _error(
            issues,
            "capability",
            "plan node requests capabilities outside policy",
            (node.node_id, *unknown),
        )
    required_gates = set(mandatory_gates_for(node_kind=node.kind.value))
    if not required_gates.issubset(gate_map.get(node.node_id, set())):
        _error(issues, "mandatory-gate", "plan node is missing machine-owned Gates", (node.node_id,))
    capability = formal_task_capability(node.kind)
    if capability.agent_role == "main-creative-agent" and node.kind == PlanNodeKind.SEMANTIC_REVIEW:
        _error(issues, "reviewer-role", "semantic review cannot use the creative writer role", (node.node_id,))


def _lint_node_progress(node: PlanTaskNode, issues: list[PlanIssue]) -> None:
    progress = node.progress_contract
    if node.kind == PlanNodeKind.FORMAL_PROSE and (
        progress.target_hanzi <= 0 or not progress.formal_artifact_delta
    ):
        _error(
            issues,
            "prose-progress",
            "formal prose requires a positive Hanzi target and formal artifact delta",
            (node.node_id,),
        )
    if node.kind == PlanNodeKind.STATE_EVOLUTION and not progress.expected_state_patch:
        _error(issues, "state-progress", "state evolution requires an expected patch", (node.node_id,))


def _cycle_path(dependencies: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> tuple[str, ...]:
        if node in visiting:
            start = stack.index(node)
            return tuple([*stack[start:], node])
        if node in visited:
            return ()
        visiting.add(node)
        stack.append(node)
        for dependency in dependencies.get(node, ()):
            cycle = visit(dependency)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return ()

    for node in dependencies:
        cycle = visit(node)
        if cycle:
            return cycle
    return ()


def _error(
    issues: list[PlanIssue],
    code: str,
    message: str,
    node_ids: tuple[str, ...] = (),
) -> None:
    issues.append(PlanIssue(code, PlanIssueSeverity.ERROR, message, node_ids))


def _warning(
    issues: list[PlanIssue],
    code: str,
    message: str,
    node_ids: tuple[str, ...] = (),
) -> None:
    issues.append(PlanIssue(code, PlanIssueSeverity.WARNING, message, node_ids))


def _severity_order(value: PlanIssueSeverity) -> int:
    return {
        PlanIssueSeverity.ERROR: 0,
        PlanIssueSeverity.WARNING: 1,
        PlanIssueSeverity.NOTE: 2,
    }[value]


def _digest(value: object) -> str:
    return canonical_json_digest(to_primitive(value))
