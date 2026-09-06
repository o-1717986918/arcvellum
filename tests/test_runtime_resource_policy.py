"""Product packaging must not revive historical Engine instructions."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from literary_engineering_studio_engine.foundation.runtime_resources import (
    RUNTIME_DOCUMENT_FILES,
    RUNTIME_DOCUMENT_PREFIXES,
    RUNTIME_REFERENCE_FILES,
    is_installable_engine_resource,
)
from literary_engineering_studio_engine.tasking.protocol import list_protocol_routes


ROOT = Path(__file__).resolve().parents[1]
ENGINE_DATA = ROOT / "src" / "literary_engineering_studio_engine" / "_engine"


class RuntimeResourcePolicyTests(unittest.TestCase):
    def test_current_route_reading_is_installable(self):
        for route in list_protocol_routes():
            for path in route.read:
                if path.startswith(("docs/", "references/", "templates/")):
                    self.assertTrue(
                        is_installable_engine_resource(path),
                        f"{route.key}: {path}",
                    )

    def test_historical_documents_remain_source_only(self):
        historical = (
            "docs/roadmap.md",
            "docs/implementation/phase12-dify-dsl.md",
            "docs/plans/phase84-90-skill-kernel-hardening-plan.md",
            "references/artifact-contracts.md",
            "references/orchestration.md",
            "references/project-director-playbook.md",
            "references/workflows.md",
        )
        for relative in historical:
            self.assertTrue((ENGINE_DATA / relative).is_file(), relative)
            self.assertFalse(is_installable_engine_resource(relative), relative)

    def test_allowlisted_runtime_guides_do_not_advertise_retired_commands(self):
        retired = re.compile(
            r"`(?:dify-dsl|director-chat|director-status|run-langgraph|run-workflow|serve-api|config-show|config-init|config-set-profile)(?:\s|`)",
            re.IGNORECASE,
        )
        current = set(RUNTIME_REFERENCE_FILES) | set(RUNTIME_DOCUMENT_FILES)
        for prefix in RUNTIME_DOCUMENT_PREFIXES:
            current.update(
                path.relative_to(ENGINE_DATA).as_posix()
                for path in (ENGINE_DATA / prefix).glob("*.md")
            )
        for relative in sorted(current):
            text = (ENGINE_DATA / relative).read_text(encoding="utf-8")
            self.assertIsNone(retired.search(text), relative)

    def test_distribution_configuration_uses_document_allowlist(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn('"_engine/docs/**/*.md"', pyproject)
        self.assertNotIn('"_engine/references/*.md"', pyproject)
        spec = (ROOT / "packaging" / "studio_sidecar.spec").read_text(encoding="utf-8")
        self.assertIn("is_installable_engine_resource(relative)", spec)


if __name__ == "__main__":
    unittest.main()
