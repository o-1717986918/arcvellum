"""Compatibility facade for the creative-director domain package.

New code belongs in :mod:`literary_engineering_studio_engine.director`.
This module deliberately keeps the legacy import path stable for existing CLI,
API, and third-party integrations while the implementation stays domain-based.
"""

from __future__ import annotations

from .director import (
    DirectorBootstrapResult,
    DirectorToolLoopResult,
    DirectorTurnResult,
    bootstrap_project_from_direction,
    build_director_status,
    director_project_slug,
    run_director_turn,
)
from .director import bootstrap as _bootstrap
from .director import contracts as _contracts
from .director import helpers as _helpers
from .director import loop as _loop
from .director import prompts as _prompts
from .director import records as _records
from .director import routing as _routing
from .director import service as _service
from .director import status as _status


def _export_legacy_symbols(module: object) -> None:
    for name, value in vars(module).items():
        if not name.startswith("__"):
            globals().setdefault(name, value)


for _module in (_contracts, _bootstrap, _helpers, _status, _routing, _prompts, _records, _loop, _service):
    _export_legacy_symbols(_module)


__all__ = [
    "DirectorBootstrapResult",
    "DirectorToolLoopResult",
    "DirectorTurnResult",
    "bootstrap_project_from_direction",
    "build_director_status",
    "director_project_slug",
    "run_director_turn",
]
