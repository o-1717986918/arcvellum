"""Packaging regressions for the Windows sidecar executable."""

from __future__ import annotations

from pathlib import Path
import unittest


class SidecarSpecTests(unittest.TestCase):
    def test_windows_sidecar_retains_console_subsystem_for_uvicorn_readiness(self) -> None:
        spec = (Path(__file__).resolve().parents[1] / "packaging" / "studio_sidecar.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("console=True", spec)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
