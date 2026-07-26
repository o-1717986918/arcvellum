"""Behavior-preserving default plan factory for the fixed formal route."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from literary_engineering_studio_engine.orchestration import default_route_macro

from .constitution import constitution_v1
from .contracts import (
    PLAN_SCHEMA,
    CreativeExecutionPlan,
    CreativeStrategy,
    FreedomBudget,
    NarrativeInterpretation,
    PlanLifecycleStatus,
    PlanScope,
    PlanScopeKind,
)


class DefaultPlanFactory:
    """Wrap the existing route order without creating a second task graph."""

    def create(
        self,
        *,
        base_project_fingerprint: str,
        created_at: str | None = None,
    ) -> CreativeExecutionPlan:
        fingerprint = base_project_fingerprint.strip()
        if not fingerprint:
            raise ValueError("base_project_fingerprint is required")
        macro = default_route_macro()
        constitution = constitution_v1()
        plan_id = "plan-fixed-" + hashlib.sha256(
            f"{macro.macro_id}:{fingerprint}".encode("utf-8")
        ).hexdigest()[:16]
        return CreativeExecutionPlan(
            schema=PLAN_SCHEMA,
            plan_id=plan_id,
            revision=1,
            base_project_fingerprint=fingerprint,
            candidate_digest="",
            constitution_version=constitution.version,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            lifecycle_status=PlanLifecycleStatus.NORMALIZED,
            scope=PlanScope(kind=PlanScopeKind.BOOK, key="book"),
            objective="按照当前正式固定路线安全推进作品。",
            interpretation=NarrativeInterpretation(
                dramatic_problem="由现有正式项目状态决定。",
                reader_effect="由现有章节和场景契约决定。",
                chapter_function="保持当前固定路线行为，不引入自适应判断。",
            ),
            strategy=CreativeStrategy(branch_count=1),
            task_nodes=(),
            replan_rules=(),
            freedom_budget=FreedomBudget(
                max_added_tasks=0,
                max_replans_per_scope=0,
                max_parallel_read_tasks=1,
                max_branch_count=1,
                max_research_tasks=0,
                max_research_cost=0.0,
                max_analysis_to_production_ratio=0.0,
                max_plan_depth=len(macro.route_order),
                max_plan_stall_cycles=0,
            ),
            route_macro_id=macro.macro_id,
            route_sequence=macro.route_order,
            mandatory_gate_nodes=(),
        )
