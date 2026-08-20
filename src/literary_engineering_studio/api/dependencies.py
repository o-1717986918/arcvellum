"""Dependency factories kept outside the HTTP application assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..application.archaeology import ArchaeologyApplicationService
from ..application.style import (
    StyleApplicationService,
    StyleAuthoringService,
    StyleMountApplicationService,
)
from ..application.style.task_service import StyleTaskService
from ..core_read_models import style_library
from .routers.archaeology import ArchaeologyRouterDependencies
from .routers.style_lab import StyleLabRouterDependencies


def archaeology_router_dependencies() -> ArchaeologyRouterDependencies:
    application = ArchaeologyApplicationService()
    return ArchaeologyRouterDependencies(
        options=application.options,
        catalog=application.catalog,
        workbench=application.workbench,
        import_source=application.import_source,
    )


def style_lab_dependencies(
    config: dict[str, Any],
    *,
    mounts: StyleMountApplicationService,
    launch_style_worker: Callable[[dict[str, str]], dict[str, object]],
    invalidate_project: Callable[[Path, str], Any] | None = None,
) -> StyleLabRouterDependencies:
    application = StyleApplicationService()
    return StyleLabRouterDependencies(
        config=config,
        style_library=lambda settings, root: style_library(settings, root),
        style_authors=application.authors,
        style_versions=lambda library, project: application.version_catalog(
            library,
            project_root=project,
        ),
        style_workbench=lambda project, library: application.workbench(
            project,
            library,
        ),
        style_version_detail=lambda project, style_id, version_id: application.version_detail(
            project,
            style_id=style_id,
            version_id=version_id,
        ),
        authoring=StyleAuthoringService(),
        tasks=StyleTaskService(launch_style_worker),
        mounts=mounts,
        invalidate_project=invalidate_project or (lambda _root, _reason: None),
    )
