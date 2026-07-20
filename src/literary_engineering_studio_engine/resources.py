"""Packaged resource locations for the embedded literary engineering engine."""

from __future__ import annotations

from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent / "_engine"


def engine_root() -> Path:
    """Return the resource root shipped inside the Studio installation."""

    if not ENGINE_ROOT.is_dir():
        raise FileNotFoundError(f"embedded literary engine resources are missing: {ENGINE_ROOT}")
    return ENGINE_ROOT


def engine_path(*parts: str) -> Path:
    path = engine_root().joinpath(*parts)
    if not path.exists():
        raise FileNotFoundError(f"embedded literary engine resource is missing: {path}")
    return path
