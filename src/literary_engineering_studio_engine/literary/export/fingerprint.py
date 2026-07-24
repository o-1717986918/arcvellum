"""Stable release-candidate fingerprints for content-bound approvals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def release_candidate_fingerprint(project_root: Path, chapter_id: str) -> str:
    """Hash release semantics and delivery text, excluding volatile timestamps/DOCX metadata."""

    root = project_root.resolve()
    manifest = root / "exports" / chapter_id / "export_manifest.json"
    if not manifest.is_file():
        return ""
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    content_hashes: dict[str, str] = {}
    for key in ("novel", "screenplay", "video_prompt_pack"):
        relative = str(outputs.get(key) or "").replace("\\", "/")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            return ""
        path = root / relative
        if not path.is_file():
            return ""
        content_hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    stable = {
        "schema": payload.get("schema"),
        "chapter_id": payload.get("chapter_id") or chapter_id,
        "include_blocked": payload.get("include_blocked") is True,
        "exported_scenes": payload.get("exported_scenes", []),
        "skipped_scenes": payload.get("skipped_scenes", []),
        "content_hashes": content_hashes,
    }
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
