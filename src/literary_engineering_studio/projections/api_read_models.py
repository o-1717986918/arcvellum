"""Cached read-model composition for the Studio HTTP API.

The API factory owns routing and mutation boundaries.  This class owns the
coherent project snapshots consumed by both HTTP endpoints and SSE streams so
they cannot quietly drift into separate cache or revision behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..observability.agent_observability import build_agent_observability
from .core_read_models import build_dashboard, build_library, build_narrative_evidence
from .delivery import build_delivery
from ..application.project_progress import build_project_progress
from .reader import build_reader_manifest, public_reader_manifest
from .workspace_revision import build_workspace_revisions


class ProjectReadModels:
    """Build revision-aware API projections for one Studio application."""

    def __init__(
        self,
        config: dict[str, Any],
        lifecycle,
        autopilot,
        *,
        dashboard_builder: Callable[[Path], dict[str, Any]] | None = None,
    ):
        self._config = config
        self._lifecycle = lifecycle
        self._autopilot = autopilot
        self._dashboard_builder = dashboard_builder or (lambda root: build_dashboard(self._config, root))

    def cached(self, key: str, root: Path, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        return self._lifecycle.read_models.get(key, root, builder)

    def dashboard(self, root: Path) -> dict[str, Any]:
        return self.cached(f"dashboard:{root}", root, lambda: self._dashboard_builder(root))

    def library(self, root: Path) -> dict[str, Any]:
        return self.cached(f"library:{root}", root, lambda: build_library(self._config, root))

    def narrative_evidence(self, root: Path) -> dict[str, Any]:
        return self.cached(
            f"narrative-evidence:{root}",
            root,
            lambda: build_narrative_evidence(self._config, root),
        )

    def reader(self, root: Path) -> dict[str, Any]:
        return self.cached(f"reader:{root}", root, lambda: public_reader_manifest(build_reader_manifest(root)))

    def progress(self, root: Path) -> dict[str, Any]:
        return self.cached(
            f"progress:{root}",
            root,
            lambda: build_project_progress(self.dashboard(root), self.library(root), self.reader(root)),
        )

    def delivery(self, root: Path) -> dict[str, Any]:
        return self.cached(
            f"delivery:{root}",
            root,
            lambda: build_delivery(self._config, root, dashboard_payload=self.dashboard(root)),
        )

    def workspace(self, root: Path) -> dict[str, Any]:
        """Return a coherent bundle for the persistent project workbench."""

        autopilot_status = self._autopilot.status(root)
        run = autopilot_status.get("run") if isinstance(autopilot_status.get("run"), dict) else {}
        events = self._lifecycle.persistence.autopilot.autopilot_events_since(
            str(run.get("run_id") or ""),
            limit=80,
        ) if run.get("run_id") else []
        dashboard = self.dashboard(root)
        sections = {
            "dashboard": dashboard,
            "library": self.library(root),
            "delivery": self.delivery(root),
            "reader_manifest": self.reader(root),
            "project_progress": self.progress(root),
            "autopilot_status": autopilot_status,
            "agent_observability": build_agent_observability(
                str(root),
                autopilot_status,
                events,
                dashboard,
                self._lifecycle.persistence.sessions.list_agent_sessions(str(root), limit=30),
                self._lifecycle.opencode_pool.status(),
            ),
        }
        source_revisions, revision = build_workspace_revisions(sections)
        return {
            "ok": True,
            "schema": "arcvellum/project-workspace-stream/v1",
            "project_root": str(root),
            "revision": revision,
            "source_revisions": source_revisions,
            **sections,
        }
