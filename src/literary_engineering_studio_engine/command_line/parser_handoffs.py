"""Parser registration for scene handoff and planning-review commands."""

from __future__ import annotations

import argparse


def register_handoff_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    handoff = subparsers.add_parser(
        "scene-handoff",
        help="Materialize a promoted scene continuity handoff for the next formal scene.",
    )
    handoff.add_argument("project", help="Work project directory.")
    handoff.add_argument(
        "--scene",
        default="scenes/scene_0001.yaml",
        help="Promoted scene whose post-scene handoff is recorded.",
    )

    review = subparsers.add_parser(
        "prepare-longform-review",
        help="Prepare an independent digest-bound review for one longform planning candidate.",
    )
    review.add_argument("project", help="Work project directory.")
    review.add_argument(
        "--kind",
        required=True,
        choices=("budget", "scene_inventory", "chapter_obligation"),
        help="Planning candidate kind to review.",
    )


__all__ = ["register_handoff_commands"]
