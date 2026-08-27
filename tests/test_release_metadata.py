from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from literary_engineering_studio import __version__


ROOT = Path(__file__).resolve().parents[1]


def _toml_version(path: Path) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"version is missing from {path}")
    return match.group(1)


class ReleaseMetadataTests(unittest.TestCase):
    def test_all_runtime_versions_match_the_python_core(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        tauri = json.loads((ROOT / "desktop" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        versions = {
            "python_core": __version__,
            "pyproject": _toml_version(ROOT / "pyproject.toml"),
            "package": str(package["version"]),
            "cargo": _toml_version(ROOT / "desktop" / "src-tauri" / "Cargo.toml"),
            "tauri": str(tauri["version"]),
        }
        self.assertEqual(set(versions.values()), {__version__}, versions)
        self.assertTrue((ROOT / "docs" / "releases" / f"v{__version__}.md").is_file())

    def test_windows_release_prepares_runtime_assets_before_python_contracts(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("TEMP: ${{ runner.temp }}", workflow)
        self.assertIn("TMP: ${{ runner.temp }}", workflow)
        python_contracts = workflow.index("- name: Test Python and prompt contracts")
        self.assertLess(workflow.index("- name: Test Vue client"), python_contracts)
        self.assertLess(workflow.index("- name: Test embedded Pi Worker"), python_contracts)


if __name__ == "__main__":
    unittest.main()
