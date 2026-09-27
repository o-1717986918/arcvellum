"""Application composition contracts independent of HTTP and desktop shells."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..advisor.service import ProjectAdvisor
from ..automation.controller import AutopilotService
from .bootstrap import ApplicationBootstrapService
from .lifecycle import ApplicationLifecycleManager
from .ports import ApplicationPorts
from .prompt_workbench import PromptWorkbenchService
from .style.mount_service import StyleMountApplicationService
from ..observability.agent_session_tracking import AgentSessionEventProjector
from ..persistence.scene_transactions import SceneTransactionRepository


@dataclass(frozen=True)
class ApplicationServices:
    lifecycle: ApplicationLifecycleManager
    bootstrap: ApplicationBootstrapService
    advisor: ProjectAdvisor
    autopilot: AutopilotService
    style_mounts: StyleMountApplicationService
    session_events: AgentSessionEventProjector
    prompts: PromptWorkbenchService | None = None


@dataclass(frozen=True)
class ApplicationContainer:
    config: dict[str, Any]
    ports: ApplicationPorts
    services: ApplicationServices

    def shutdown(self, *, wait: bool = True) -> None:
        self.services.autopilot.shutdown()
        self.services.bootstrap.shutdown()
        self.services.lifecycle.shutdown(wait=wait)


def build_application_container(
    config: dict[str, Any],
    ports: ApplicationPorts,
) -> ApplicationContainer:
    """Compose use cases over caller-owned ports without selecting adapters."""

    lifecycle = ApplicationLifecycleManager(config, ports)
    style_mounts = StyleMountApplicationService()
    bootstrap = ApplicationBootstrapService(config, lifecycle)
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    data_root = Path(str(application.get("data_root") or "."))
    prompts = PromptWorkbenchService(ports.persistence.prompt_layers) if ports.persistence.prompt_layers is not None else None
    session_events = AgentSessionEventProjector(
        ports.persistence.sessions,
        ports.persistence.context_ledgers,
        ports.persistence.mutation_receipts,
        mutation_listener=lambda project_root, receipt: _invalidate_for_receipt(
            ports.read_models, project_root, receipt
        ),
    )
    advisor = ProjectAdvisor(
        config,
        ports.persistence.sessions,
        runtime_pool=ports.runtime_pool,
        data_root=data_root,
        session_event_tracker=session_events,
        prompt_resolver=(lambda layer_id, root: prompts.resolve(layer_id, root).text)
        if prompts is not None else None,
    )
    autopilot = AutopilotService(
        config,
        runs=ports.persistence.autopilot,
        sessions=ports.persistence.sessions,
        plans=ports.persistence.plans,
        session_event_tracker=session_events,
        runtime_pool=ports.runtime_pool,
        execution_coordinator=ports.execution_coordinator,
        style_mount_service=style_mounts,
        prepared_context_cache=ports.prepared_context_cache,
        live_events=ports.live_events,
        scene_transactions=SceneTransactionRepository(ports.persistence.unit_of_work),
        prompt_resolver=(lambda layer_id, root: prompts.resolve(layer_id, root).text)
        if prompts is not None else None,
    )
    return ApplicationContainer(
        config=config,
        ports=ports,
        services=ApplicationServices(
            lifecycle=lifecycle,
            bootstrap=bootstrap,
            advisor=advisor,
            autopilot=autopilot,
            style_mounts=style_mounts,
            session_events=session_events,
            prompts=prompts,
        ),
    )


def _invalidate_for_receipt(read_models, project_root: str, receipt: dict[str, Any]) -> None:
    if (
        str(receipt.get("writeback_status") or "") == "applied"
        or str(receipt.get("formal_effect") or "") == "formal"
    ):
        read_models.invalidate(Path(project_root), reason="worker-writeback")


__all__ = [
    "ApplicationContainer",
    "ApplicationPorts",
    "ApplicationServices",
    "build_application_container",
]
