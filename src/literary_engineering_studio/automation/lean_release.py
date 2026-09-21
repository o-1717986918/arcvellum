"""Whole-book release for projects with sealed lean scene transactions."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from literary_engineering_studio_engine.public.projects import atomic_write_text
from literary_engineering_studio_engine.public.projections import final_body_from_workbench_text

from ..application.lean_book_audit import audit_lean_book
from ..projections.whole_book_release import _write_release


class LeanWholeBookReleaseCoordinator:
    def __init__(self, config: dict[str, Any]):
        application = config.get("application")
        application = application if isinstance(application, dict) else {}
        self.data_root = Path(str(application.get("data_root") or ".")).expanduser().resolve()

    def release(self, project_root: Path, *, approved_by: str, autopilot_run_id: str = "") -> dict[str, Any]:
        root = project_root.expanduser().resolve()
        audit = audit_lean_book(root, self.data_root)
        plan = json.loads((root / "plot" / "lean_project_plan.json").read_text(encoding="utf-8"))
        chapter_titles = {str(item["chapter_id"]): str(item["title"]) for item in plan["chapters"]}
        sources: list[Path] = []
        for index, (chapter_id, scene_paths) in enumerate(audit["chapters"], start=1):
            sections = [final_body_from_workbench_text(path.read_text(encoding="utf-8")).strip()
                        for path in scene_paths]
            if not all(sections):
                raise ValueError(f"chapter contains an empty committed scene: {chapter_id}")
            chapter_path = root / "exports" / chapter_id / f"{chapter_id}_novel.md"
            heading = f"第{index}章 {_chapter_title(chapter_titles[chapter_id])}"
            atomic_write_text(chapter_path, f"# {heading}\n\n" + "\n\n".join(sections) + "\n")
            sources.append(chapter_path)
        public_audit = {key: value for key, value in audit.items() if key != "chapters"}
        atomic_write_text(
            root / "workflow" / "book_actuals.json",
            json.dumps(audit["length_projection"], ensure_ascii=False, indent=2) + "\n",
        )
        return _write_release(
            root, sources,
            {route: public_audit for route in
             ("longform-planning", "scene-development", "review-and-audit", "export-and-release")},
            approved_by=approved_by, autopilot_run_id=autopilot_run_id,
        )


_CHAPTER_PREFIX = re.compile(
    r"^\s*(?:第[〇零一二三四五六七八九十百千万两\d]+章|chapter\s*\d+)\s*[：:、.．-]*\s*",
    re.IGNORECASE,
)


def _chapter_title(value: str) -> str:
    """Keep the plan's literary title while the exporter owns numbering."""

    title = str(value or "").strip()
    normalized = _CHAPTER_PREFIX.sub("", title).strip()
    return normalized or title or "未命名"
