"""Markdown and JSON rendering for workflow protocols."""

from __future__ import annotations

import json
from typing import Iterable

from .protocol_model import ProtocolRoute


def render_protocol(route: ProtocolRoute) -> str:
    sections = [
        f"# {route.title} Protocol",
        "",
        f"route: `{route.key}`",
        "",
        route.purpose,
        "",
        _render_list("Read First", route.read),
        _render_list("Preflight", route.preflight),
        _render_list("Suggested CLI Chain", route.cli_chain),
        _render_list("Platform Agent Handoffs", route.platform_agent_handoffs),
        _render_list("Completion Gates", route.completion_gates),
        _render_list("Forbidden Shortcuts", route.forbidden_shortcuts),
    ]
    return "\n".join(sections).rstrip() + "\n"


def render_protocol_list(routes: Iterable[ProtocolRoute]) -> str:
    lines = ["# Available Protocol Routes", ""]
    for route in routes:
        lines.append(f"- `{route.key}`: {route.purpose}")
    return "\n".join(lines) + "\n"


def protocol_to_json(
    route: ProtocolRoute | None,
    routes: Iterable[ProtocolRoute],
) -> str:
    payload: object = route.to_dict() if route is not None else [
        item.to_dict() for item in routes
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _render_list(title: str, items: tuple[str, ...]) -> str:
    lines = [f"## {title}", ""]
    lines.extend(f"- {item}" for item in items)
    lines.append("")
    return "\n".join(lines)


__all__ = ["protocol_to_json", "render_protocol", "render_protocol_list"]
