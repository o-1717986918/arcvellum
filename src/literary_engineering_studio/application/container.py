"""Application composition contracts independent of HTTP and desktop shells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..advisor.service import ProjectAdvisor
from ..automation.controller import AutopilotService
from .bootstrap import ApplicationBootstrapService
from .lifecycle import ApplicationLifecycleManager
from .ports import ApplicationPorts
from .style.mount_service import StyleMountApplicationService


@dataclass(frozen=True)
class ApplicationServices:
    lifecycle: ApplicationLifecycleManager
    bootstrap: ApplicationBootstrapService
    advisor: ProjectAdvisor
    autopilot: AutopilotService
    style_mounts: StyleMountApplicationService


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
    advisor = ProjectAdvisor(config, ports.store, runtime_pool=ports.runtime_pool)
    autopilot = AutopilotService(
        config,
        ports.store,
        runtime_pool=ports.runtime_pool,
        execution_coordinator=ports.execution_coordinator,
        style_mount_service=style_mounts,
        prepared_context_cache=ports.prepared_context_cache,
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
        ),
    )


__all__ = [
    "ApplicationContainer",
    "ApplicationPorts",
    "ApplicationServices",
    "build_application_container",
]
