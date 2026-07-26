"""Public result contract returned by the formal Agent Worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    project_root: Path
    route: str
    task_id: str
    runtime: str
    run_root: Path | None
    workspace: Path | None
    message: str
    imported_outputs: tuple[str, ...] = ()
    audit_fields: dict[str, str] | None = None
    writeback_preview: dict[str, object] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": str(self.project_root),
            "route": self.route,
            "task_id": self.task_id,
            "runtime": self.runtime,
            "run_root": str(self.run_root) if self.run_root else "",
            "workspace": str(self.workspace) if self.workspace else "",
            "message": self.message,
            "imported_outputs": list(self.imported_outputs),
            "audit": self.audit_fields or {},
            "writeback_preview": self.writeback_preview or {},
        }
