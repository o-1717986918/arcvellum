from __future__ import annotations

import unittest

from literary_engineering_studio.application.config import default_config
from literary_engineering_studio.automation.controller import ROUTE_ORDER
from literary_engineering_studio.orchestration import OrchestrationMode, orchestration_settings
from literary_engineering_studio_engine.orchestration_blueprint import (
    build_orchestration_blueprint as root_blueprint,
)
from literary_engineering_studio_engine.orchestration import (
    DEFAULT_ROUTE_ORDER,
    GateId,
    PlanNodeKind,
    formal_task_capabilities,
    mandatory_gates_for,
)
from literary_engineering_studio_engine.platforms.orchestration_blueprint import (
    build_orchestration_blueprint as platform_blueprint,
)
from literary_engineering_studio_engine.tasking.orchestration import (
    build_orchestration_blueprint as tasking_blueprint,
)


class OrchestrationFoundationTests(unittest.TestCase):
    def test_feature_is_disabled_and_fixed_by_default(self):
        settings = orchestration_settings(default_config())

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.configured_mode, OrchestrationMode.FIXED)
        self.assertEqual(settings.effective_mode, OrchestrationMode.FIXED)
        self.assertFalse(settings.production_chapter_horizon)
        self.assertFalse(settings.bundle_execution)
        self.assertFalse(settings.campaign_runtime)
        self.assertEqual(settings.chapter_horizon_size, 3)
        self.assertEqual(settings.campaign_checkpoint_interval_steps, 5)

    def test_production_rollout_flags_are_explicit_and_horizon_is_bounded(self):
        config = default_config()
        config["orchestration"].update(
            {
                "enabled": True,
                "mode": "assisted",
                "production_chapter_horizon": True,
                "chapter_horizon_size": 4,
                "bundle_execution": True,
                "campaign_runtime": True,
                "campaign_checkpoint_interval_steps": 8,
            }
        )
        settings = orchestration_settings(config)

        self.assertTrue(settings.production_chapter_horizon)
        self.assertTrue(settings.bundle_execution)
        self.assertTrue(settings.campaign_runtime)
        self.assertEqual(settings.chapter_horizon_size, 4)
        self.assertEqual(settings.campaign_checkpoint_interval_steps, 8)

        config["orchestration"]["chapter_horizon_size"] = 5
        with self.assertRaisesRegex(ValueError, "between 2 and 4"):
            orchestration_settings(config)

        config["orchestration"]["chapter_horizon_size"] = 4
        config["orchestration"]["campaign_checkpoint_interval_steps"] = 101
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            orchestration_settings(config)

    def test_partial_or_empty_config_safely_defaults_to_fixed(self):
        settings = orchestration_settings({})

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.configured_mode, OrchestrationMode.FIXED)
        self.assertEqual(settings.effective_mode, OrchestrationMode.FIXED)

    def test_disabled_feature_forces_fixed_effective_mode(self):
        config = default_config()
        config["orchestration"]["mode"] = "full_adaptive"

        settings = orchestration_settings(config)

        self.assertEqual(settings.configured_mode, OrchestrationMode.FULL_ADAPTIVE)
        self.assertEqual(settings.effective_mode, OrchestrationMode.FIXED)

    def test_default_route_macro_matches_current_autopilot(self):
        self.assertEqual(DEFAULT_ROUTE_ORDER, ROUTE_ORDER)

    def test_platform_blueprint_legacy_imports_reach_the_new_owner(self):
        self.assertIs(root_blueprint, platform_blueprint)
        self.assertIs(tasking_blueprint, platform_blueprint)

    def test_formal_catalog_covers_every_plan_node_kind_once(self):
        capabilities = formal_task_capabilities()

        self.assertEqual({item.node_kind for item in capabilities}, set(PlanNodeKind))
        self.assertEqual(len({item.capability_id for item in capabilities}), len(capabilities))
        self.assertTrue(all(item.allowed_task_types for item in capabilities))
        self.assertTrue(all("command" not in item.capability_id for item in capabilities))

    def test_formal_prose_gates_are_machine_owned_and_complete(self):
        gates = set(mandatory_gates_for(node_kind=PlanNodeKind.FORMAL_PROSE.value))

        self.assertTrue(
            {
                GateId.WORD_BUDGET.value,
                GateId.RHYTHM_CONTRACT.value,
                GateId.BRIDGE_CONTRACT.value,
                GateId.MOUNTED_STYLE.value,
                GateId.CAUSAL_SIMULATION.value,
                GateId.BRANCH_DECISION.value,
                GateId.PROSE_SINGLE_WRITER.value,
            }.issubset(gates)
        )

    def test_high_risk_scene_forces_full_roleplay(self):
        gates = mandatory_gates_for(
            node_kind=PlanNodeKind.ROLEPLAY_SIMULATION.value,
            risk_features={"new_character": True},
        )

        self.assertIn(GateId.FULL_ROLEPLAY.value, gates)


if __name__ == "__main__":
    unittest.main()
