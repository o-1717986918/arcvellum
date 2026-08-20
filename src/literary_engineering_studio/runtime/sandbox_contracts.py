"""Stable value contracts shared by Sandbox staging and writeback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxManifest:
    run_id: str
    run_root: Path
    # ``workspace`` is always the Agent-visible workspace. The control
    # workspace is reserved for deterministic CLI commands and preflight.
    workspace: Path
    prompt_path: Path
    manifest_path: Path
    baseline_path: Path
    expected_outputs: tuple[str, ...]
    control_workspace: Path | None = None
    agent_workspace: Path | None = None


__all__ = ["SandboxManifest"]
