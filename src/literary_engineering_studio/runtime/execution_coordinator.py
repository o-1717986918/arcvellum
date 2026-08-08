"""In-process project execution ownership shared by manual and automatic workers."""

from __future__ import annotations

from pathlib import Path
import hashlib
import threading

from .resources import ResourceClaim, claims_conflict, project_identity


class ProjectExecutionCoordinator:
    def __init__(self):
        self._owners: dict[str, dict[str, ResourceClaim | None]] = {}
        self._lock = threading.RLock()

    def acquire(self, project_root: str | Path, owner: str) -> bool:
        key = project_execution_key(project_root)
        with self._lock:
            owners = self._owners.setdefault(key, {})
            if owner in owners:
                return owners[owner] is None
            if owners:
                return False
            owners[owner] = None
            return True

    def acquire_claim(
        self,
        project_root: str | Path,
        owner: str,
        claim: ResourceClaim,
    ) -> bool:
        if claim.project_id != project_identity(Path(project_root)):
            raise ValueError("resource claim project does not match execution project")
        key = project_execution_key(project_root)
        with self._lock:
            owners = self._owners.setdefault(key, {})
            if owner in owners:
                return owners[owner] == claim
            if any(
                current is None or claims_conflict(current, claim).conflicts
                for current in owners.values()
            ):
                return False
            owners[owner] = claim
            return True

    def release(self, project_root: str | Path, owner: str) -> None:
        key = project_execution_key(project_root)
        with self._lock:
            owners = self._owners.get(key)
            if owners is None:
                return
            owners.pop(owner, None)
            if not owners:
                self._owners.pop(key, None)

    def owner(self, project_root: str | Path) -> str:
        with self._lock:
            owners = self._owners.get(project_execution_key(project_root), {})
            return next(iter(owners), "") if len(owners) <= 1 else ""

    def owners(self, project_root: str | Path) -> tuple[str, ...]:
        with self._lock:
            owners = self._owners.get(project_execution_key(project_root), {})
            return tuple(sorted(owners))


def project_execution_key(project_root: str | Path) -> str:
    project = str(Path(project_root).expanduser().resolve()).casefold()
    return hashlib.sha256(project.encode("utf-8")).hexdigest()[:20]
