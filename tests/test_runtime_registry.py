from __future__ import annotations

from pathlib import Path
import unittest

from literary_engineering_studio.runtimes import (
    DEFAULT_RUNTIME_REGISTRY,
    RuntimeAvailability,
    RuntimeFactoryContext,
    RuntimeRegistry,
    SubprocessRuntimeBase,
    agent_runner_status,
    build_runtime,
)
from literary_engineering_studio.runtimes.registry import runtime_descriptor


class FixtureRuntime(SubprocessRuntimeBase):
    runtime_id = "fixture"

    def availability(self) -> RuntimeAvailability:
        return RuntimeAvailability(self.runtime_id, True, "fixture", "fixture 1.0")

    def build_command(self, workspace: Path) -> tuple[str, ...]:
        return ("fixture", str(workspace))


class RuntimeRegistryTests(unittest.TestCase):
    def test_registry_rejects_duplicate_and_unknown_runtime_ids(self):
        descriptor = runtime_descriptor(FixtureRuntime)

        with self.assertRaisesRegex(ValueError, "duplicate"):
            RuntimeRegistry((descriptor, descriptor))

        registry = RuntimeRegistry((descriptor,))
        with self.assertRaisesRegex(ValueError, "unknown Agent runtime"):
            registry.descriptor("missing")

    def test_factory_receives_pool_and_role_without_concrete_core_branch(self):
        observed: dict[str, object] = {}

        def factory(
            settings: dict[str, object], context: RuntimeFactoryContext
        ) -> FixtureRuntime:
            observed.update(settings=settings, context=context)
            return FixtureRuntime(settings)

        registry = RuntimeRegistry((runtime_descriptor(FixtureRuntime, factory),))
        pool = object()
        runtime = build_runtime(
            "fixture",
            {"agent_runners": {"fixture": {"enabled": True}}},
            runtime_pool=pool,
            role="reviewer",
            registry=registry,
        )

        self.assertEqual(runtime.runtime_id, "fixture")
        self.assertEqual(observed["settings"], {"enabled": True, "role": "reviewer"})
        context = observed["context"]
        self.assertIsInstance(context, RuntimeFactoryContext)
        self.assertIs(context.runtime_pool, pool)

    def test_default_opencode_descriptor_injects_runtime_pool(self):
        pool = object()

        runtime = build_runtime(
            "opencode",
            {"agent_runners": {"opencode": {"enabled": True}}},
            runtime_pool=pool,
        )

        self.assertIs(runtime.runtime_pool, pool)

    def test_status_probe_can_use_an_isolated_registry(self):
        registry = RuntimeRegistry((runtime_descriptor(FixtureRuntime),))

        statuses = agent_runner_status(
            {"agent_runners": {"fixture": {"enabled": True}}},
            force_refresh=True,
            registry=registry,
        )

        self.assertEqual([item["runner_id"] for item in statuses], ["fixture"])
        self.assertTrue(statuses[0]["available"])

    def test_registry_extension_does_not_mutate_default_catalog(self):
        before = DEFAULT_RUNTIME_REGISTRY.ids()
        extended = DEFAULT_RUNTIME_REGISTRY.with_descriptor(
            runtime_descriptor(FixtureRuntime)
        )

        self.assertEqual(DEFAULT_RUNTIME_REGISTRY.ids(), before)
        self.assertEqual(extended.ids()[-1], "fixture")


if __name__ == "__main__":
    unittest.main()
