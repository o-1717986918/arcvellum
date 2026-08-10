from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.observability.runtime_benchmark import BenchmarkCase
from literary_engineering_studio.observability.runtime_benchmark_live import (
    _configure_prompt_version,
    _safe_preflight_projection,
    _unavailable,
)


class RuntimeBenchmarkLiveTests(unittest.TestCase):
    def test_preflight_projection_keeps_only_count_and_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "run.json").write_text(
                json.dumps(
                    {
                        "preflight": {
                            "issues": [
                                {
                                    "code": "schema-error",
                                    "path": "C:/private/project/output.json",
                                    "message": "SECRET CONTENT",
                                },
                                {"code": "missing-field", "message": "PRIVATE"},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            projection = _safe_preflight_projection(root)

        self.assertEqual(projection["issue_count"], 2)
        self.assertEqual(projection["issue_codes"], ["missing-field", "schema-error"])
        self.assertNotIn("SECRET", json.dumps(projection))

    def test_live_prompt_version_override_is_in_memory_and_runtime_scoped(self):
        config = {"worker": {"prompt_program": {"mode": "shadow"}}}

        _configure_prompt_version(config, "v3", "pi-worker")

        prompt = config["worker"]["prompt_program"]
        self.assertEqual(prompt["mode"], "enforced")
        self.assertTrue(prompt["enforcement"]["enabled"])
        self.assertEqual(prompt["enforcement"]["runtimes"], ["pi-worker"])

        _configure_prompt_version(config, "v2", "pi-worker")
        self.assertEqual(prompt["mode"], "off")
        self.assertFalse(prompt["enforcement"]["enabled"])

    def test_unavailable_report_is_content_safe_and_explicit(self):
        case = BenchmarkCase(
            case_id="analysis",
            benchmark_class="analysis",
            fixture_id="fixture",
            title="title",
            premise="premise",
            work_type="novel",
            target_length=30000,
            route="scene-development",
            preparation="deterministic-prefix",
            expected_state="roleplay-agent-task",
            availability="ready",
            rationale="rationale",
        )
        report = _unavailable(case, "opencode", "runner missing", prompt_version="v3")
        self.assertEqual(report["status"], "evidence-insufficient")
        self.assertEqual(report["failure_kind"], "runner-unavailable")
        self.assertEqual(report["sample"], {})
        self.assertEqual(report["requested_prompt_version"], "v3")
        self.assertNotIn("premise", str(report))


if __name__ == "__main__":
    unittest.main()
