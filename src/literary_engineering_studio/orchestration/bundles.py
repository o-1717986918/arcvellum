"""Deterministic Execution Bundle contracts and compiler (AO-6, W6-7A).

An ``ExecutionBundle`` is a controlled execution optimization over compiled
task nodes, not a second task lifecycle.  The compiler only emits bundles
from whitelist templates; it never creates tasks, never executes, and never
activates a plan.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal, Sequence

from literary_engineering_studio_engine.public.orchestration import PlanNodeKind

from ..protocols.violations import ContractViolation
from .contracts import CompiledTaskGraph


_BUNDLE_ID_CONTRACT = "execution-bundle-id/v2"


@dataclass(frozen=True)
class BundleTemplate:
    template_id: str
    scope_kind: Literal["chapter", "scene"]
    node_kinds: tuple[PlanNodeKind, ...]
    agent_role: str
    stop_before: tuple[PlanNodeKind, ...]


@dataclass(frozen=True)
class ExecutionBundle:
    bundle_id: str
    plan_id: str
    template_id: str
    scope_kind: Literal["chapter", "scene"]
    scope_key: str
    step_node_ids: tuple[str, ...]
    agent_role: str
    expected_outputs: tuple[str, ...]
    base_revision: str
    context_snapshot_hash: str
    atomic_writeback_group: str
    stop_before: tuple[str, ...]


BundleViolation = ContractViolation


def bundle_template_catalog() -> tuple[BundleTemplate, ...]:
    """Return the machine-owned whitelist of bundle templates."""
    return (
        BundleTemplate(
            template_id="chapter-planning",
            scope_kind="chapter",
            node_kinds=(PlanNodeKind.CREATIVE_ANALYSIS,),
            agent_role="creative-analysis-agent",
            stop_before=(
                PlanNodeKind.ASSET_CANDIDATE,
                PlanNodeKind.CHAPTER_AUDIT,
                PlanNodeKind.LONGFORM_AUDIT,
            ),
        ),
        BundleTemplate(
            template_id="scene-analysis",
            scope_kind="scene",
            node_kinds=(
                PlanNodeKind.ROLEPLAY_SIMULATION,
                PlanNodeKind.BRANCH_SIMULATION,
            ),
            agent_role="main-review-agent",
            stop_before=(PlanNodeKind.BRANCH_SELECTION,),
        ),
        BundleTemplate(
            template_id="scene-authoring",
            scope_kind="scene",
            node_kinds=(PlanNodeKind.FORMAL_PROSE,),
            agent_role="main-creative-agent",
            stop_before=(
                PlanNodeKind.SEMANTIC_REVIEW,
                PlanNodeKind.REVISION,
            ),
        ),
        BundleTemplate(
            template_id="scene-quality",
            scope_kind="scene",
            node_kinds=(PlanNodeKind.SEMANTIC_REVIEW,),
            agent_role="main-review-agent",
            stop_before=(
                PlanNodeKind.REVISION,
                PlanNodeKind.STATE_EVOLUTION,
                PlanNodeKind.CANON_EVOLUTION,
            ),
        ),
        BundleTemplate(
            template_id="scene-state-extraction",
            scope_kind="scene",
            node_kinds=(PlanNodeKind.STATE_EVOLUTION,),
            agent_role="state-analyst",
            stop_before=(
                PlanNodeKind.CANON_EVOLUTION,
                PlanNodeKind.SEMANTIC_REVIEW,
            ),
        ),
    )


def bundle_template(template_id: str) -> BundleTemplate:
    for template in bundle_template_catalog():
        if template.template_id == template_id:
            return template
    raise ValueError(f"unsupported bundle template: {template_id}")


def compile_bundles(
    graph: CompiledTaskGraph,
    *,
    template_id: str | None = None,
    scope_key: str | None = None,
    context_snapshot_hash: str = "",
) -> tuple[ExecutionBundle, ...]:
    """Compile whitelisted bundles from a compiled task graph."""
    templates = (
        (bundle_template(template_id),)
        if template_id is not None
        else bundle_template_catalog()
    )
    bundles: list[ExecutionBundle] = []
    for template in templates:
        scope_keys = _scope_keys(graph, template.scope_kind, scope_key)
        for current_scope in scope_keys:
            bundle = _compile_for_scope(
                graph,
                template,
                scope_key=current_scope,
                context_snapshot_hash=context_snapshot_hash,
            )
            if bundle is not None:
                bundles.append(bundle)
    return tuple(bundles)


def bundle_violations(bundle: ExecutionBundle) -> tuple[BundleViolation, ...]:
    """Return deterministic structural violations for a bundle."""
    issues: list[BundleViolation] = []
    if not bundle.step_node_ids:
        issues.append(
            BundleViolation(
                code="empty-step-nodes",
                message="step_node_ids must not be empty",
            )
        )
    if not bundle.agent_role:
        issues.append(
            BundleViolation(
                code="missing-agent-role",
                message="agent_role must not be empty",
            )
        )
    if not bundle.base_revision:
        issues.append(
            BundleViolation(
                code="missing-base-revision",
                message="base_revision must not be empty",
            )
        )
    if bundle.scope_kind not in {"chapter", "scene"}:
        issues.append(
            BundleViolation(
                code="invalid-scope-kind",
                message="scope_kind must be chapter or scene",
            )
        )
    if not bundle.atomic_writeback_group:
        issues.append(
            BundleViolation(
                code="missing-writeback-group",
                message="atomic_writeback_group must not be empty",
            )
        )
    if not bundle.stop_before:
        issues.append(
            BundleViolation(
                code="missing-stop-boundary",
                message="stop_before must not be empty",
            )
        )
    return tuple(issues)


def _compile_for_scope(
    graph: CompiledTaskGraph,
    template: BundleTemplate,
    *,
    scope_key: str,
    context_snapshot_hash: str,
) -> ExecutionBundle | None:
    allowed_kinds = set(template.node_kinds)
    selected: list[str] = []
    expected: list[str] = []
    for node in graph.nodes:
        if node.kind in allowed_kinds and scope_key in node.scope_refs:
            selected.append(node.node_id)
            expected.extend(node.progress_contract.formal_artifact_delta)
    if not selected:
        return None
    bundle_id = _bundle_id(
        graph,
        template.template_id,
        scope_key,
        selected,
        context_snapshot_hash=context_snapshot_hash,
    )
    return ExecutionBundle(
        bundle_id=bundle_id,
        plan_id=graph.plan_id,
        template_id=template.template_id,
        scope_kind=template.scope_kind,
        scope_key=scope_key,
        step_node_ids=tuple(dict.fromkeys(selected)),
        agent_role=template.agent_role,
        expected_outputs=tuple(dict.fromkeys(expected)),
        base_revision=graph.base_project_fingerprint,
        context_snapshot_hash=context_snapshot_hash,
        atomic_writeback_group=f"{template.template_id}:{scope_key}",
        stop_before=tuple(kind.value for kind in template.stop_before),
    )


def _scope_keys(
    graph: CompiledTaskGraph,
    scope_kind: str,
    scope_key: str | None,
) -> tuple[str, ...]:
    keys: set[str] = set()
    for node in graph.nodes:
        for ref in node.scope_refs:
            if _ref_scope_kind(ref) == scope_kind:
                keys.add(ref)
    ordered = sorted(keys)
    if scope_key is not None:
        if scope_key not in ordered:
            return ()
        return (scope_key,)
    return tuple(ordered)


def _ref_scope_kind(ref: str) -> str:
    if ref.startswith("chapter_"):
        return "chapter"
    if ref.startswith("scene_"):
        return "scene"
    return ""


def _bundle_id(
    graph: CompiledTaskGraph,
    template_id: str,
    scope_key: str,
    node_ids: Sequence[str],
    *,
    context_snapshot_hash: str,
) -> str:
    digest = hashlib.sha256(
        "|".join(
            (
                _BUNDLE_ID_CONTRACT,
                graph.plan_id,
                str(graph.plan_revision),
                graph.base_project_fingerprint,
                graph.graph_digest,
                context_snapshot_hash,
                template_id,
                scope_key,
                *node_ids,
            )
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{template_id}-{scope_key}-{digest}"
