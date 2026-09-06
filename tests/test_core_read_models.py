from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import literary_engineering_studio.core_read_models as core_read_models
from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import (
    build_dashboard,
    build_library,
    install_core_import_path,
    mount_style,
)


class CoreReadModelTests(unittest.TestCase):
    def test_reuses_core_dashboard_and_library(self):
        config = default_config()
        install_core_import_path(config)
        from literary_engineering_studio_engine.projects.init import InitOptions, init_work_project

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            init_work_project(InitOptions(target=root, title="Studio Integration"))
            library = build_library(config, root)
            dashboard = build_dashboard(config, root)
            self.assertTrue(library["ok"])
            self.assertIn("sections", library)
            self.assertTrue(dashboard["ok"])
            self.assertIn("route_audits", dashboard)

    def test_mount_style_uses_default_library_without_dynamic_engine_module(self):
        config = default_config()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            library = Path(temporary) / "styles"
            result = SimpleNamespace(
                project_root=root,
                style_id="plain-prose",
                mount_dir=root / "style" / "mounted" / "plain-prose",
                mount_manifest_path=root / "style" / "mounted" / "plain-prose" / "mount.json",
                project_style_path=root / "style" / "active.md",
            )
            with (
                patch.object(core_read_models, "engine_default_style_library_root", return_value=library),
                patch.object(core_read_models, "engine_mount_style_skill", return_value=result) as mount,
                patch.object(core_read_models, "engine_active_project_style", return_value={}),
            ):
                payload = mount_style(config, root, "", "plain-prose")

            self.assertEqual(mount.call_args.kwargs["library_root"], library)
            self.assertEqual(payload["style_id"], "plain-prose")


if __name__ == "__main__":
    unittest.main()
