"""Short-lived read-model cache keyed by a lightweight project revision fingerprint."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any, Callable


WATCHED_ROOTS = (
    "project.yaml",
    "canon",
    "characters",
    "drafts",
    "manuscript",
    "plot",
    "reviews",
    "scenes",
    "state",
    "workflow",
)

IGNORED_DERIVED_PATHS = {
    "workflow/route_state.json",
    "workflow/route_state.md",
    "workflow/workflow_contract.json",
    "workflow/workflow_contract.md",
}
IGNORED_DERIVED_PREFIXES = (
    "workflow/dashboard/",
    "workflow/runtime_choices/",
)


@dataclass
class _Entry:
    revision: str
    expires_at: float
    value: Any


class ReadModelCache:
    def __init__(self, *, ttl_seconds: float = 1.5):
        self.ttl_seconds = max(0.1, float(ttl_seconds))
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.RLock()

    def get(self, key: str, project_root: Path, builder: Callable[[], Any]) -> Any:
        now = time.monotonic()
        revision = project_revision_fingerprint(project_root)
        with self._lock:
            current = self._entries.get(key)
            if current is not None and current.revision == revision:
                current.expires_at = now + self.ttl_seconds
                return deepcopy(current.value)
            value = builder()
            self._entries[key] = _Entry(revision, now + self.ttl_seconds, deepcopy(value))
            return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def project_revision_fingerprint(project_root: Path) -> str:
    root = project_root.expanduser().resolve()
    count = 0
    total_size = 0
    newest = 0
    for relative in WATCHED_ROOTS:
        target = root / relative
        if target.is_file():
            files = (target,)
        elif target.is_dir():
            files = (item for item in target.rglob("*") if item.is_file())
        else:
            continue
        for path in files:
            relative_path = path.relative_to(root).as_posix()
            if relative_path in IGNORED_DERIVED_PATHS or relative_path.startswith(IGNORED_DERIVED_PREFIXES):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            count += 1
            total_size += stat.st_size
            newest = max(newest, stat.st_mtime_ns)
    return f"{count}:{total_size}:{newest}"
