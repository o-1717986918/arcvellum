from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.config import default_config
from literary_engineering_studio.runtimes import DEFAULT_RUNTIME_REGISTRY


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class RetiredRuntimeSurfaceTests(unittest.TestCase):
    def test_opencode_is_absent_from_runtime_api_ui_and_desktop_resources(self):
        self.assertNotIn("opencode", DEFAULT_RUNTIME_REGISTRY.ids())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = default_config()
            config["application"]["data_root"] = str(root)
            config["application"]["database_path"] = str(root / "studio.sqlite3")
            config["application"]["projects_root"] = str(root / "projects")
            config["worker"]["runs_root"] = str(root / "runs")
            paths = create_app(config).openapi()["paths"]
        self.assertFalse(any("opencode" in path.lower() for path in paths))

        retired_paths = (
            "src/literary_engineering_studio/integrations/opencode/__init__.py",
            "src/literary_engineering_studio/runtimes/opencode.py",
            "src/literary_engineering_studio/vendor/opencode-manifest.json",
            "desktop/src-tauri/resources/opencode",
        )
        self.assertFalse(
            [path for path in retired_paths if (REPOSITORY_ROOT / path).exists()]
        )

        client_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (REPOSITORY_ROOT / "client" / "src").rglob("*.vue")
        )
        self.assertNotIn("opencode", client_source.lower())


if __name__ == "__main__":
    unittest.main()
