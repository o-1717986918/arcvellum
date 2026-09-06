"""Allowlist for Engine data shipped in wheels and desktop sidecars."""

from __future__ import annotations

from pathlib import PurePosixPath


RUNTIME_REFERENCE_FILES = frozenset(
    {
        "references/agent-run-protocol.md",
        "references/cli-run-protocol.md",
        "references/file-format-export.md",
        "references/formal-host-operating-constitution.md",
        "references/punctuation-standard.md",
    }
)
RUNTIME_DOCUMENT_FILES = frozenset({"docs/architecture/data-model.md"})
RUNTIME_DOCUMENT_PREFIXES = ("docs/modules/",)
RUNTIME_DATA_PREFIXES = ("schemas/", "templates/")


def normalize_engine_resource(value: str) -> str:
    normalized = str(value).replace("\\", "/").strip().lstrip("./")
    return PurePosixPath(normalized).as_posix() if normalized else ""


def is_installable_engine_resource(value: str) -> bool:
    """Return whether an embedded Engine data file belongs in the product."""

    relative = normalize_engine_resource(value)
    if relative in RUNTIME_REFERENCE_FILES or relative in RUNTIME_DOCUMENT_FILES:
        return True
    return relative.endswith((".md", ".yaml", ".yml", ".json")) and relative.startswith(
        (*RUNTIME_DOCUMENT_PREFIXES, *RUNTIME_DATA_PREFIXES)
    )


__all__ = [
    "RUNTIME_DATA_PREFIXES",
    "RUNTIME_DOCUMENT_FILES",
    "RUNTIME_DOCUMENT_PREFIXES",
    "RUNTIME_REFERENCE_FILES",
    "is_installable_engine_resource",
    "normalize_engine_resource",
]
