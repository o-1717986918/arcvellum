"""Finalize an Autopilot release or route it back to missing chapter exports."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .support import _now
from ..projections.whole_book_release import (
    MissingFormalChapterSources,
    WholeBookReleaseCoordinator,
)


def complete_release(
    *,
    config: dict[str, Any],
    runs: Any,
    pause: Callable[[str, str, str], None],
    run_id: str,
    project: Path,
    run: dict[str, Any],
    release_policy: str,
    coordinator_factory: Callable[[dict[str, Any]], Any] = WholeBookReleaseCoordinator,
    release_route_index: int = 6,
) -> bool:
    if release_policy != "delegated":
        pause(run_id, "release-approval-required", "全书已经完成正式路线，等待你批准最终交付。")
        return True
    try:
        release = coordinator_factory(config).release(
            project,
            approved_by="delegated-agent:creative-steward",
            autopilot_run_id=run_id,
        )
    except MissingFormalChapterSources:
        runs.update_autopilot_run(
            run_id,
            route_index=release_route_index,
            current_route="export-and-release",
            current_task_id="",
            status="running",
            stop_reason="",
            last_error="",
            finished_at="",
        )
        runs.append_autopilot_event(
            run_id,
            "release.deferred",
            {"reason": "chapter-exports-missing", "resume_route": "export-and-release"},
        )
        return False
    runs.append_autopilot_event(run_id, "release.completed", release)
    runs.update_autopilot_run(run_id, status="complete", finished_at=_now(), stop_reason="")
    runs.append_autopilot_event(
        run_id,
        "autopilot.completed",
        {"tasks_completed": run["tasks_completed"]},
    )
    return True


__all__ = ["complete_release"]
