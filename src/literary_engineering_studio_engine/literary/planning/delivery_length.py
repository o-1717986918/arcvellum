"""Formal whole-work delivery length status."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import load_word_budget_summary


@dataclass(frozen=True)
class DeliveryLengthStatus:
    target_chinese_chars: int
    actual_chinese_chars: int
    shortfall_chinese_chars: int
    completion_ratio: float
    inventory_complete: bool
    target_source: str
    chapter_rows: tuple[dict[str, Any], ...]

    @property
    def met(self) -> bool:
        return self.target_chinese_chars <= 0 or self.shortfall_chinese_chars == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_chinese_chars": self.target_chinese_chars,
            "actual_chinese_chars": self.actual_chinese_chars,
            "shortfall_chinese_chars": self.shortfall_chinese_chars,
            "completion_ratio": self.completion_ratio,
            "inventory_complete": self.inventory_complete,
            "target_source": self.target_source,
            "status": "pass" if self.met else "shortfall",
            "chapter_rows": [dict(row) for row in self.chapter_rows],
        }


def delivery_length_status(project_root: Path) -> DeliveryLengthStatus:
    root = project_root.resolve()
    budget = load_word_budget_summary(root, live=True)
    target = budget.get("target") if isinstance(budget.get("target"), dict) else {}
    totals = budget.get("totals") if isinstance(budget.get("totals"), dict) else {}
    binding = (
        budget.get("scene_inventory_binding")
        if isinstance(budget.get("scene_inventory_binding"), dict)
        else {}
    )
    target_chars = _to_int(
        target.get("target_chinese_chars")
        or totals.get("target_chinese_chars")
        or target.get("target_words")
        or totals.get("target_words")
    )
    actual_chars = _to_int(
        binding.get("actual_draft_chinese_chars")
        or binding.get("actual_draft_chars")
    )
    planned_scenes = _to_int(totals.get("scene_count"))
    actual_scenes = _to_int(binding.get("actual_scene_count"))
    missing_scenes = _to_int(binding.get("missing_scene_count"))
    rows = binding.get("chapter_rows") if isinstance(binding.get("chapter_rows"), list) else []
    chapter_rows = tuple(dict(row) for row in rows if isinstance(row, dict))
    inventory_complete = bool(
        planned_scenes > 0
        and actual_scenes >= planned_scenes
        and missing_scenes == 0
    )
    shortfall = max(target_chars - actual_chars, 0)
    ratio = round(actual_chars / target_chars, 6) if target_chars else 1.0
    return DeliveryLengthStatus(
        target_chinese_chars=target_chars,
        actual_chinese_chars=actual_chars,
        shortfall_chinese_chars=shortfall,
        completion_ratio=ratio,
        inventory_complete=inventory_complete,
        target_source="plot/word_budget/word_budget.json" if target_chars else "",
        chapter_rows=chapter_rows,
    )


def _to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = ["DeliveryLengthStatus", "delivery_length_status"]
