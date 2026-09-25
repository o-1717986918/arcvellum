"""Audited project-author style direction, distinct from reviewed style versions."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4

from literary_engineering_studio_engine.public.projects import atomic_write_batch


RELATIVE_PATH = Path("style/owner_style_directive.md")
EMPTY_REVISION = hashlib.sha256(b"").hexdigest()
_WRITE_LOCK = RLock()


def read_owner_style_directive(root: Path) -> dict[str, object]:
    project = root.resolve()
    path = project / RELATIVE_PATH
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {
        "schema": "arcvellum/owner-style-directive/v1",
        "content": content,
        "revision": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "active": bool(content.strip()),
    }


def write_owner_style_directive(
    root: Path, *, content: str, base_revision: str, reason: str,
) -> dict[str, object]:
    if not isinstance(content, str) or len(content) > 3500:
        raise ValueError("owner style directive must be text of at most 3500 characters")
    if len(reason.strip()) < 6:
        raise ValueError("owner style directive needs an explanatory reason")
    project = root.resolve()
    if not (project / "project.yaml").is_file():
        raise ValueError("owner style directive requires a work project")
    with _WRITE_LOCK:
        previous = read_owner_style_directive(project)
        if base_revision != previous["revision"]:
            raise ValueError("owner style directive changed since it was read")
        if content == previous["content"]:
            raise ValueError("owner style directive is unchanged")
        transaction_id = f"owner-style-{uuid4().hex}"
        revision = hashlib.sha256(content.encode("utf-8")).hexdigest()
        current = {
            "schema": "arcvellum/owner-style-directive/v1",
            "content": content, "revision": revision, "active": bool(content.strip()),
        }
        receipt = {
            "schema": "arcvellum/owner-style-directive-receipt/v1",
            "transaction_id": transaction_id,
            "authority": "owner", "reason": reason.strip(),
            "base_revision": base_revision, "new_revision": revision,
            "active": current["active"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        receipt_path = project / "style" / "owner_style_receipts" / f"{transaction_id}.json"
        atomic_write_batch({
            project / RELATIVE_PATH: content,
            receipt_path: json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        })
        return {"directive": current, "receipt": receipt}


__all__ = ["EMPTY_REVISION", "read_owner_style_directive", "write_owner_style_directive"]
