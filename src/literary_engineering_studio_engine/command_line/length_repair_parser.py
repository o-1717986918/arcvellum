"""Parser registration for whole-work target-length repair."""

from __future__ import annotations


def add_length_repair_parser(sub) -> None:
    parser = sub.add_parser(
        "plan-length-repair",
        help="Allocate a whole-work Chinese-content shortfall to bounded scene revisions.",
    )
    parser.add_argument("project", help="Work project directory.")
    parser.add_argument("--out", default="", help="Output repair JSON path.")
    parser.add_argument("--md-out", default="", help="Output repair Markdown path.")


__all__ = ["add_length_repair_parser"]
