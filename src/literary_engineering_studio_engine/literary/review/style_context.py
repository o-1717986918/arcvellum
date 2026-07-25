"""Mounted-style context for independent scene review."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ..style.snapshot import (
    active_style_evidence_paths,
    active_style_mount_snapshot_payload,
    active_style_prompt_path,
)


@dataclass(frozen=True)
class SceneReviewStyleContext:
    prompt_path: Path | None
    snapshot: dict[str, str]
    evidence_paths: tuple[Path, ...]


def scene_review_style_context(root: Path) -> SceneReviewStyleContext:
    prompt = active_style_prompt_path(root) or _first_existing(
        [
            root / "style" / "style_prompt.md",
            root / "style" / "demo-author" / "style_prompt.md",
            root / "style" / "style-profile.md",
        ]
    )
    evidence = active_style_evidence_paths(root)
    if prompt and prompt.is_file():
        evidence.append(prompt)
    return SceneReviewStyleContext(
        prompt_path=prompt,
        snapshot=active_style_mount_snapshot_payload(root),
        evidence_paths=tuple(dict.fromkeys(evidence)),
    )


def render_review_style_snapshot(snapshot: dict[str, str]) -> str:
    return f"""## Immutable Style Mount Snapshot

```json
{json.dumps(snapshot, ensure_ascii=False, indent=2)}
```

若快照非空，本次审查只能依据该 exact style version。不得改读其他
style prompt、旧版本或散装 profile；输出中的 `style_mount_snapshot`
由系统绑定，不得自行改写。"""


def _first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


__all__ = [
    "SceneReviewStyleContext",
    "render_review_style_snapshot",
    "scene_review_style_context",
]
