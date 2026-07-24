"""Prompt asset loading and bounded director prompt construction."""

from __future__ import annotations

import json
from typing import Any

from ..resources import engine_path


def _director_user_prompt(direction: str, project_status: dict[str, Any]) -> str:
    template = _template("director_user.md")
    return template.replace("{{USER_DIRECTION}}", direction).replace(
        "{{PROJECT_STATUS}}", json.dumps(project_status, ensure_ascii=False, indent=2)[:12000]
    )


def _template(name: str) -> str:
    path = engine_path("templates", "prompts", name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "You are a top-level literary engineering director. Output JSON only."
