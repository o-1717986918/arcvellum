"""Deterministic ArcVellum demo bundle creation and verification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


DEMO_BUNDLE_SCHEMA = "arcvellum/demo-bundle/v1"
MAX_DEMO_BUNDLE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class DemoBundleVerification:
    bundle_path: Path
    manifest: dict[str, Any]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def require_valid(self) -> "DemoBundleVerification":
        if self.errors:
            raise ValueError("demo bundle is invalid: " + "; ".join(self.errors))
        return self


def build_demo_bundle(
    project_root: Path | str,
    output: Path | str,
    *,
    bundle_id: str,
    version: str,
    project_folder: str = "",
) -> Path:
    root = Path(project_root).expanduser().resolve()
    identity = _require_sealed_demo_project(root)
    folder = _normalized_project_folder(project_folder, bundle_id=bundle_id)
    records = _project_file_records(root)
    manifest = _bundle_manifest(
        identity=identity,
        bundle_id=bundle_id,
        version=version,
        project_folder=folder,
        records=records,
    )
    destination = Path(output).expanduser().resolve()
    _write_demo_archive(destination, root=root, manifest=manifest, records=records)
    verify_demo_bundle(destination).require_valid()
    return destination


def _require_sealed_demo_project(root: Path) -> dict[str, Any]:
    if not (root / "project.yaml").is_file():
        raise FileNotFoundError(f"ArcVellum project not found: {root}")
    identity = _read_json(root / ".arcvellum-demo.json")
    if identity.get("schema") != "arcvellum/authorized-demo-project/v1":
        raise ValueError("demo bundle requires an authorized demo project identity")
    if identity.get("read_only_reference") is not True or identity.get("build_status") != "sealed":
        raise ValueError("demo bundle requires a sealed read-only reference project")
    return identity


def _normalized_project_folder(project_folder: str, *, bundle_id: str) -> str:
    folder = project_folder.strip() or f"{bundle_id}-demo"
    if not _safe_component(folder):
        raise ValueError("project_folder must be one safe directory name")
    return folder


def _project_file_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise ValueError(f"demo bundle does not allow symlinks: {path}")
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_size": len(payload),
            }
        )
    return records


def _bundle_manifest(
    *,
    identity: dict[str, Any],
    bundle_id: str,
    version: str,
    project_folder: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": DEMO_BUNDLE_SCHEMA,
        "bundle_id": bundle_id,
        "version": version,
        "project_folder": project_folder,
        "title": str(identity.get("title") or bundle_id),
        "author": str(identity.get("author") or ""),
        "work_id": str(identity.get("work_id") or ""),
        "authorized_manifest_digest": str(identity.get("manifest_digest") or ""),
        "project_digest": _file_set_digest(records),
        "file_count": len(records),
        "uncompressed_bytes": sum(int(item["byte_size"]) for item in records),
        "files": records,
    }


def _write_demo_archive(
    destination: Path,
    *,
    root: Path,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=9) as package:
        _write_zip_bytes(
            package,
            "bundle.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        for record in records:
            relative = str(record["path"])
            _write_zip_bytes(package, f"project/{relative}", (root / relative).read_bytes())


def verify_demo_bundle(bundle_path: Path | str) -> DemoBundleVerification:
    path = Path(bundle_path).expanduser().resolve()
    if not path.is_file():
        return DemoBundleVerification(path, {}, (f"demo bundle not found: {path}",))
    errors: list[str] = []
    manifest: dict[str, Any] = {}
    try:
        with ZipFile(path) as package:
            manifest = _read_bundle_manifest(package)
            errors.extend(_manifest_errors(manifest))
            errors.extend(_archive_errors(package, manifest))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        errors.append(f"cannot read demo bundle: {error}")
    return DemoBundleVerification(path, manifest, tuple(dict.fromkeys(errors)))


def _manifest_errors(manifest: dict[str, Any]) -> list[str]:
    errors = _manifest_identity_errors(manifest)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return [*errors, "demo bundle manifest requires files"]
    errors.extend(error for item in files for error in _file_record_errors(item))
    paths = [str(item.get("path") or "") for item in files if isinstance(item, dict)]
    if len(paths) != len(set(paths)):
        errors.append("demo bundle paths must be unique")
    if _integer(manifest.get("file_count"), default=-1) != len(files):
        errors.append("demo bundle file_count mismatch")
    return errors


def _manifest_identity_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != DEMO_BUNDLE_SCHEMA:
        errors.append("unsupported demo bundle schema")
    for key in ("bundle_id", "version", "project_folder", "title", "work_id", "project_digest"):
        if not str(manifest.get(key) or "").strip():
            errors.append(f"demo bundle manifest requires {key}")
    if not _safe_component(str(manifest.get("project_folder") or "")):
        errors.append("demo bundle project_folder is unsafe")
    return errors


def _file_record_errors(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return ["demo bundle file record must be an object"]
    errors: list[str] = []
    relative = str(item.get("path") or "")
    if not _safe_relative_path(relative):
        errors.append(f"unsafe demo bundle path: {relative or '<empty>'}")
    digest = str(item.get("sha256") or "")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        errors.append(f"invalid demo bundle SHA-256: {relative}")
    if _integer(item.get("byte_size"), default=-1) < 0:
        errors.append(f"invalid demo bundle byte size: {relative}")
    return errors


def _read_bundle_manifest(package: ZipFile) -> dict[str, Any]:
    if "bundle.json" not in package.namelist():
        raise ValueError("demo bundle is missing bundle.json")
    manifest = json.loads(package.read("bundle.json").decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("bundle.json must contain an object")
    return manifest


def _archive_errors(package: ZipFile, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        f"project/{item.get('path')}"
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    }
    actual = {
        name
        for name in package.namelist()
        if name != "bundle.json" and not name.endswith("/")
    }
    if actual != expected:
        errors.append("demo bundle file inventory does not match bundle.json")
    records, total, file_errors = _verified_archive_records(package, manifest, actual)
    errors.extend(file_errors)
    if total > MAX_DEMO_BUNDLE_UNCOMPRESSED_BYTES:
        errors.append("demo bundle exceeds the uncompressed size limit")
    if records and _file_set_digest(records) != str(manifest.get("project_digest") or ""):
        errors.append("demo bundle project digest mismatch")
    return errors


def _verified_archive_records(
    package: ZipFile,
    manifest: dict[str, Any],
    actual: set[str],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    total = 0
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        relative = str(item.get("path") or "")
        archive_name = f"project/{relative}"
        if archive_name not in actual:
            continue
        payload = package.read(archive_name)
        total += len(payload)
        if len(payload) != _integer(item.get("byte_size"), default=-1):
            errors.append(f"demo bundle byte size mismatch: {relative}")
        if hashlib.sha256(payload).hexdigest() != str(item.get("sha256") or ""):
            errors.append(f"demo bundle SHA-256 mismatch: {relative}")
        records.append(dict(item))
    return records, total, errors


def _file_set_digest(records: list[dict[str, Any]]) -> str:
    value = "\n".join(
        f"{item['path']}:{item['sha256']}:{int(item['byte_size'])}"
        for item in sorted(records, key=lambda record: str(record["path"]))
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_zip_bytes(package: ZipFile, name: str, payload: bytes) -> None:
    info = ZipInfo(name, date_time=_ZIP_TIME)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    package.writestr(info, payload)


def _safe_component(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and not any(char in value for char in '<>:"/\\|?*\x00')


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value.replace("\\", "/"))
    return bool(value) and not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _integer(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload
