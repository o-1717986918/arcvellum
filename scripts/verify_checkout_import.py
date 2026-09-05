"""Fail when validation imports ArcVellum from a different checkout."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def checkout_report(repository: Path) -> dict[str, object]:
    root = repository.resolve()
    source = (root / "src").resolve()
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

    import literary_engineering_studio
    import literary_engineering_studio_engine

    packages = {
        "studio": Path(literary_engineering_studio.__file__).resolve(),
        "engine": Path(literary_engineering_studio_engine.__file__).resolve(),
    }
    outside = {
        name: str(path)
        for name, path in packages.items()
        if not path.is_relative_to(source)
    }
    return {
        "ok": not outside,
        "repository": str(root),
        "python": sys.executable,
        "commit": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "branch", "--show-current"),
        "dirty": bool(_git(root, "status", "--porcelain")),
        "package_roots": {name: str(path) for name, path in packages.items()},
        "outside_checkout": outside,
    }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def main() -> int:
    report = checkout_report(Path(__file__).resolve().parents[1])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
