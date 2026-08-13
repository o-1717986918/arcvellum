"""Characterization tests for the public Embedded Engine command surface.

The parser will be split into command groups. These tests deliberately assert
the host-facing contract rather than any particular parser implementation.
"""

from __future__ import annotations

import argparse
import unittest

from literary_engineering_studio_engine.cli import FORMAL_HELP_COMMANDS, build_parser
from literary_engineering_studio_engine.command_line.commands.formal import FORMAL_HANDLERS
from literary_engineering_studio_engine.command_line.commands.scene import SCENE_HANDLERS


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise AssertionError("engine CLI parser has no subcommand action")


class EngineCliSurfaceTests(unittest.TestCase):
    def test_formal_host_commands_remain_parseable(self):
        parser = build_parser()
        choices = set(_subparser_action(parser).choices)
        self.assertTrue(FORMAL_HELP_COMMANDS <= choices, FORMAL_HELP_COMMANDS - choices)

        parser.parse_args(["formal-help"])
        parser.parse_args(["workflow-dashboard", "C:/work/project"])
        parser.parse_args(["task-next", "C:/work/project", "--route", "scene-development"])
        parser.parse_args(["task-open", "C:/work/project", "--task-id", "scene-development-scene-0001-context-packet"])
        parser.parse_args(["task-submit", "C:/work/project", "--task-id", "example", "--from", "workflow/output.json"])
        parser.parse_args(["task-complete", "C:/work/project", "--task-id", "example"])
        parser.parse_args(["route-audit", "C:/work/project", "--route", "scene-development"])

    def test_compact_help_hides_low_level_choices_but_keeps_formal_loop(self):
        parser = build_parser(full_help=False)
        compact_help = parser.format_help()
        for command in ("formal-help", "workflow-dashboard", "task-next", "task-open", "task-submit", "task-complete", "route-audit"):
            self.assertIn(command, compact_help)
        self.assertNotIn("compose-scene", compact_help)
        self.assertNotIn("agent-run", compact_help)

    def test_formal_and_scene_dispatch_tables_cover_their_owned_commands(self):
        self.assertEqual(
            set(FORMAL_HANDLERS),
            {
                "protocol",
                "agent-task-status",
                "route-audit",
                "workflow-state",
                "workflow-events",
                "workflow-dashboard",
                "workflow-validate",
                "task-next",
                "task-open",
                "task-contract-replay",
                "task-submit",
                "task-complete",
                "task-revert-submission",
                "task-contract-audit",
                "workflow-advance",
                "prompt-registry-list",
                "prompt-registry-validate",
                "prompt-preview",
            },
        )
        self.assertEqual(
            set(SCENE_HANDLERS),
            {
                "draft-scene",
                "review-scene",
                "generate-scene",
                "prepare-scene-character-assets",
                "revise-scene",
                "promote-candidate",
                "state-evolve",
                "canon-evolve",
                "canon-backlog",
                "canon-apply",
                "state-apply",
                "simulate-scene",
                "branch-simulate",
                "compose-scene",
            },
        )


if __name__ == "__main__":
    unittest.main()
