"""Production composition for one lean literary scene runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..application.scene_transaction import SceneTransactionService, TransactionEventSink
from ..automation.lean_scene_loop import LeanSceneRunCoordinator
from ..persistence.scene_transactions import SceneTransactionRepository
from ..runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from .project_scene_transactions import AtomicProjectSceneCommitter, ProjectSceneBriefProvider


@dataclass(frozen=True)
class LeanSceneRuntimeBundle:
    runtime: PiSceneTransactionRuntime
    service: SceneTransactionService
    coordinator: LeanSceneRunCoordinator


def build_lean_scene_runtime(
    config: dict[str, Any],
    *,
    project_root: Path,
    data_root: Path,
    repository: SceneTransactionRepository,
    event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    transaction_events: TransactionEventSink | None = None,
) -> LeanSceneRuntimeBundle:
    project = project_root.expanduser().resolve()
    runtime = PiSceneTransactionRuntime(
        config,
        project_root=project,
        data_root=data_root.expanduser().resolve(),
        event_sink=event_sink,
    )
    service = SceneTransactionService(
        briefs=ProjectSceneBriefProvider(),
        runtime=runtime,
        critic=runtime,
        repository=repository,
        commits=AtomicProjectSceneCommitter(project),
        events=transaction_events,
    )
    return LeanSceneRuntimeBundle(
        runtime=runtime,
        service=service,
        coordinator=LeanSceneRunCoordinator(
            project_root=project,
            data_root=data_root,
            service=service,
            repository=repository,
            revision_runtime=runtime,
        ),
    )


__all__ = ["LeanSceneRuntimeBundle", "build_lean_scene_runtime"]
