"""Short-lived read-model cache keyed by a lightweight project revision fingerprint."""

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
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
    project_key: str
    generation: int
    revision: str
    quick_revision: str
    next_fallback_scan_at: float
    value: Any


class ReadModelCache:
    def __init__(self, *, ttl_seconds: float = 1.5, fallback_scan_seconds: float = 15.0):
        self.ttl_seconds = max(0.1, float(ttl_seconds))
        self.fallback_scan_seconds = max(self.ttl_seconds, float(fallback_scan_seconds))
        self._entries: dict[str, _Entry] = {}
        self._generations: dict[str, int] = {}
        self._lock = threading.RLock()
        self._key_locks: dict[tuple[str, str], tuple[Any, int]] = {}
        self._epoch = 0

    def get(self, key: str, project_root: Path, builder: Callable[[], Any], *,
            selector: Callable[[Any], Any] | None = None) -> Any:
        """Return an isolated value; selectors are trusted read-only projection code."""
        root = project_root.expanduser().resolve()
        with self._key_guard((str(root), key)):
            for _attempt in range(3):
                accepted, value = self._snapshot(key, root, builder)
                if accepted:
                    break
            else:
                raise RuntimeError("project changed while building read model; retry")
        return deepcopy(selector(value) if selector is not None else value)

    def _snapshot(self, key: str, root: Path, builder: Callable[[], Any]) -> tuple[bool, Any]:
        project_key = str(root)
        now = time.monotonic()
        quick_revision = project_quick_fingerprint(root)
        with self._lock:
            current = self._entries.get(key)
            generation = self._generations.get(project_key, 0)
            epoch = self._epoch
            if (
                current is not None
                and current.project_key == project_key
                and current.generation == generation
                and current.quick_revision == quick_revision
                and now < current.next_fallback_scan_at
            ):
                return True, current.value
        revision = project_revision_fingerprint(root)
        if (current is not None and current.project_key == project_key
                and current.generation == generation and current.revision == revision):
            with self._lock:
                if self._epoch != epoch or generation != self._generations.get(project_key, 0):
                    return False, None
                current.quick_revision = quick_revision
                current.next_fallback_scan_at = now + self.fallback_scan_seconds
            return True, current.value
        value = builder()
        final_revision = project_revision_fingerprint(root)
        stored = deepcopy(value)
        final_quick = project_quick_fingerprint(root)
        with self._lock:
            # A writer may invalidate while the slow builder is outside the metadata lock.
            if self._epoch != epoch or generation != self._generations.get(project_key, 0) or revision != final_revision:
                return False, None
            self._entries[key] = _Entry(
                project_key=project_key,
                generation=generation,
                revision=final_revision,
                quick_revision=final_quick,
                next_fallback_scan_at=time.monotonic() + self.fallback_scan_seconds,
                value=stored,
            )
        return True, value

    @contextmanager
    def _key_guard(self, identity: tuple[str, str]):
        with self._lock:
            lock, users = self._key_locks.get(identity, (threading.RLock(), 0))
            self._key_locks[identity] = (lock, users + 1)
        try:
            with lock:
                yield
        finally:
            with self._lock:
                lock, users = self._key_locks[identity]
                if users == 1:
                    del self._key_locks[identity]
                else:
                    self._key_locks[identity] = (lock, users - 1)

    def invalidate(self, project_root: Path, reason: str = "project-mutated") -> int:
        del reason
        project_key = str(project_root.expanduser().resolve())
        with self._lock:
            generation = self._generations.get(project_key, 0) + 1
            self._generations[project_key] = generation
            self._entries = {
                key: entry for key, entry in self._entries.items()
                if entry.project_key != project_key
            }
            return generation

    def revision(self, project_root: Path) -> int:
        project_key = str(project_root.expanduser().resolve())
        with self._lock:
            return self._generations.get(project_key, 0)

    def clear(self, project_root: Path | None = None) -> None:
        with self._lock:
            if project_root is not None:
                self.invalidate(project_root, reason="cache-clear")
                return
            self._entries.clear()
            self._generations.clear()
            self._epoch += 1


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


def project_quick_fingerprint(project_root: Path) -> str:
    """Return a non-recursive fingerprint for the top-level project surfaces.

    This is deliberately incomplete: it decides whether a deep scan can be
    skipped for a short cache window, not whether the project has changed
    forever.  ``project_revision_fingerprint`` remains the authoritative
    invalidation check once the cache entry expires.
    """

    root = project_root.expanduser().resolve()
    parts: list[str] = []
    for relative in WATCHED_ROOTS:
        target = root / relative
        try:
            stat = target.stat()
        except OSError:
            parts.append(f"{relative}:missing")
            continue
        kind = "file" if target.is_file() else "dir" if target.is_dir() else "other"
        parts.append(f"{relative}:{kind}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)
