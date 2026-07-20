import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.application_info import (
    build_application_info,
    build_diagnostic_report,
    export_diagnostic_report,
)


class _Lifecycle:
    def health(self):
        return {"ready": True, "project_root": "C:/private/work", "job_store": {"ready": True}}


class _Bootstrap:
    def snapshot(self):
        return {"phase": "degraded", "ready": True, "degraded": True, "steps": [], "notices": []}


class ApplicationInfoTests(unittest.TestCase):
    def test_application_info_exposes_product_without_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "application": {"data_root": temporary},
                "agent_runners": {"opencode": {"model": "deepseek/chat"}},
                "updates": {"channel": "stable"},
            }
            with patch("literary_engineering_studio.application_info.locate_opencode", return_value=None):
                payload = build_application_info(config)
        self.assertEqual(payload["product_name"], "ArcVellum")
        self.assertEqual(payload["current_model"], "deepseek/chat")
        self.assertNotIn("credential", json.dumps(payload).lower())

    def test_diagnostic_report_redacts_secrets_paths_and_prose(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "application": {"data_root": temporary, "password": "should-never-appear"},
                "agent_runners": {"opencode": {"model": "provider/model", "token": "sk-example-secret-value"}},
                "model_connections": {"connections": []},
                "server": {"host": "127.0.0.1"},
            }
            with (
                patch("literary_engineering_studio.application_info.locate_opencode", return_value=None),
                patch("literary_engineering_studio.application_info.list_projects", return_value={"projects": [], "current_project": "C:/private/work"}),
                patch("literary_engineering_studio.application_info.agent_runner_status", return_value=[]),
            ):
                report = build_diagnostic_report(config, _Lifecycle(), _Bootstrap())
                target = export_diagnostic_report(config, _Lifecycle(), _Bootstrap())
            serialized = json.dumps(report, ensure_ascii=False)
            exported = target.read_text(encoding="utf-8")
        self.assertNotIn("should-never-appear", serialized)
        self.assertNotIn("sk-example-secret-value", serialized)
        self.assertNotIn("C:/private/work", serialized)
        self.assertIn("[redacted]", serialized)
        self.assertNotIn("should-never-appear", exported)


if __name__ == "__main__":
    unittest.main()
