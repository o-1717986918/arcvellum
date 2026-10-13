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
    stylometry = StylometryService(LabStylometryAnalysis(data_root / "stylometry-cache"), FileStylometryRepository(data_root))
    runtime = PiSceneTransactionRuntime(
        config,
        project_root=project,
        data_root=data_root.expanduser().resolve(),
        event_sink=event_sink,
        prompt_snapshot_provider=prompt_workbench.snapshot,
        creator_style_snapshot_provider=stylometry.repository.snapshot,
        style_preset_catalog_provider=stylometry.preset_catalog,
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


def build_lean_planning_service(config, *, data_root, gateway=None, event_sink=None):
    from ..runtimes.planning_natural import PlanningNaturalDelivery
    workbench = PromptWorkbenchService(FilePromptLayerRepository(data_root))
    return LeanLongformPlanningService(config, data_root=data_root, gateway=gateway, event_sink=event_sink,
        planning_delivery=PlanningNaturalDelivery(lambda key, root: workbench.resolve(key, root).text,
            lambda root: _planning_work_context(root, data_root)))


def _planning_work_context(root, data_root):
    from ..application.actor_card_store import ActorCardStore
    from ..application.creator_persona import CreatorPersonaStore
    from ..application.project_manager import read_directions
    persona = CreatorPersonaStore(data_root).read_current(root)
    if persona['status'] == 'needs-repair':
        raise RuntimeError('主创人格待修订：' + str(persona.get('literary_review', {}).get('reason', '请完成顶层人格初始化。')))
    cards = []
    for path in sorted((root / "characters/role-cards").glob("*.json")):
        stored = json.loads(path.read_text(encoding="utf-8"))
        card = ActorCardStore.read(root, stored["card"]["target"])
        sections = card["card"]["sections"]
        cards.append({"target": card["card"]["target"], "version_digest": card["digest"],
                      "expression": {key: sections[key] for key in ("PERSONA_LOAD", "PERSONALITY_CORE", "SELF_CLAIM_EXAMPLES", "FOOD_PREFERENCE")}})
    return {"creator_persona": persona.get("active"), "actor_expression_versions": cards,
            "author_direction": [row for row in read_directions(root, limit=200)
                                 if row["status"] == "active" and row["source_kind"] == "author_intent"]}
