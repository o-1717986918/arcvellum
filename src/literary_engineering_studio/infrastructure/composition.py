"""Default application composition selected by HTTP and desktop adapters."""

from __future__ import annotations

from typing import Any

from ..application.container import ApplicationContainer, build_application_container
from ..config import load_config
from .defaults import build_default_application_ports


def resolve_application_container(
    config_override: dict[str, Any] | None,
    container: ApplicationContainer | None,
) -> ApplicationContainer:
    if container is not None and config_override is not None:
        raise ValueError("provide config_override or container, not both")
    if container is not None:
        return container
    config = config_override or load_config()
    return build_application_container(config, build_default_application_ports(config))


__all__ = ["resolve_application_container"]
