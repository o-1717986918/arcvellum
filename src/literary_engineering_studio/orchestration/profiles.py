"""Machine-owned profiles for adaptive orchestration Agents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..runtime.capabilities.contracts import CapabilityId


PROFILE_REVISION = "arcvellum/orchestration-agent-profiles/2026-07-26.1"


class OrchestrationAgentRole(str, Enum):
    PLANNER = "orchestration-planner"
    REVIEWER = "orchestration-reviewer"


@dataclass(frozen=True)
class OrchestrationAgentProfile:
    profile_id: str
    role: OrchestrationAgentRole
    purpose: str
    allowed_capability_ids: tuple[str, ...]
    output_schema: str
    network_policy: str
    subagent_policy: str
    emission_mode: str
    can_write_formal_files: bool
    can_activate_plan: bool
    requires_independent_session: bool
    revision: str = PROFILE_REVISION

    def as_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "role": self.role.value,
            "purpose": self.purpose,
            "allowed_capability_ids": list(self.allowed_capability_ids),
            "output_schema": self.output_schema,
            "network_policy": self.network_policy,
            "subagent_policy": self.subagent_policy,
            "emission_mode": self.emission_mode,
            "can_write_formal_files": self.can_write_formal_files,
            "can_activate_plan": self.can_activate_plan,
            "requires_independent_session": self.requires_independent_session,
            "revision": self.revision,
        }


PLANNER_PROFILE = OrchestrationAgentProfile(
    profile_id="adaptive-planner.v1",
    role=OrchestrationAgentRole.PLANNER,
    purpose="Interpret bounded project evidence and propose a creative execution plan candidate.",
    allowed_capability_ids=(
        CapabilityId.PROJECT_QUERY.value,
        CapabilityId.SCHEMA_INSPECT.value,
        CapabilityId.TEXT_STATISTICS.value,
        CapabilityId.REFERENCE_SEARCH.value,
    ),
    output_schema="arcvellum/creative-execution-plan-candidate/v1",
    network_policy="deny",
    subagent_policy="analysis_only",
    emission_mode="structured_response",
    can_write_formal_files=False,
    can_activate_plan=False,
    requires_independent_session=False,
)


REVIEWER_PROFILE = OrchestrationAgentProfile(
    profile_id="orchestration-reviewer.v1",
    role=OrchestrationAgentRole.REVIEWER,
    purpose="Critically review an exact plan candidate and its deterministic evidence.",
    allowed_capability_ids=(
        CapabilityId.PROJECT_QUERY.value,
        CapabilityId.SCHEMA_INSPECT.value,
        CapabilityId.TEXT_STATISTICS.value,
        CapabilityId.REFERENCE_SEARCH.value,
        CapabilityId.ASSET_DIFF.value,
    ),
    output_schema="arcvellum/orchestration-review-judgment/v1",
    network_policy="deny",
    subagent_policy="deny",
    emission_mode="structured_response",
    can_write_formal_files=False,
    can_activate_plan=False,
    requires_independent_session=True,
)


def orchestration_profile(role: OrchestrationAgentRole | str) -> OrchestrationAgentProfile:
    normalized = OrchestrationAgentRole(role)
    return PLANNER_PROFILE if normalized == OrchestrationAgentRole.PLANNER else REVIEWER_PROFILE
