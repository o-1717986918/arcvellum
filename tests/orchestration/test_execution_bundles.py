from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    ExecutionBundle,
    bundle_template,
    bundle_template_catalog,
    bundle_violations,
    compile_bundles,
)

from tests.orchestration.plan_persistence_support import FINGERPRINT, shadow_pipeline


class ExecutionBundleCompilerTests(unittest.TestCase):
    def setUp(self):
        _, _, self.graph, _, _ = shadow_pipeline()

    def test_scene_analysis_bundle_merges_roleplay_and_branches(self):
        bundles = compile_bundles(
            self.graph,
            template_id="scene-analysis",
        )

        self.assertEqual(len(bundles), 1)
        bundle = bundles[0]
        self.assertEqual(bundle.scope_key, "scene_0001")
        self.assertEqual(bundle.step_node_ids, ("roleplay", "branches"))
        self.assertEqual(bundle.agent_role, "main-review-agent")
        self.assertEqual(bundle.stop_before, ("branch_selection",))
        self.assertEqual(bundle.base_revision, FINGERPRINT)
        self.assertEqual(bundle.atomic_writeback_group, "scene-analysis:scene_0001")
        self.assertEqual(bundle_violations(bundle), ())

    def test_scene_authoring_bundle_contains_only_writer_node(self):
        bundles = compile_bundles(
            self.graph,
            template_id="scene-authoring",
        )

        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].step_node_ids, ("prose",))
        self.assertEqual(bundles[0].agent_role, "main-creative-agent")
        self.assertIn(
            "drafts/scenes/scene_0001.md@promoted",
            bundles[0].expected_outputs,
        )

    def test_scene_quality_and_state_extraction_bundles(self):
        quality = compile_bundles(self.graph, template_id="scene-quality")
        state = compile_bundles(
            self.graph,
            template_id="scene-state-extraction",
        )

        self.assertEqual(quality[0].step_node_ids, ("review",))
        self.assertEqual(quality[0].agent_role, "main-review-agent")
        self.assertEqual(state[0].step_node_ids, ("state",))
        self.assertEqual(state[0].agent_role, "state-analyst")

    def test_chapter_planning_template_has_no_scene_graph_bundles(self):
        bundles = compile_bundles(
            self.graph,
            template_id="chapter-planning",
        )

        self.assertEqual(bundles, ())

    def test_all_templates_compile_without_error(self):
        bundles = compile_bundles(self.graph)
        template_ids = {bundle.template_id for bundle in bundles}

        self.assertEqual(
            template_ids,
            {
                "scene-analysis",
                "scene-authoring",
                "scene-quality",
                "scene-state-extraction",
            },
        )
        for bundle in bundles:
            self.assertEqual(bundle_violations(bundle), ())

    def test_scope_filter_and_unknown_scope(self):
        scoped = compile_bundles(self.graph, scope_key="scene_0001")
        unknown = compile_bundles(self.graph, scope_key="scene_0099")

        self.assertEqual(len(scoped), 4)
        self.assertEqual(unknown, ())

    def test_invalid_template_raises(self):
        with self.assertRaises(ValueError):
            bundle_template("not-a-template")
        with self.assertRaises(ValueError):
            compile_bundles(self.graph, template_id="not-a-template")

    def test_bundle_id_is_stable_and_deterministic(self):
        first = compile_bundles(
            self.graph,
            template_id="scene-analysis",
            context_snapshot_hash="snapshot-1",
        )
        second = compile_bundles(
            self.graph,
            template_id="scene-analysis",
            context_snapshot_hash="snapshot-1",
        )

        self.assertEqual(first[0].bundle_id, second[0].bundle_id)
        self.assertEqual(first[0].context_snapshot_hash, "snapshot-1")

    def test_catalog_is_whitelisted_and_single_role(self):
        for template in bundle_template_catalog():
            self.assertIn(template.scope_kind, {"chapter", "scene"})
            self.assertTrue(template.agent_role)
            self.assertTrue(template.stop_before)


class ExecutionBundleViolationTests(unittest.TestCase):
    def test_structural_violations_are_reported(self):
        bundle = ExecutionBundle(
            bundle_id="bundle-1",
            plan_id="plan-1",
            template_id="scene-analysis",
            scope_kind="scene",
            scope_key="scene_0001",
            step_node_ids=(),
            agent_role="",
            expected_outputs=(),
            base_revision="",
            context_snapshot_hash="",
            atomic_writeback_group="",
            stop_before=(),
        )

        codes = {item.code for item in bundle_violations(bundle)}
        self.assertEqual(
            codes,
            {
                "empty-step-nodes",
                "missing-agent-role",
                "missing-base-revision",
                "missing-writeback-group",
                "missing-stop-boundary",
            },
        )


if __name__ == "__main__":
    unittest.main()
