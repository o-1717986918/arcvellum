"""Create a Tauri updater manifest and release checksums from signed artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil


def build_manifest(
    *,
    bundle_dir: Path,
    output_dir: Path,
    version: str,
    base_url: str,
    notes: str,
) -> dict[str, object]:
    artifacts = []
    for signature_path in sorted(bundle_dir.rglob("*.sig")):
        artifact = Path(str(signature_path)[: -len(".sig")])
        if artifact.is_file() and (artifact.name.endswith(".nsis.zip") or artifact.name.endswith("-setup.exe")):
            artifacts.append(artifact)
    if not artifacts:
        unsigned = sorted(bundle_dir.rglob("*.nsis.zip")) + sorted(bundle_dir.rglob("*-setup.exe"))
        current = [path for path in unsigned if version in path.name]
        candidate = current[0] if len(current) == 1 else unsigned[0] if len(unsigned) == 1 else None
        if candidate is not None:
            raise RuntimeError(f"signed updater artifact is missing its signature: {candidate}.sig")
    if len(artifacts) != 1:
        raise RuntimeError(f"expected exactly one signed NSIS updater artifact, found {len(artifacts)}")
    artifact = artifacts[0]
    signature = Path(str(artifact) + ".sig")
    if not signature.is_file() or not signature.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"signed updater archive is missing its signature: {signature}")
    installers = []
    if artifact.suffix.lower() != ".exe":
        installers = [
            path
            for path in sorted(bundle_dir.rglob("*-setup.exe")) + sorted(bundle_dir.rglob("*.msi"))
            if version in path.name
        ]
    output_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in dict.fromkeys([artifact, signature, *installers]):
        target = output_dir / source.name
        shutil.copy2(source, target)
        copied.append(target)
    payload = {
        "version": version,
        "notes": notes.strip(),
        "pub_date": datetime.now(timezone.utc).isoformat(),
        "platforms": {
            "windows-x86_64": {
                "signature": signature.read_text(encoding="utf-8").strip(),
                "url": base_url.rstrip("/") + "/" + artifact.name,
            }
        },
    }
    manifest = output_dir / "latest.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    copied.append(manifest)
    checksums = output_dir / "SHA256SUMS.txt"
    checksums.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in sorted(copied, key=lambda item: item.name)),
        encoding="utf-8",
    )
    return {
        "manifest": str(manifest),
        "checksums": str(checksums),
        "files": [path.name for path in copied] + [checksums.name],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--notes", default="ArcVellum 更新。")
    args = parser.parse_args()
    result = build_manifest(
        bundle_dir=args.bundle_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        version=args.version,
        base_url=args.base_url,
        notes=args.notes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
