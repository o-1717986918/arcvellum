"""Persistence port used by the orchestration audit coordinator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class CreativePlanIndex(Protocol):
    def reserve_creative_plan_revision(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]: ...

    def finalize_creative_plan_revision(
        self,
        plan_id: str,
        revision: int,
        *,
        digest: str,
    ) -> dict[str, Any]: ...

    def read_creative_plan(self, plan_id: str) -> dict[str, Any]: ...

    def read_creative_plan_revision(
        self,
        plan_id: str,
        revision: int,
    ) -> dict[str, Any]: ...

    def activate_creative_plan(
        self,
        plan_id: str,
        revision: int,
        *,
        expected_active_revision: int,
        current_project_fingerprint: str,
        verified_revision_digest: str,
        active_plan_path: Path,
        active_plan_payload: dict[str, Any],
    ) -> dict[str, Any]: ...
