"""Compose deterministic output canonicalizers at the Studio boundary."""

from __future__ import annotations

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .canonicalization import (
    _read_object,
    _write_machine_fields,
    canonicalize_task_outputs as canonicalize_core_outputs,
)
from .chapter_obligation import canonicalize_chapter_obligation_metadata


def canonicalize_task_outputs(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    """Run core normalization followed by Studio-owned literary adapters."""

    changes = canonicalize_core_outputs(task, sandbox)
    changes.extend(
        canonicalize_chapter_obligation_metadata(
            task,
            sandbox,
            read_object=_read_object,
            write_machine_fields=_write_machine_fields,
        )
    )
    return changes


__all__ = ["canonicalize_task_outputs"]
