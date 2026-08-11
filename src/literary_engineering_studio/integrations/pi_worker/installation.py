"""Locate the embedded or development ArcVellum Pi Worker installation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from typing import Mapping


_GENERIC_NODE_NAMES = frozenset({"", "node", "node.exe"})


@dataclass(frozen=True)
class PiWorkerInstallation:
    executable: str
    entrypoint: Path | None
    source: str

    @property
    def available(self) -> bool:
        return bool(self.executable and self.entrypoint and self.entrypoint.is_file())


def locate_pi_worker(settings: Mapping[str, object]) -> PiWorkerInstallation:
    """Resolve one portable Worker installation without persisting machine paths.

    A non-generic user executable remains authoritative. Desktop resource
    environment variables override the portable defaults. Source checkouts use
    the locally compiled Worker as the final fallback.
    """

    configured_executable = str(settings.get("executable") or "").strip()
    embedded_executable = os.environ.get("LES_PI_WORKER_EXECUTABLE", "").strip()
    executable_value = _preferred_executable(configured_executable, embedded_executable)
    executable = _resolve_executable(executable_value)

    configured_entrypoint = str(settings.get("entrypoint") or "").strip()
    embedded_entrypoint = os.environ.get("LES_PI_WORKER_ENTRYPOINT", "").strip()
    candidates = (
        (configured_entrypoint, "configured"),
        (embedded_entrypoint, "embedded"),
        (str(_development_entrypoint() or ""), "source-checkout"),
    )
    for value, source in candidates:
        if not value:
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.is_file():
            return PiWorkerInstallation(executable, candidate, source)
    return PiWorkerInstallation(executable, None, "missing")


def _preferred_executable(configured: str, embedded: str) -> str:
    if configured.lower() not in _GENERIC_NODE_NAMES:
        return configured
    if embedded:
        return embedded
    return configured or "node"


def _development_entrypoint() -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "workers" / "pi-worker" / "dist" / "main.js"
        if candidate.is_file():
            return candidate
    return None


def _resolve_executable(value: str) -> str:
    if not value:
        return ""
    direct = Path(value).expanduser()
    if direct.is_file():
        return str(direct.resolve())
    found = shutil.which(value)
    if found:
        return str(Path(found).resolve())
    if os.name == "nt" and Path(value).suffix == "":
        command = shutil.which(value + ".cmd")
        if command:
            return str(Path(command).resolve())
    return ""
