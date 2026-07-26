"""Bounded textual asset comparison."""

from __future__ import annotations

import difflib
from typing import Any

from ..context import CapabilityContext
from ..contracts import HandlerOutput
from .text import _read_bounded


def asset_diff(context: CapabilityContext, arguments: dict[str, Any]) -> HandlerOutput:
    before_rel = str(arguments.get("before_path") or "")
    after_rel = str(arguments.get("after_path") or "")
    before_scope = str(arguments.get("before_scope") or "project")
    after_scope = str(arguments.get("after_scope") or "workspace")
    before_path = context.resolve_path(before_rel, scope=before_scope)
    after_path = context.resolve_path(after_rel, scope=after_scope)
    if not before_path.is_file() or not after_path.is_file():
        raise FileNotFoundError("asset.diff requires two existing text files")
    before = _read_bounded(before_path).splitlines()
    after = _read_bounded(after_path).splitlines()
    lines = list(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"before/{before_rel}",
            tofile=f"after/{after_rel}",
            lineterm="",
            n=3,
        )
    )
    changed = sum(line.startswith(("+", "-")) and not line.startswith(("+++", "---")) for line in lines)
    return HandlerOutput(
        f"asset diff completed with {changed} changed lines",
        {
            "before_path": before_rel,
            "after_path": after_rel,
            "changed_lines": changed,
            "diff": "\n".join(lines),
        },
    )
