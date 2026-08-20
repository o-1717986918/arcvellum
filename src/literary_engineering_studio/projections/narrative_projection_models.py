"""Value contracts for the v2 narrative projection pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProjectionInventory:
    scenes: list[dict[str, Any]]
    characters: list[dict[str, Any]]
    branches: list[dict[str, Any]]
    reviews: list[dict[str, Any]]
    canon_patches: list[dict[str, Any]]

    @classmethod
    def from_library(cls, library: dict[str, Any]) -> "ProjectionInventory":
        sections = library.get("sections") if isinstance(library.get("sections"), dict) else {}
        return cls(
            scenes=_dict_rows(sections.get("scenes")),
            characters=_dict_rows(sections.get("characters")),
            branches=_dict_rows(sections.get("branches")),
            reviews=_dict_rows(sections.get("reviews")),
            canon_patches=_dict_rows(sections.get("canon_patches")),
        )


def _dict_rows(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


__all__ = ["ProjectionInventory"]
