"""Build and verify the portable ArcVellum Pi Worker desktop resource."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable
from urllib.request import urlopen
import zipfile


SCHEMA = "arcvellum/pi-worker-installation/v1"
NODE_VERSION = "22.19.0"
NODE_ARCHIVE = f"node-v{NODE_VERSION}-win-x64.zip"
NODE_ARCHIVE_SHA256 = "ea3fad0e67a991d8477d8c01344b56e69c676ccb733f065b22436994b1253f86"
NODE_ARCHIVE_URL = f"https://nodejs.org/dist/v{NODE_VERSION}/{NODE_ARCHIVE}"
RECEIPT_NAME = "pi-worker-installation.json"


def stage_bundle(*, root: Path, destination: Path, cache_root: Path) -> dict[str, object]:
    root = root.resolve()
    worker = root / "workers" / "pi-worker"
    _require_worker_source(worker)
    npm = _npm_command()
    _run([npm, "ci", "--ignore-scripts"], cwd=worker)
    _run([npm, "run", "build"], cwd=worker)

    archive = _node_archive(cache_root.resolve())
    _reset_directory(destination.resolve(), root / "desktop" / "src-tauri" / "resources")
    _extract_node_executable(archive, destination / "node.exe")
    (destination / "dist").mkdir(parents=True, exist_ok=True)
    shutil.copy2(worker / "dist" / "main.js", destination / "dist" / "main.js")
    for name in ("package.json", "package-lock.json", "README.md"):
        shutil.copy2(worker / name, destination / name)
    shutil.copy2(root / "third_party" / "pi" / "PI-AGENT-LICENSE.txt", destination / "PI-AGENT-LICENSE.txt")
    shutil.copy2(root / "third_party" / "pi" / "PI-AGENT-NOTICE.md", destination / "PI-AGENT-NOTICE.md")

    payload = _receipt_payload(root=root, destination=destination)
    (destination / RECEIPT_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def verify_bundle(*, root: Path, destination: Path) -> dict[str, object]:
    root = root.resolve()
    destination = destination.resolve()
    receipt_path = destination / RECEIPT_NAME
    if not receipt_path.is_file():
        raise RuntimeError(f"Pi Worker installation receipt is missing: {receipt_path}")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise RuntimeError("Pi Worker installation receipt schema is unsupported")
    expected = _receipt_payload(root=root, destination=destination)
    fields = (
        "worker_version",
        "node_version",
        "node_archive_sha256",
        "worker_source_sha256",
        "package_lock_sha256",
        "bundle_sha256",
        "file_count",
    )
    mismatches = [name for name in fields if payload.get(name) != expected.get(name)]
    if mismatches:
        raise RuntimeError("Pi Worker desktop resource is stale for: " + ", ".join(mismatches))
    return payload


def _receipt_payload(*, root: Path, destination: Path) -> dict[str, object]:
    package = json.loads((root / "workers" / "pi-worker" / "package.json").read_text(encoding="utf-8"))
    bundled_files = tuple(_bundle_files(destination))
    return {
        "schema": SCHEMA,
        "worker_version": str(package.get("version") or ""),
        "node_version": NODE_VERSION,
        "node_archive": NODE_ARCHIVE,
        "node_archive_sha256": NODE_ARCHIVE_SHA256,
        "worker_source_sha256": _worker_source_sha256(root / "workers" / "pi-worker"),
        "package_lock_sha256": _sha256(root / "workers" / "pi-worker" / "package-lock.json"),
        "bundle_sha256": _tree_sha256(destination, bundled_files),
        "file_count": len(bundled_files),
        "entrypoint": "dist/main.js",
        "executable": "node.exe",
    }


def _worker_source_sha256(worker: Path) -> str:
    files = [worker / "package.json", worker / "package-lock.json", worker / "tsconfig.build.json"]
    files.extend(sorted((worker / "src").glob("*.ts")))
    files.extend(sorted((worker / "test").glob("*.ts")))
    return _paths_sha256(worker, files)


def _bundle_files(destination: Path) -> Iterable[Path]:
    for path in sorted(destination.rglob("*")):
        if path.is_file() and path.name != RECEIPT_NAME:
            yield path


def _tree_sha256(root: Path, files: Iterable[Path]) -> str:
    return _paths_sha256(root, files)


def _paths_sha256(root: Path, files: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _node_archive(cache_root: Path) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)
    archive = cache_root / NODE_ARCHIVE
    if not archive.is_file() or _sha256(archive) != NODE_ARCHIVE_SHA256:
        temporary = archive.with_suffix(".download")
        temporary.unlink(missing_ok=True)
        with urlopen(NODE_ARCHIVE_URL, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if _sha256(temporary) != NODE_ARCHIVE_SHA256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("downloaded Node.js archive failed SHA-256 verification")
        temporary.replace(archive)
    return archive


def _extract_node_executable(archive: Path, destination: Path) -> None:
    member = f"node-v{NODE_VERSION}-win-x64/node.exe"
    with zipfile.ZipFile(archive) as bundle:
        with bundle.open(member) as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)


def _reset_directory(path: Path, allowed_parent: Path) -> None:
    path = path.resolve()
    allowed_parent = allowed_parent.resolve()
    if path == allowed_parent or not path.is_relative_to(allowed_parent):
        raise RuntimeError(f"refusing to replace directory outside {allowed_parent}: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _require_worker_source(worker: Path) -> None:
    required = (worker / "package.json", worker / "package-lock.json", worker / "src" / "main.ts")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Pi Worker source is incomplete: " + ", ".join(missing))


def _npm_command() -> str:
    if sys.platform == "win32":
        return shutil.which("npm.cmd") or "npm.cmd"
    return shutil.which("npm") or "npm"


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed with {completed.returncode}: {' '.join(command)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("stage", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    args = parser.parse_args()
    if args.command == "stage":
        cache_root = args.cache_root or args.root / "build" / "vendor" / f"node-v{NODE_VERSION}"
        result = stage_bundle(root=args.root, destination=args.destination, cache_root=cache_root)
    else:
        result = verify_bundle(root=args.root, destination=args.destination)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
