"""Application-owned OpenCode profiles for formal work and read-only advice."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any


class OpenCodeRole(str, Enum):
    WORKER = "worker"
    ADVISOR = "advisor"
    STEWARD = "steward"
    PLANNER = "planner"
    REVIEWER = "reviewer"


ROLE_AGENT_IDS: dict[OpenCodeRole, str] = {
    OpenCodeRole.WORKER: "literary-worker",
    OpenCodeRole.ADVISOR: "project-advisor",
    OpenCodeRole.STEWARD: "creative-steward",
    OpenCodeRole.PLANNER: "orchestration-planner",
    OpenCodeRole.REVIEWER: "orchestration-reviewer",
}


def worker_profile(model: str) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "description": "Executes one Studio task package inside an isolated task sandbox.",
        "mode": "primary",
        "prompt": (
            "Follow AGENT_TASK.md as the complete execution program. Read only staged sources, then use the edit tool "
            "to finish every Agent-authored declared output before replying. A pending JSON scaffold is not a completed "
            "output. Write only declared expected outputs. Never use shell, web, skills, subagents, or external directories."
        ),
        "permission": {
            "*": "deny",
            "read": {
                "*": "allow",
                "*.agent_tasks.md": "deny",
            },
            "glob": "deny",
            "grep": "deny",
            "list": "allow",
            "edit": "allow",
            "write": "allow",
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


def steward_profile(model: str) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "description": "Selects among bounded literary decisions from a read-only project snapshot.",
        "mode": "primary",
        "prompt": (
            "Act as the delegated Creative Steward. The decision prompt contains the complete bounded evidence packet. "
            "Compare only the declared options and return one auditable JSON decision immediately. Never inspect files, "
            "execute tools, invent new options, or impersonate the user."
        ),
        "permission": {
            "*": "deny",
            "read": "deny",
            "glob": "deny",
            "grep": "deny",
            "list": "deny",
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
            "doom_loop": "deny",
        },
    }
    if model:
        agent["model"] = model
    return _base_profile("creative-steward", agent, model)


def planner_profile(model: str) -> dict[str, Any]:
    return _orchestration_profile(
        OpenCodeRole.PLANNER,
        model,
        description="Proposes one bounded creative execution plan from a machine-curated planning snapshot.",
        prompt=(
            "Treat the supplied planning snapshot as the complete readable context. Return exactly one JSON object "
            "matching the declared CreativeExecutionPlanCandidate schema. You may interpret literary strategy, but "
            "you may not invent commands, paths, machine fields, completed facts, or formal project writes."
        ),
    )


def reviewer_profile(model: str) -> dict[str, Any]:
    return _orchestration_profile(
        OpenCodeRole.REVIEWER,
        model,
        description="Critically reviews one exact creative plan and its deterministic evidence.",
        prompt=(
            "Review only the exact candidate, normalized plan, lint, graph, simulation, and planning ledger supplied "
            "in this independent session. Return exactly one JSON judgment object. Do not edit the candidate, activate "
            "a plan, inspect external files, or accept missing literary obligations merely to speed execution."
        ),
    )


def write_profile(
    directory: Path,
    *,
    role: OpenCodeRole | str,
    model: str,
    provider_overrides: dict[str, dict[str, Any]] | None = None,
) -> Path:
    root = directory.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    normalized = OpenCodeRole(role)
    if normalized is OpenCodeRole.ADVISOR:
        payload = advisor_profile(model)
    elif normalized is OpenCodeRole.STEWARD:
        payload = steward_profile(model)
    elif normalized is OpenCodeRole.PLANNER:
        payload = planner_profile(model)
    elif normalized is OpenCodeRole.REVIEWER:
        payload = reviewer_profile(model)
    else:
        payload = worker_profile(model)
    if provider_overrides:
        payload["provider"] = provider_overrides
    path = root / "opencode.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def agent_id_for_role(role: OpenCodeRole | str) -> str:
    return ROLE_AGENT_IDS[OpenCodeRole(role)]


def _orchestration_profile(
    role: OpenCodeRole,
    model: str,
    *,
    description: str,
    prompt: str,
) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "description": description,
        "mode": "primary",
        "prompt": prompt,
        "permission": {
            "*": "deny",
            "read": "allow",
            "glob": "allow",
            "grep": "allow",
            "list": "allow",
            "edit": "deny",
            "write": "deny",
            "bash": "deny",
            "task": "deny",
            "external_directory": "deny",
            "todowrite": "deny",
            "webfetch": "deny",
            "websearch": "deny",
            "lsp": "deny",
            "skill": "deny",
            "question": "deny",
            "doom_loop": "deny",
        },
    }
    if model:
        agent["model"] = model
    return _base_profile(ROLE_AGENT_IDS[role], agent, model)


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
