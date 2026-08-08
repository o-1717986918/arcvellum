"""State-machine-first formal host command dispatch."""

from __future__ import annotations

import sys

from ...cli_parser import build_parser
from ...cli_support import render_formal_help
from ...formal_mode import bypass_hits, formal_bypass_message
from .formal_prompts import HANDLERS as PROMPT_HANDLERS
from .formal_tasks import HANDLERS as TASK_HANDLERS
from .formal_workflow import HANDLERS as WORKFLOW_HANDLERS


FORMAL_HANDLERS = {
    **WORKFLOW_HANDLERS,
    **TASK_HANDLERS,
    **PROMPT_HANDLERS,
}


def handle(args, parser) -> int | None:
    if args.command == "formal-help":
        print(render_formal_help(args.project, args.route), end="")
        return 0
    if args.command == "help-all":
        print(build_parser(full_help=True).format_help(), end="")
        return 0

    hits = bypass_hits(vars(args))
    if hits:
        print(
            formal_bypass_message(hits, surface=f"lew {args.command}"),
            file=sys.stderr,
        )
        return 2

    command_handler = FORMAL_HANDLERS.get(args.command)
    return command_handler(args, parser) if command_handler else None
