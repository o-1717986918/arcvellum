"""Scene-development command dispatch for the formal literary pipeline."""

from __future__ import annotations

from .scene_continuity import HANDLERS as CONTINUITY_HANDLERS
from .scene_prose import HANDLERS as PROSE_HANDLERS
from .scene_simulation import HANDLERS as SIMULATION_HANDLERS


SCENE_HANDLERS = {
    **PROSE_HANDLERS,
    **CONTINUITY_HANDLERS,
    **SIMULATION_HANDLERS,
}


def handle(args, parser) -> int | None:
    command_handler = SCENE_HANDLERS.get(args.command)
    return command_handler(args, parser) if command_handler else None
