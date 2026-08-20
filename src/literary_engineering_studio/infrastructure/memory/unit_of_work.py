"""Lock-backed unit of work for deterministic memory adapters."""

from __future__ import annotations

from contextlib import contextmanager

from .state import MemoryPersistenceState


class MemoryUnitOfWork:
    def __init__(self, state: MemoryPersistenceState):
        self.state = state

    @contextmanager
    def read(self):
        with self.state.lock:
            yield self.state

    @contextmanager
    def write(self, *, immediate: bool = False):
        del immediate
        with self.state.lock:
            yield self.state


__all__ = ["MemoryUnitOfWork"]
