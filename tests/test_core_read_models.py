from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import build_dashboard, build_library, install_core_import_path


class CoreReadModelTests(unittest.TestCase):
    def test_reuses_core_dashboard_and_library(self):
        config = default_config()
        install_core_import_path(config)
        from literary_engineering_workbench.init_project import InitOptions, init_work_project

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            init_work_project(InitOptions(target=root, title="Studio Integration"))
            library = build_library(config, root)
            dashboard = build_dashboard(config, root)
            self.assertTrue(library["ok"])
            self.assertIn("sections", library)
            self.assertTrue(dashboard["ok"])
            self.assertIn("route_audits", dashboard)


if __name__ == "__main__":
    unittest.main()
