"""Atomic install, restore and clone operations for demo projects."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from shutil import copytree, rmtree
from typing import Any
from zipfile import ZipFile

from literary_engineering_studio_engine.public.projects import atomic_write_text

from .bundle import DemoBundleVerification, verify_demo_bundle


@dataclass(frozen=True)
class DemoInstallResult:
    project_root: Path
    status: str
    bundle_id: str
    version: str


def install_demo_bundle(
    bundle_path: Path | str,
    projects_root: Path | str,
    *,
    restore_as: str = "",
) -> DemoInstallResult:
    verification = verify_demo_bundle(bundle_path).require_valid()
    manifest = verification.manifest
    parent = Path(projects_root).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    folder = restore_as.strip() or str(manifest["project_folder"])
    if not _safe_component(folder):
        raise ValueError("demo install folder is unsafe")
    target = parent / folder
    if target.exists():
        if _installed_project_matches(target, manifest):
            return _result(target, "already_installed", manifest)
        raise FileExistsError(
            f"demo target already exists and differs from the bundle: {target}; "
            "choose an explicit restore_as folder"
        )
    staging = parent / f".{folder}.installing"
    if staging.exists():
        rmtree(staging)
    staging.mkdir(parents=True)
    try:
        _extract_verified_project(verification, staging)
        _write_install_record(staging, manifest)
        if not _installed_project_matches(staging, manifest):
            raise ValueError("installed demo project failed deterministic verification")
        staging.replace(target)
    except Exception:
        if staging.exists():
            rmtree(staging)
        raise
    return _result(target, "installed", manifest)


def clone_demo_project(
    demo_project_root: Path | str,
    target: Path | str,
    *,
    title: str = "",
) -> Path:
    source = Path(demo_project_root).expanduser().resolve()
    identity = _read_json(source / ".arcvellum-demo.json")
    if identity.get("schema") != "arcvellum/authorized-demo-project/v1":
        raise ValueError("source project is not an authorized ArcVellum demo")
    destination = Path(target).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"editable copy target already exists: {destination}")
    copytree(source, destination)
    (destination / ".arcvellum-demo.json").unlink(missing_ok=True)
    (destination / ".arcvellum-demo-install.json").unlink(missing_ok=True)
    clone_record = {
        "schema": "arcvellum/demo-editable-copy/v1",
        "source_work_id": identity.get("work_id"),
        "source_manifest_digest": identity.get("manifest_digest"),
        "origin": "authorized_demo_copy",
        "authorization_note": (
            "复制不会扩大原授权范围；续写、改写和再分发仍应遵守授权与适用法律。"
        ),
    }
    atomic_write_text(
        destination / ".arcvellum-demo-copy.json",
        json.dumps(clone_record, ensure_ascii=False, indent=2) + "\n",
    )
    _make_project_editable(destination, title=title)
    return destination


def _extract_verified_project(verification: DemoBundleVerification, staging: Path) -> None:
    manifest = verification.manifest
    expected = {
        f"project/{item['path']}": item
        for item in manifest["files"]
        if isinstance(item, dict)
    }
    with ZipFile(verification.bundle_path) as package:
        for archive_name, record in expected.items():
            relative = str(record["path"])
            target = (staging / relative).resolve()
            try:
                target.relative_to(staging.resolve())
            except ValueError as error:
                raise ValueError("demo bundle extraction escaped the target") from error
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = package.read(archive_name)
            target.write_bytes(payload)


def _write_install_record(root: Path, manifest: dict[str, Any]) -> None:
    record = {
        "schema": "arcvellum/demo-install/v1",
        "bundle_id": manifest["bundle_id"],
        "version": manifest["version"],
        "project_digest": manifest["project_digest"],
        "authorized_manifest_digest": manifest.get("authorized_manifest_digest", ""),
    }
    atomic_write_text(
        root / ".arcvellum-demo-install.json",
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
    )


def _installed_project_matches(root: Path, manifest: dict[str, Any]) -> bool:
    record = _read_json(root / ".arcvellum-demo-install.json", optional=True)
    if record.get("project_digest") != manifest.get("project_digest"):
        return False
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            return False
        path = root / str(item.get("path") or "")
        if not path.is_file():
            return False
        payload = path.read_bytes()
        if len(payload) != int(item.get("byte_size") or 0):
            return False
        if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
            return False
    return True


def _make_project_editable(root: Path, *, title: str) -> None:
    project = root / "project.yaml"
    text = project.read_text(encoding="utf-8")
    text = text.replace("  status: reference\n", "  status: planning\n", 1)
    if title.strip():
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("  title:"):
                lines[index] = "  title: " + json.dumps(title.strip(), ensure_ascii=False)
                break
        text = "\n".join(lines).rstrip() + "\n"
    atomic_write_text(project, text)


def _result(root: Path, status: str, manifest: dict[str, Any]) -> DemoInstallResult:
    return DemoInstallResult(
        project_root=root,
        status=status,
        bundle_id=str(manifest["bundle_id"]),
        version=str(manifest["version"]),
    )


def _safe_component(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and not any(char in value for char in '<>:"/\\|?*\x00')


def _read_json(path: Path, *, optional: bool = False) -> dict[str, Any]:
    if optional and not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}
