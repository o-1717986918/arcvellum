from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.config import default_config
from literary_engineering_studio.projections.core_read_models import build_dashboard
from literary_engineering_studio_engine.init_project import InitOptions, init_work_project
from literary_engineering_studio_engine.project_interaction import build_current_human_choices
from literary_engineering_studio_engine.workflow.activity import build_workflow_activity
from literary_engineering_studio_engine.workflow.audit.task_status import (
    project_agent_task_status,
    project_route_audit,
)
from literary_engineering_studio_engine.workflow.dashboard import build_workflow_dashboard
from literary_engineering_studio_engine.workflow.dashboard_projection import (
    project_workflow_dashboard,
)
from literary_engineering_studio_engine.workflow.state import project_workflow_state


class ReadModelPurityTests(unittest.TestCase):
    def test_ui_projections_do_not_materialize_hidden_project_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            init_work_project(InitOptions(target=root, title="Pure Projection"))
            before = _project_snapshot(root)

            dashboard = project_workflow_dashboard(root)
            project_workflow_state(root, route="overall", scene_scope="dashboard")
            project_agent_task_status(root)
            project_route_audit(root, route="scene-development")
            build_workflow_activity(root)
            build_current_human_choices(root)
            build_current_human_choices(root, route="style-engineering")
            studio_dashboard = build_dashboard(default_config(), root)

            self.assertEqual(_project_snapshot(root), before)
            self.assertEqual(studio_dashboard["dashboard"]["summary"], dashboard["summary"])
            self.assertFalse((root / "workflow" / "dashboard").exists())

    def test_cli_dashboard_command_still_materializes_portable_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            init_work_project(InitOptions(target=root, title="Materialized Dashboard"))

            result = build_workflow_dashboard(root)

            self.assertTrue(result.json_path.is_file())
            self.assertTrue(result.markdown_path.is_file())
            self.assertTrue(result.html_path.is_file())
            self.assertTrue((root / "workflow" / "dashboard" / "route_state.json").is_file())


def _project_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()
