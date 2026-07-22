"""Prove that a frozen desktop sidecar was built from the current source tree."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable


SCHEMA = "arcvellum/sidecar-provenance/v1"
PACKAGE_ROOTS = (
    Path("src/literary_engineering_studio"),
    Path("src/literary_engineering_studio_engine"),
)
FIXED_INPUTS = (
    Path("pyproject.toml"),
    Path("packaging/studio_sidecar.py"),
    Path("packaging/studio_sidecar.spec"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version(root: Path) -> str:
    source = (root / "src" / "literary_engineering_studio" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r"__version__\s*=\s*\"([^\"]+)\"", source)
    if not match:
        raise RuntimeError("could not read ArcVellum version from __init__.py")
    return match.group(1)


def _source_files(root: Path) -> Iterable[Path]:
    for relative in FIXED_INPUTS:
        candidate = root / relative
        if not candidate.is_file():
            raise RuntimeError(f"sidecar source input is missing: {relative.as_posix()}")
        yield candidate
    for package_root in PACKAGE_ROOTS:
        absolute = root / package_root
        if not absolute.is_dir():
            raise RuntimeError(f"sidecar package source is missing: {package_root.as_posix()}")
        for candidate in sorted(absolute.rglob("*")):
            if (
                candidate.is_file()
                and "__pycache__" not in candidate.parts
                and candidate.suffix != ".pyc"
            ):
                yield candidate


def source_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for candidate in _source_files(root):
        relative = candidate.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def write_provenance(*, root: Path, binary: Path, output: Path) -> dict[str, str]:
    root = root.resolve()
    binary = binary.resolve()
    if not binary.is_file():
        raise RuntimeError(f"frozen sidecar is missing: {binary}")
    payload = {
        "schema": SCHEMA,
        "version": _version(root),
        "source_sha256": source_sha256(root),
        "binary_sha256": _sha256(binary),
        "binary_name": binary.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_provenance(*, root: Path, binary: Path, manifest: Path) -> dict[str, str]:
    root = root.resolve()
    binary = binary.resolve()
    if not manifest.is_file():
        raise RuntimeError(f"sidecar provenance is missing: {manifest}")
    if not binary.is_file():
        raise RuntimeError(f"frozen sidecar is missing: {binary}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise RuntimeError("sidecar provenance schema is unsupported")
    expected = {
        "version": _version(root),
        "source_sha256": source_sha256(root),
        "binary_sha256": _sha256(binary),
        "binary_name": binary.name,
    }
    mismatches = [field for field, value in expected.items() if payload.get(field) != value]
    if mismatches:
        raise RuntimeError("frozen sidecar provenance is stale for: " + ", ".join(mismatches))
    return {str(key): str(value) for key, value in payload.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("write", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "write":
        result = write_provenance(root=args.root, binary=args.binary, output=args.manifest)
    else:
        result = verify_provenance(root=args.root, binary=args.binary, manifest=args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
