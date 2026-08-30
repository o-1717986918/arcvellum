"""Reject release builds whose public version declarations diverge."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


VERSION_PATTERN = re.compile(r'^\s*version\s*=\s*"([^"]+)"', re.MULTILINE)
PYTHON_PATTERN = re.compile(r'__version__\s*=\s*"([^"]+)"')
WORKER_PATTERN = re.compile(r'const\s+VERSION\s*=\s*"([^"]+)"')


def version_matrix(root: Path) -> dict[str, str]:
    root = root.resolve()
    python_source = (root / "src/literary_engineering_studio/__init__.py").read_text(encoding="utf-8")
    python_match = PYTHON_PATTERN.search(python_source)
    if not python_match:
        raise RuntimeError("could not read Studio Python version")
    pyproject_match = VERSION_PATTERN.search((root / "pyproject.toml").read_text(encoding="utf-8"))
    cargo_match = VERSION_PATTERN.search((root / "desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    if not pyproject_match or not cargo_match:
        raise RuntimeError("could not read project or desktop package version")
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    worker_package = json.loads((root / "workers/pi-worker/package.json").read_text(encoding="utf-8"))
    worker_source = (root / "workers/pi-worker/src/main.ts").read_text(encoding="utf-8")
    worker_match = WORKER_PATTERN.search(worker_source)
    if not worker_match:
        raise RuntimeError("could not read Pi Worker runtime version")
    tauri = json.loads((root / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    return {
        "python": python_match.group(1),
        "pyproject": pyproject_match.group(1),
        "node": str(package.get("version") or ""),
        "pi-worker-node": str(worker_package.get("version") or ""),
        "pi-worker-runtime": worker_match.group(1),
        "cargo": cargo_match.group(1),
        "tauri": str(tauri.get("version") or ""),
    }


def verify_versions(root: Path) -> dict[str, object]:
    matrix = version_matrix(root)
    unique = sorted(set(matrix.values()))
    if len(unique) != 1 or not unique[0]:
        raise RuntimeError("version declarations diverge: " + json.dumps(matrix, ensure_ascii=False))
    return {"ok": True, "version": unique[0], "sources": matrix}


def main(argv: list[str] | None = None) -> int:
    root = Path((argv or sys.argv[1:])[0]).expanduser() if (argv or sys.argv[1:]) else Path(__file__).resolve().parents[1]
    print(json.dumps(verify_versions(root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
