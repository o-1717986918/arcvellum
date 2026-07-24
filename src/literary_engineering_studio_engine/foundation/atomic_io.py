"""Small atomic text writer for cross-process read models."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Mapping


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline="",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, target)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def atomic_write_batch(entries: Mapping[Path, str], *, encoding: str = "utf-8") -> None:
    """Replace a small group of related text files with rollback on failure.

    A scene state apply touches more than one durable artifact.  `os.replace`
    is atomic per file, not per workflow operation, so keep the original bytes
    in memory and compensate if a later replacement fails.  The helper is
    deliberately for small metadata/YAML batches, never large prose files.
    """

    normalized = {Path(path).resolve(): text for path, text in entries.items()}
    if not normalized:
        return
    originals: dict[Path, bytes | None] = {}
    temporary: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for target, text in normalized.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            originals[target] = target.read_bytes() if target.exists() else None
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=encoding,
                newline="",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
                temporary[target] = Path(handle.name)
        for target, staged in temporary.items():
            os.replace(staged, target)
            replaced.append(target)
    except Exception:
        for target in reversed(replaced):
            original = originals.get(target)
            if original is None:
                target.unlink(missing_ok=True)
            else:
                rollback = target.with_name(f".{target.name}.rollback.tmp")
                rollback.write_bytes(original)
                os.replace(rollback, target)
        raise
    finally:
        for staged in temporary.values():
            staged.unlink(missing_ok=True)
