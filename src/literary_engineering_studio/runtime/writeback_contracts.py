"""Immutable contracts shared by sandbox inspection and mutation tracking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WritebackPreview:
    policy: str
    preview_path: Path
    changes: tuple[dict[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "literary-engineering-studio/writeback-preview/v0.1",
            "policy": self.policy,
            "preview_path": str(self.preview_path),
            "change_count": len(self.changes),
            "changes": list(self.changes),
        }
