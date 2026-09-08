"""Evidence-gated literary-kernel selection and project-origin marking."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path(__file__).with_name("lean-kernel-v2.json")
PROJECT_ORIGIN_PATH = Path(".arcvellum") / "studio-project.json"
MANIFEST_SCHEMA = "arcvellum/literary-kernel-compatibility/v1"
PROJECT_ORIGIN_SCHEMA = "arcvellum/studio-project-origin/v1"


@dataclass(frozen=True)
class KernelSelection:
    kernel: str
    scene_execution_mode: str
    source: str
    reason: str
    ready_for_default: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def kernel_compatibility_manifest() -> dict[str, Any]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("literary-kernel compatibility manifest has an unsupported schema")
    kernels = payload.get("kernels")
    if not isinstance(kernels, dict) or not {"strict-v1", "lean-v2"}.issubset(kernels):
        raise ValueError("literary-kernel compatibility manifest is missing a supported kernel")
    adoption = payload.get("adoption")
    if not isinstance(adoption, dict) or not isinstance(adoption.get("ready_for_default"), bool):
        raise ValueError("literary-kernel compatibility manifest has no adoption decision")
    return payload


def initial_kernel_selection(project_root: Path | str) -> KernelSelection:
    """Select an initial policy without changing an explicitly persisted policy."""

    root = Path(project_root).expanduser().resolve()
    manifest = kernel_compatibility_manifest()
    adoption = manifest["adoption"]
    studio_created = _is_studio_created(root)
    ready = bool(adoption["ready_for_default"])
    if not studio_created:
        return KernelSelection(
            kernel=str(manifest["fallback"]),
            scene_execution_mode=str(manifest["new_project_mode"]),
            source="legacy-project-fallback",
            reason="project has no Studio creation marker; preserve strict-v1 behavior",
            ready_for_default=ready,
        )
    if ready:
        return KernelSelection(
            kernel=str(manifest["candidate"]),
            scene_execution_mode=str(manifest["new_project_mode"]),
            source="new-project-recommendation",
            reason="blind literary evidence permits the lean-v2 default",
            ready_for_default=True,
        )
    return KernelSelection(
        kernel=str(manifest["fallback"]),
        scene_execution_mode=str(manifest["new_project_mode"]),
        source="new-project-evidence-fallback",
        reason=str(adoption.get("decision") or "literary evidence is pending"),
        ready_for_default=False,
    )


def mark_studio_created_project(project_root: Path | str) -> Path:
    root = Path(project_root).expanduser().resolve()
    path = root / PROJECT_ORIGIN_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": PROJECT_ORIGIN_SCHEMA,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "kernel_selection": "compatibility-manifest",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _is_studio_created(project_root: Path) -> bool:
    path = project_root / PROJECT_ORIGIN_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    return payload.get("schema") == PROJECT_ORIGIN_SCHEMA


__all__ = [
    "KernelSelection",
    "initial_kernel_selection",
    "kernel_compatibility_manifest",
    "mark_studio_created_project",
]
