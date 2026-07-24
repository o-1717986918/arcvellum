"""Stable command-line facade for Literary Engineering Workbench.

Parser registration and command groups live in dedicated modules.  This file
intentionally owns only policy enforcement and deterministic dispatch.
"""

from __future__ import annotations

from .commands.agent import handle as _handle_agent
from .commands.assets import handle as _handle_assets
from .commands.formal import handle as _handle_formal
from .commands.legacy import handle as _handle_legacy
from .commands.longform import handle as _handle_longform
from .parser import build_parser
from .policy import FORMAL_HELP_COMMANDS, STUDIO_DISABLED_COMMANDS
from .commands.projects import handle as _handle_project
from .commands.scene import handle as _handle_scene


def main(argv=None) -> int:
    parser = build_parser(full_help=False)
    args = parser.parse_args(argv)
    if args.command in STUDIO_DISABLED_COMMANDS:
        parser.error(
            f"{args.command} is disabled in standalone Studio; use the controlled host-agent, Claude Code, or Codex CLI runtime"
        )
    for handler in (
        _handle_formal,
        _handle_project,
        _handle_agent,
        _handle_assets,
        _handle_scene,
        _handle_longform,
        _handle_legacy,
    ):
        result = handler(args, parser)
        if result is not None:
            return result
    parser.error(f"unknown command: {args.command}")
    return 2
