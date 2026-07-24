"""In-process project execution ownership shared by manual and automatic workers."""

from __future__ import annotations

from pathlib import Path
import hashlib
import threading


class ProjectExecutionCoordinator:
    def __init__(self):
        self._owners: dict[str, str] = {}
        self._lock = threading.RLock()

    def acquire(self, project_root: str | Path, owner: str) -> bool:
        key = project_execution_key(project_root)
        with self._lock:
            current = self._owners.get(key)
            if current and current != owner:
                return False
            self._owners[key] = owner
            return True

    def release(self, project_root: str | Path, owner: str) -> None:
        key = project_execution_key(project_root)
        with self._lock:
            if self._owners.get(key) == owner:
                self._owners.pop(key, None)

    def owner(self, project_root: str | Path) -> str:
        with self._lock:
            return self._owners.get(project_execution_key(project_root), "")


def project_execution_key(project_root: str | Path) -> str:
    project = str(Path(project_root).expanduser().resolve()).casefold()
    return hashlib.sha256(project.encode("utf-8")).hexdigest()[:20]
