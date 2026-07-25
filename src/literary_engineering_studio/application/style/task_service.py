"""Application orchestration for formal style-engineering Worker tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from literary_engineering_studio_engine.literary.style.lab import (
    ensure_style_library,
)
from literary_engineering_studio_engine.literary.style.session import (
    StyleSessionResult,
    StyleSourceSelection,
    prepare_style_engineering_session,
)


class StyleTaskService:
    def __init__(self, launch_worker: Callable[[dict[str, str]], dict[str, object]]):
        self._launch_worker = launch_worker

    def compile(
        self,
        project_root: Path,
        library_root: Path | None,
        *,
        author_id: str,
        profile_id: str,
        display_name: str,
        training_sources: list[dict[str, str]],
        holdout_sources: list[dict[str, str]],
        runtime: str,
    ) -> dict[str, object]:
        project = project_root.expanduser().resolve()
        library = ensure_style_library(library_root)
        session = prepare_style_engineering_session(
            project,
            library,
            author_id=author_id,
            profile_id=profile_id,
            display_name=display_name,
            training_sources=_selections(training_sources),
            holdout_sources=_selections(holdout_sources),
        )
        relative = session.profile_dir.relative_to(project).as_posix()
        job = self._launch_worker(
            {
                "project_root": str(project),
                "route": "style-engineering",
                "runtime": runtime.strip() or "opencode",
                "task_id": "",
                "scene": relative,
                "idempotency_key": f"style-compile:{session.request_digest}",
            }
        )
        return {
            "schema": "arcvellum/style-compile-job/v1",
            "session": _public_session(session, project),
            "job": job,
        }


def _selections(rows: list[dict[str, str]]) -> tuple[StyleSourceSelection, ...]:
    return tuple(
        StyleSourceSelection(
            work_id=str(row.get("work_id") or ""),
            source_id=str(row.get("source_id") or ""),
        )
        for row in rows
    )


def _public_session(session: StyleSessionResult, project: Path) -> dict[str, object]:
    return {
        "session_id": f"{session.author_id}-{session.profile_id}",
        "author_id": session.author_id,
        "profile_id": session.profile_id,
        "profile_dir": session.profile_dir.relative_to(project).as_posix(),
        "request_digest": session.request_digest,
        "created": session.created,
        "status": "prepared",
    }
