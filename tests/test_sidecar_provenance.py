from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "packaging" / "sidecar_provenance.py"
SPEC = importlib.util.spec_from_file_location("arcvellum_sidecar_provenance", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _fixture_root(root: Path) -> tuple[Path, Path]:
    (root / "src" / "literary_engineering_studio").mkdir(parents=True)
    (root / "src" / "literary_engineering_studio_engine").mkdir(parents=True)
    (root / "packaging").mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "arcvellum"\n', encoding="utf-8")
    (root / "packaging" / "studio_sidecar.py").write_text("print(1)\n", encoding="utf-8")
    (root / "packaging" / "studio_sidecar.spec").write_text("spec\n", encoding="utf-8")
    (root / "src" / "literary_engineering_studio" / "__init__.py").write_text(
        '__version__ = "0.9.0"\n', encoding="utf-8"
    )
    (root / "src" / "literary_engineering_studio_engine" / "engine.py").write_text(
        "ENGINE = True\n", encoding="utf-8"
    )
    binary = root / "sidecar.exe"
    binary.write_bytes(b"frozen-sidecar")
    return binary, root / "build" / "sidecar-provenance.json"


class SidecarProvenanceTests(unittest.TestCase):
    def test_matching_binary_and_source_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary, manifest = _fixture_root(root)
            payload = MODULE.write_provenance(root=root, binary=binary, output=manifest)
            verified = MODULE.verify_provenance(root=root, binary=binary, manifest=manifest)

        self.assertEqual(payload["version"], "0.9.0")
        self.assertEqual(verified["binary_name"], "sidecar.exe")

    def test_source_or_binary_change_blocks_desktop_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary, manifest = _fixture_root(root)
            MODULE.write_provenance(root=root, binary=binary, output=manifest)
            (root / "src" / "literary_engineering_studio_engine" / "engine.py").write_text(
                "ENGINE = False\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "source_sha256"):
                MODULE.verify_provenance(root=root, binary=binary, manifest=manifest)
            MODULE.write_provenance(root=root, binary=binary, output=manifest)
            binary.write_bytes(b"changed-sidecar")
            with self.assertRaisesRegex(RuntimeError, "binary_sha256"):
                MODULE.verify_provenance(root=root, binary=binary, manifest=manifest)


if __name__ == "__main__":
    unittest.main()
