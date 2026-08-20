"""Pre-migration SQLite backup policy."""

from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3

from ..application.persistence_ports import Clock
from .system_primitives import utc_now


def backup_before_migration(
    path: Path,
    *,
    schema_version: int,
    clock: Clock,
) -> Path | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    connection = sqlite3.connect(path, timeout=10)
    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    finally:
        connection.close()
    if version > schema_version:
        raise RuntimeError(
            f"Studio database schema {version} is newer than supported {schema_version}"
        )
    if version == schema_version:
        return None
    backup_root = path.parent / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = utc_now(clock).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / f"{path.stem}-schema-{version}-{stamp}{path.suffix}"
    shutil.copy2(path, backup)
    return backup


__all__ = ["backup_before_migration"]
