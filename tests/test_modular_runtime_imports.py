"""Regression coverage for runtime dependencies exposed by module splits."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import typing
import unittest

from literary_engineering_studio.persistence.autopilot_runs import AutopilotRepository
from literary_engineering_studio_engine.director.records import _append_project_direction_memory
from literary_engineering_studio_engine.projections.interaction.choices import _latest_approval_record
from literary_engineering_studio_engine.projections.interaction.editing import record_ui_note
from literary_engineering_studio_engine.routes.export.definition import _to_int
from literary_engineering_studio_engine.workflow.audit.evidence import _mounted_style_exists
from literary_engineering_studio_engine.workflow.audit.export import _delivery_trace_hits
from literary_engineering_studio_engine.workflow.state_assets import _asset_states


class ModularRuntimeImportTests(unittest.TestCase):
    def test_autopilot_type_annotations_resolve(self):
        hints = typing.get_type_hints(AutopilotRepository._append_autopilot_event_tx)
        self.assertIn("connection", hints)

    def test_director_memory_fallback_writes_a_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = _append_project_direction_memory(root, "director-01", "让叙事保持克制而有余韵", {})
            self.assertTrue(result["index"].is_file())
            self.assertTrue(result["digest"].is_file())
            self.assertIn("叙事保持克制", result["digest"].read_text(encoding="utf-8"))

    def test_interaction_records_use_json_and_stable_note_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approvals = root / "workflow" / "approvals"
            approvals.mkdir(parents=True)
            (approvals / "index.jsonl").write_text(
                '{"run_id":"run-01","decision":"approve"}\n', encoding="utf-8"
            )
            self.assertEqual(_latest_approval_record(root, "run-01")["decision"], "approve")
            recorded = record_ui_note(root, target_type="scenes", target_id="scene_0001", note="加强结尾余波")
            self.assertTrue((root / recorded["note_path"]).is_file())

    def test_export_workspace_gate_parses_numeric_summary_values(self):
        self.assertEqual(_to_int("1"), 1)
        self.assertEqual(_to_int(None), 0)
        self.assertEqual(_to_int("not-a-number"), 0)

    def test_asset_state_infers_type_from_registered_candidate_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "canon" / "candidates" / "locations" / "harbor.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("{}", encoding="utf-8")
            assets = _asset_states(root)
            self.assertEqual(assets[0]["asset_type"], "location")

    def test_audit_helpers_read_paths_and_delivery_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mounted = root / "style" / "mounted" / "quiet-prose.md"
            mounted.parent.mkdir(parents=True)
            mounted.write_text("style", encoding="utf-8")
            delivery = root / "delivery.md"
            delivery.write_text("scene_0001\n[AGENT_TASK: internal]", encoding="utf-8")
            self.assertTrue(_mounted_style_exists(root))
            self.assertEqual(_delivery_trace_hits(delivery), ["scene-id", "agent-task"])


if __name__ == "__main__":
    unittest.main()
