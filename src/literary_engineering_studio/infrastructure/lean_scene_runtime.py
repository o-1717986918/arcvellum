"""Production composition for one lean literary scene runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..application.scene_transaction import SceneTransactionService, TransactionEventSink
from ..application.lean_longform_planning import LeanLongformPlanningService
from ..application.prompt_workbench import PromptWorkbenchService
from ..automation.lean_scene_loop import LeanSceneRunCoordinator
from ..persistence.scene_transactions import SceneTransactionRepository
from ..persistence.prompt_layers import FilePromptLayerRepository
from ..runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from .project_scene_transactions import AtomicProjectSceneCommitter, ProjectSceneBriefProvider
from .stylometry_analysis import LabStylometryAnalysis
from ..persistence.stylometry import FileStylometryRepository
from ..application.style.stylometry_service import StylometryService
from ..application.style.stylometry_contracts import LabDocument
import json


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
    planning: LeanLongformPlanningService | None = None,
) -> LeanSceneRuntimeBundle:
    project = project_root.expanduser().resolve()
    prompt_workbench = PromptWorkbenchService(FilePromptLayerRepository(data_root))
    stylometry = StylometryService(LabStylometryAnalysis(), FileStylometryRepository(data_root))
    runtime = PiSceneTransactionRuntime(
        config,
        project_root=project,
        data_root=data_root.expanduser().resolve(),
        event_sink=event_sink,
        prompt_snapshot_provider=prompt_workbench.snapshot,
        creator_style_snapshot_provider=stylometry.repository.snapshot,
        creator_style_measure_provider=lambda root, text, version: LabDocument("stylometric-host/v1",
            json.dumps(stylometry.measure(root, text, version_id=version), ensure_ascii=False)),
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
            planning=planning,
        ),
    )


__all__ = ["LeanSceneRuntimeBundle", "build_lean_scene_runtime"]
