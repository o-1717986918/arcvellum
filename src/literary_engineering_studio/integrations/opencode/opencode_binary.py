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

from ...application.config import default_data_root, repository_root


INSTALLATION_RECEIPT = "opencode-installation.json"


def _bundled_vendor_dir() -> Path:
    """Return Studio-owned pinned OpenCode resources, independent of module layout."""

    return Path(__file__).resolve().parents[2] / "vendor"


def bundle_manifest() -> dict[str, Any]:
    path = _bundled_vendor_dir() / "opencode-manifest.json"
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
        verification = verify_opencode(executable)
        if verification.get("verification_state") == "receipt-mismatch":
            raise ValueError(
                "existing pinned OpenCode binary does not match its installation receipt; "
                "remove the vendor directory and reinstall it"
            )
        if verification.get("verification_state") == "receipt-verified":
            return _installation_result(executable, manifest, target_id, "already-installed")
        # A repository build cache can contain a previously expanded binary
        # without the receipt required by the desktop packager. Do not bless
        # that binary merely because it exists: fetch the pinned archive again,
        # verify its archive checksum, then overwrite it and write a receipt.
        # This also replaces the source-build placeholder receipt with a real
        # one. A mismatched real receipt remains a hard failure above.

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="les-opencode-download-") as temporary:
        archive = Path(temporary) / str(target["archive"])
        expected = str(target["sha256"]).lower()
        cached_archive = _verified_cached_archive(root, manifest, target_id)
        if cached_archive is not None:
            shutil.copyfile(cached_archive, archive)
        else:
            request = Request(str(target["url"]), headers={"User-Agent": "Literary-Engineering-Studio"})
            with urlopen(request, timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        actual = _sha256(archive)
        if actual != expected:
            raise ValueError(f"OpenCode checksum mismatch: expected {expected}, got {actual}")
        with zipfile.ZipFile(archive) as bundle:
            _safe_extract(bundle, root)
    if not executable.is_file():
        raise FileNotFoundError(f"OpenCode archive did not contain {executable.name}")
    notice_source = _bundled_vendor_dir() / "OPENCODE-NOTICE.md"
    shutil.copy2(notice_source, root / "OPENCODE-NOTICE.md")
    _write_installation_receipt(executable, manifest, target_id)
    return _installation_result(executable, manifest, target_id, "installed")


def verify_opencode(path: Path) -> dict[str, Any]:
    executable = path.expanduser().resolve()
    if not executable.is_file():
        return {"verified": False, "executable": str(executable), "detail": "executable not found"}
    manifest = bundle_manifest()
    try:
        target_id = current_target()
    except RuntimeError:
        target_id = "unsupported"
    target = manifest["targets"].get(target_id, {})
    archive_checksum = str(target.get("sha256") or "")
    actual = _sha256(executable)
    receipt = _read_installation_receipt(executable)
    expected_binary = str(receipt.get("binary_sha256") or "") if receipt else ""
    is_build_placeholder = bool(receipt and str(receipt.get("status") or "") == "build-time-receipt-required")
    receipt_matches = bool(
        receipt
        and expected_binary
        and expected_binary == actual
        and str(receipt.get("version") or "") == str(manifest["version"])
        and str(receipt.get("target") or "") == target_id
        and str(receipt.get("executable") or "") == executable.name
    )
    verification_state = (
        "receipt-verified"
        if receipt_matches
        else "build-time-receipt-required"
        if is_build_placeholder
        else "receipt-mismatch"
        if receipt
        else "external-or-unrecorded"
    )
    return {
        "verified": receipt_matches,
        "verification_state": verification_state,
        "executable": str(executable),
        "pinned_version": str(manifest["version"]),
        "target": target_id,
        "archive_sha256": archive_checksum,
        "binary_sha256": actual,
        "expected_binary_sha256": expected_binary,
        "receipt_path": str(_receipt_path(executable)) if receipt else "",
    }


def ensure_opencode_integrity(path: Path) -> dict[str, Any]:
    """Reject a binary that has changed after a verified pinned installation.

    Explicit system binaries remain supported for advanced users, but are
    labelled external/unrecorded rather than being mistaken for a verified
    bundled artifact.
    """

    verification = verify_opencode(path)
    if verification.get("verification_state") == "receipt-mismatch":
        raise RuntimeError(
            "OpenCode binary integrity verification failed. Reinstall the pinned bundle before running Agent tasks."
        )
    return verification


def _installation_result(executable: Path, manifest: dict[str, Any], target: str, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "version": str(manifest["version"]),
        "target": target,
        "executable": str(executable.resolve()),
        "binary_sha256": _sha256(executable),
        "verification": verify_opencode(executable),
    }


def _receipt_path(executable: Path) -> Path:
    return executable.expanduser().resolve().parent / INSTALLATION_RECEIPT


def _write_installation_receipt(executable: Path, manifest: dict[str, Any], target: str) -> Path:
    receipt = {
        "schema": "arcvellum/opencode-installation/v1",
        "version": str(manifest["version"]),
        "target": target,
        "executable": executable.name,
        "archive_sha256": str(manifest["targets"][target]["sha256"]),
        "binary_sha256": _sha256(executable),
    }
    path = _receipt_path(executable)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read_installation_receipt(executable: Path) -> dict[str, Any] | None:
    path = _receipt_path(executable)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_cached_archive(root: Path, manifest: dict[str, Any], target_id: str) -> Path | None:
    """Return a local archive only after it passes the pinned manifest hash.

    Source and CI builds deliberately keep the downloaded archive next to the
    expanded executable. Reusing that archive avoids a second flaky network
    transfer while retaining the exact same integrity proof as a fresh fetch.
    """

    target = manifest["targets"][target_id]
    archive_name = str(target["archive"])
    version = str(manifest["version"])
    expected = str(target["sha256"]).lower()
    candidates = [
        root.parent / archive_name,
        repository_root() / "build" / "vendor" / f"opencode-v{version}" / archive_name,
    ]
    for candidate in dict.fromkeys(path.resolve() for path in candidates):
        if candidate.is_file() and _sha256(candidate) == expected:
            return candidate
    return None


def _safe_extract(bundle: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in bundle.infolist():
        target = (root / member.filename).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"unsafe path in OpenCode archive: {member.filename}")
    bundle.extractall(root)
