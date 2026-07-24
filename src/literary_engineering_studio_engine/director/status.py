"""Read-only project status projection for the creative director."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..asset_workshop import list_asset_candidates
from ..style_lab import active_project_style

def build_director_status(project_root: Path, *, limit: int = 8) -> dict[str, Any]:
    root = project_root.resolve()
    asset_items = list_asset_candidates(root) if root.is_dir() else []
    workflow_index = root / "workflow" / "runs" / "index.jsonl"
    director_index = root / "director" / "runs" / "index.jsonl"
    conversation_index = root / "director" / "conversation" / "turns.jsonl"
    direction_memory_index = root / "director" / "memory" / "project_direction.jsonl"
    return {
        "root": str(root),
        "has_project": (root / "project.yaml").exists(),
        "project_yaml": _read_text(root / "project.yaml", 3000),
        "active_style_skill": active_project_style(root) if root.is_dir() else {},
        "counts": {
            "characters": len(list((root / "characters").glob("*.yaml"))) if (root / "characters").exists() else 0,
            "scenes": len(list((root / "scenes").glob("*.yaml"))) if (root / "scenes").exists() else 0,
            "drafts": len(list((root / "drafts" / "scenes").glob("*.md"))) if (root / "drafts" / "scenes").exists() else 0,
            "candidate_assets": len(asset_items),
            "director_runs": len(_tail_jsonl(director_index, 1000)),
        },
        "candidate_assets": asset_items[-limit:],
        "recent_workflow_runs": _tail_jsonl(workflow_index, limit),
        "recent_director_runs": _tail_jsonl(director_index, limit),
        "recent_conversation": _tail_jsonl(conversation_index, limit),
        "recent_project_directions": _tail_jsonl(direction_memory_index, limit),
    }


def _compact_director_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_project": bool(status.get("has_project")),
        "counts": status.get("counts", {}),
        "candidate_assets": [
            {
                "asset_type": item.get("asset_type", ""),
                "candidate_id": item.get("candidate_id", ""),
                "status": item.get("status", ""),
                "title": item.get("title", ""),
            }
            for item in status.get("candidate_assets", [])[-3:]
            if isinstance(item, dict)
        ],
        "recent_conversation": [
            {
                "user_direction": item.get("user_direction", ""),
                "assistant_headline": item.get("assistant_headline", ""),
                "assistant_reply": item.get("assistant_reply", ""),
                "chosen_workflow": item.get("chosen_workflow", ""),
                "status": item.get("status", ""),
            }
            for item in status.get("recent_conversation", [])[-3:]
            if isinstance(item, dict)
        ],
        "recent_project_directions": [
            {
                "summary": item.get("summary", ""),
                "preferences": item.get("preferences", []),
                "constraints": item.get("constraints", []),
                "created_at": item.get("created_at", ""),
            }
            for item in status.get("recent_project_directions", [])[-5:]
            if isinstance(item, dict)
        ],
    }



def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _read_text(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")[:limit]
