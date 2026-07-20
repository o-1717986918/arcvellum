"""Pinned OpenCode binary discovery, download, and verification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
from typing import Any
from urllib.request import Request, urlopen
import zipfile

from .config import default_data_root, repository_root


def bundle_manifest() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "vendor" / "opencode-manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("targets"), dict):
        raise ValueError(f"invalid OpenCode bundle manifest: {path}")
    return payload


def current_target() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return "windows-x64-baseline"
    raise RuntimeError(f"no pinned OpenCode bundle for {system}/{machine}")


def locate_opencode(settings: dict[str, object] | None = None) -> Path | None:
    values = settings or {}
    explicit = str(values.get("executable") or os.environ.get("LES_OPENCODE_EXECUTABLE") or "").strip()
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        resolved = shutil.which(explicit)
        if resolved:
            return Path(resolved).resolve()

    manifest = bundle_manifest()
    try:
        target_id = current_target()
    except RuntimeError:
        return None
    target = manifest["targets"][target_id]
    version = str(manifest["version"])
    executable_name = str(target["executable"])
    candidates = [
        default_data_root() / "vendor" / "opencode" / version / executable_name,
        repository_root() / "build" / "vendor" / f"opencode-v{version}" / "expanded" / executable_name,
    ]
    frozen_root = getattr(__import__("sys"), "_MEIPASS", "")
    if frozen_root:
        candidates.insert(0, Path(frozen_root) / "vendor" / "opencode" / executable_name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    resolved = shutil.which("opencode")
    return Path(resolved).resolve() if resolved else None


def install_pinned_opencode(destination_root: Path | None = None) -> dict[str, Any]:
    manifest = bundle_manifest()
    target_id = current_target()
    target = manifest["targets"][target_id]
    version = str(manifest["version"])
    root = (destination_root or (default_data_root() / "vendor" / "opencode" / version)).expanduser().resolve()
    executable = root / str(target["executable"])
    if executable.is_file():
        return _installation_result(executable, manifest, target_id, "already-installed")

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="les-opencode-download-") as temporary:
        archive = Path(temporary) / str(target["archive"])
        request = Request(str(target["url"]), headers={"User-Agent": "Literary-Engineering-Studio"})
        with urlopen(request, timeout=120) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        actual = _sha256(archive)
        expected = str(target["sha256"]).lower()
        if actual != expected:
            raise ValueError(f"OpenCode checksum mismatch: expected {expected}, got {actual}")
        with zipfile.ZipFile(archive) as bundle:
            _safe_extract(bundle, root)
    if not executable.is_file():
        raise FileNotFoundError(f"OpenCode archive did not contain {executable.name}")
    notice_source = Path(__file__).resolve().parent / "vendor" / "OPENCODE-NOTICE.md"
    shutil.copy2(notice_source, root / "OPENCODE-NOTICE.md")
    return _installation_result(executable, manifest, target_id, "installed")


def verify_opencode(path: Path) -> dict[str, Any]:
    executable = path.expanduser().resolve()
    if not executable.is_file():
        return {"verified": False, "executable": str(executable), "detail": "executable not found"}
    manifest = bundle_manifest()
    target = manifest["targets"].get(current_target(), {})
    archive_checksum = str(target.get("sha256") or "")
    return {
        "verified": True,
        "executable": str(executable),
        "pinned_version": str(manifest["version"]),
        "target": current_target(),
        "archive_sha256": archive_checksum,
        "binary_sha256": _sha256(executable),
    }


def _installation_result(executable: Path, manifest: dict[str, Any], target: str, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "version": str(manifest["version"]),
        "target": target,
        "executable": str(executable.resolve()),
        "binary_sha256": _sha256(executable),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(bundle: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in bundle.infolist():
        target = (root / member.filename).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"unsafe path in OpenCode archive: {member.filename}")
    bundle.extractall(root)
