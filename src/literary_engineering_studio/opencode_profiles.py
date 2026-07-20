"""Application-owned OpenCode profiles for formal work and read-only advice."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def worker_profile(model: str) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "description": "Executes one Studio task package inside an isolated task sandbox.",
        "mode": "primary",
        "prompt": (
            "Follow AGENT_TASK.md as the complete execution program. Read only staged sources. "
            "Write only declared expected outputs. Never use shell, web, skills, subagents, or external directories."
        ),
        "permission": {
            "*": "deny",
            "read": "allow",
            "glob": "allow",
            "grep": "allow",
            "list": "allow",
            "edit": "allow",
            "bash": "deny",
            "task": "deny",
            "external_directory": "deny",
            "todowrite": "deny",
            "webfetch": "deny",
            "websearch": "deny",
            "lsp": "deny",
            "skill": "deny",
            "question": "deny",
            "doom_loop": "deny"
        },
    }
    if model:
        agent["model"] = model
    return _base_profile("literary-worker", agent, model)


def advisor_profile(model: str) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "description": "Answers questions from a read-only literary project snapshot with citations.",
        "mode": "primary",
        "prompt": (
            "Answer only from the supplied read-only project snapshot. Cite project-relative source paths for factual "
            "claims. Distinguish evidence, inference, and unknowns. Do not propose or perform edits."
        ),
        "permission": {
            "*": "deny",
            "read": "allow",
            "glob": "allow",
            "grep": "allow",
            "list": "allow",
            "edit": "deny",
            "bash": "deny",
            "task": "deny",
            "external_directory": "deny",
            "todowrite": "deny",
            "webfetch": "deny",
            "websearch": "deny",
            "lsp": "deny",
            "skill": "deny",
            "question": "deny",
            "doom_loop": "deny"
        },
    }
    if model:
        agent["model"] = model
    return _base_profile("project-advisor", agent, model)


def write_profile(directory: Path, *, role: str, model: str) -> Path:
    root = directory.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    payload = advisor_profile(model) if role == "advisor" else worker_profile(model)
    path = root / "opencode.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _base_profile(agent_id: str, agent: dict[str, Any], model: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "$schema": "https://opencode.ai/config.json",
        "autoupdate": False,
        "share": "disabled",
        "snapshot": False,
        "plugin": [],
        "mcp": {},
        "lsp": False,
        "formatter": False,
        "subagent_depth": 0,
        "default_agent": agent_id,
        "agent": {agent_id: agent},
        "permission": {"*": "deny"},
    }
    if model:
        payload["model"] = model
    return payload
