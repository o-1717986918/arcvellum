"""Application orchestration for formal style-engineering Worker tasks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from literary_engineering_studio_engine.public.tasking import issue_next_task
from literary_engineering_studio_engine.public.literary import (
    ensure_style_library,
)
from literary_engineering_studio_engine.public.literary import (
    StyleSessionResult,
    StyleSourceSelection,
    prepare_style_engineering_session,
    resolve_formal_style_profile,
)
from literary_engineering_studio_engine.public.literary import (
    inspect_style_profile_version,
    plan_style_profile_version,
)


class StyleBuildIntentError(ValueError):
    code = "style_version_not_build_ready"

    def __init__(self, message: str, *, stage: str):
        super().__init__(message)
        self.stage = stage


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
        execution = self._launch_current_task(
            project,
            session.profile_dir,
            runtime=runtime,
        )
        return {
            "schema": "arcvellum/style-compile-job/v1",
            "session": _public_session(session, project),
            **execution,
        }

    def advance(
        self,
        project_root: Path,
        *,
        author_id: str,
        profile_id: str,
        runtime: str,
    ) -> dict[str, object]:
        project = project_root.expanduser().resolve()
        profile = resolve_formal_style_profile(
            project,
            author_id=author_id,
            profile_id=profile_id,
        )
        return {
            "schema": "arcvellum/style-advance-job/v1",
            **self._launch_current_task(project, profile, runtime=runtime),
        }

    def build(
        self,
        project_root: Path,
        *,
        author_id: str,
        profile_id: str,
        runtime: str,
    ) -> dict[str, object]:
        project = project_root.expanduser().resolve()
        profile = resolve_formal_style_profile(
            project,
            author_id=author_id,
            profile_id=profile_id,
        )
        plan = plan_style_profile_version(project, profile)
        stage, _ = inspect_style_profile_version(plan)
        if stage == "ready":
            return {
                "schema": "arcvellum/style-build-job/v1",
                "status": "ready",
                "style_id": plan.style_id,
                "version_id": plan.version_id,
                "content_hash": plan.content_hash,
                "job": None,
            }
        if stage != "build":
            raise StyleBuildIntentError(
                _build_block_message(stage),
                stage=stage,
            )
        execution = self._launch_current_task(
            project,
            profile,
            runtime=runtime,
        )
        return {
            "schema": "arcvellum/style-build-job/v1",
            "status": "queued",
            "style_id": plan.style_id,
            "version_id": plan.version_id,
            "content_hash": plan.content_hash,
            **execution,
        }

    def _launch_current_task(
        self,
        project: Path,
        profile: Path,
        *,
        runtime: str,
    ) -> dict[str, object]:
        relative = profile.relative_to(project).as_posix()
        issued = issue_next_task(
            project,
            route="style-engineering",
            scene=relative,
        )
        task = {
            "task_id": issued.task_id,
            "current_state": issued.current_state,
            "status": issued.status,
        }
        if issued.status == "ready" or not issued.task_id:
            return {"status": "ready", "task": task, "job": None}
        if issued.task_json_path is None:
            raise RuntimeError("style task package was not materialized")
        contract_digest = hashlib.sha256(issued.task_json_path.read_bytes()).hexdigest()
        job = self._launch_worker(
            {
                "project_root": str(project),
                "route": "style-engineering",
                "runtime": runtime.strip() or "opencode",
                "task_id": issued.task_id,
                "scene": relative,
                "idempotency_key": f"style-task:{issued.task_id}:{contract_digest}",
            }
        )
        return {"status": str(job.get("status") or "queued"), "task": task, "job": job}


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


def _build_block_message(stage: str) -> str:
    if stage == "conflict":
        return "immutable style version has an unresolved integrity conflict"
    return "style profile has not passed every formal build gate"
