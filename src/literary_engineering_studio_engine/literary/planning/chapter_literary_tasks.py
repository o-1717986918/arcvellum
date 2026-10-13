"""Chapter literary task assets included in the planning atomic write batch."""
import json
from pathlib import Path
import re


def chapter_tasks_present(root: Path, obligations: dict) -> bool:
    return all((root / "plot" / "chapter_obligations" / f"{key}.json").is_file() for key in obligations)


def chapter_task_writes(root: Path, obligations: dict) -> dict[Path, str]:
    writes = {}
    for chapter_id, obligation in obligations.items():
        if not re.fullmatch(r"chapter_\d+", chapter_id):
            raise ValueError("invalid chapter obligation identity")
        relative = f"plot/chapter_obligations/{chapter_id}.json"
        path = root / relative
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict) or existing.get("generated_by") != "lean-window":
                continue
        payload = {"schema": "arcvellum/chapter-literary-task/v1", "generated_by": "lean-window",
                   "chapter_id": chapter_id, "obligation_ids": [relative], **obligation}
        writes[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return writes
