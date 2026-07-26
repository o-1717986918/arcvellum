"""Prepare and project per-run capability and resource control contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from .capabilities.policy import build_capability_manifest
from .resources import derive_resource_claim


@dataclass(frozen=True)
class ExecutionBoundaries:
    capability_manifest_path: Path
    resource_claim_path: Path
    capability_manifest: dict[str, Any]
    resource_claim: dict[str, Any]

    def run_manifest_fields(self) -> dict[str, object]:
        capability = self.capability_manifest
        claim = self.resource_claim
        return {
            "capability_manifest": {
                "schema": capability["schema"],
                "policy_revision": capability["policy_revision"],
                "digest": capability["digest"],
                "allowed_capability_ids": capability["allowed_capability_ids"],
                "path": "capabilities/manifest.json",
            },
            "resource_claim": {
                "schema": claim["schema"],
                "task_node_id": claim["task_node_id"],
                "project_id": claim["project_id"],
                "path": "capabilities/resource-claim.json",
            },
        }


def prepare_execution_boundaries(task: TaskPackage, run_root: Path, *, runtime: str) -> ExecutionBoundaries:
    capability = build_capability_manifest(task).as_dict()
    claim = derive_resource_claim(task, runtime_slot=runtime).as_dict()
    capability_path, claim_path = execution_boundary_paths(run_root)
    capability_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(capability_path, capability)
    _write_json(claim_path, claim)
    return ExecutionBoundaries(capability_path, claim_path, capability, claim)


def materialize_execution_boundaries(
    run_root: Path,
    task_dir: Path,
    *,
    task_context_path: Path | None = None,
) -> ExecutionBoundaries:
    capability_path, claim_path = execution_boundary_paths(run_root)
    capability = _read_json(capability_path)
    claim = _read_json(claim_path)
    _write_json(task_dir / "capability_manifest.json", capability)
    _write_json(task_dir / "resource_claim.json", claim)
    if task_context_path is not None:
        context = _read_json(task_context_path)
        context["controlled_capabilities"] = capability
        context["resource_claim"] = claim
        _write_json(task_context_path, context)
    return ExecutionBoundaries(capability_path, claim_path, capability, claim)


def execution_boundary_paths(run_root: Path) -> tuple[Path, Path]:
    boundary_root = run_root.resolve() / "capabilities"
    return boundary_root / "manifest.json", boundary_root / "resource-claim.json"


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"invalid execution boundary: {path}")
    return parsed


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
