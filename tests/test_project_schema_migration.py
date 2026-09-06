"""Project identity migration must be bounded, backed up, and repeatable."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio_engine.foundation.schema_aliases import (
    COMPLETION_SCHEMA,
    PROJECT_READING_SCHEMA,
    PROJECT_SCHEMA,
    SCHEMA_ALIASES,
    STYLE_EVAL_SCHEMA,
    STYLE_SKILL_SCHEMA,
    schema_matches,
)
from literary_engineering_studio_engine.literary.style.defaults import ensure_default_style_mount
from literary_engineering_studio_engine.projects.init import InitOptions, init_work_project
from literary_engineering_studio_engine.projects.migration import migrate_project_schemas
from literary_engineering_studio_engine.tasking.package_contract import enrich_task_payload
from literary_engineering_studio_engine.tasking.spec_models import TASK_SCHEMA_V1, TASK_SCHEMA_V2
from literary_engineering_studio_engine.tasking.storage import write_task_payload


ROOT = Path(__file__).resolve().parents[1]


class SchemaAliasRegistryTests(unittest.TestCase):
    def test_registered_legacy_identities_match_canonical_values(self):
        pairs = (
            ("literary-work-project/v0.1", PROJECT_READING_SCHEMA),
            ("literary-engineering-workbench/agent-task-completion/v1", COMPLETION_SCHEMA),
            ("literary-engineering-workbench/style-eval/v0.1", STYLE_EVAL_SCHEMA),
            ("literary-engineering-workbench/style-skill/v0.1", STYLE_SKILL_SCHEMA),
        )
        for legacy, canonical in pairs:
            self.assertTrue(schema_matches(legacy, canonical))
            self.assertEqual(SCHEMA_ALIASES.migration_target(legacy), canonical)
        self.assertFalse(schema_matches("unknown/v1", COMPLETION_SCHEMA))


class ProjectSchemaMigrationTests(unittest.TestCase):
    def test_new_project_and_default_style_use_native_identities(self):
        with TemporaryDirectory() as raw:
            root = Path(raw) / "work"
            init_work_project(InitOptions(target=root, title="Native schema"))
            ensure_default_style_mount(root)

            self.assertTrue((root / "project.yaml").read_text(encoding="utf-8").startswith(f"schema: {PROJECT_SCHEMA}\n"))
            self.assertTrue((root / "agentread.yaml").read_text(encoding="utf-8").startswith(f"schema: {PROJECT_READING_SCHEMA}\n"))
            legacy_hits = []
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml", ".md"}:
                    if "literary-engineering-workbench/" in path.read_text(encoding="utf-8", errors="ignore"):
                        legacy_hits.append(path.relative_to(root).as_posix())
            self.assertEqual(legacy_hits, [])

    def test_preview_backup_apply_and_second_apply_are_safe(self):
        with TemporaryDirectory() as raw:
            root = Path(raw) / "legacy"
            init_work_project(InitOptions(target=root, title="Legacy schema"))
            (root / "project.yaml").write_text(
                (root / "project.yaml").read_text(encoding="utf-8").removeprefix(f"schema: {PROJECT_SCHEMA}\n"),
                encoding="utf-8",
            )
            (root / "agentread.yaml").write_text("schema: literary-work-project/v0.1\nread_first: []\n", encoding="utf-8")
            completion = root / "reviews" / "legacy.agent_completion.json"
            completion.write_text(
                json.dumps({"schema": "literary-engineering-workbench/agent-task-completion/v1", "status": "complete"}),
                encoding="utf-8",
            )
            unknown = root / "reviews" / "unknown.json"
            unknown.write_text(json.dumps({"schema": "literary-engineering-workbench/unregistered/v9"}), encoding="utf-8")
            task = root / "workflow" / "tasks" / "legacy.task.json"
            task.parent.mkdir(parents=True, exist_ok=True)
            task.write_text(json.dumps(_legacy_task_payload(), ensure_ascii=False, indent=2), encoding="utf-8")

            before = {path: path.read_bytes() for path in (root / "project.yaml", root / "agentread.yaml", completion, unknown, task)}
            preview = migrate_project_schemas(root, action="preview")
            self.assertGreaterEqual(len(preview.changes), 4)
            self.assertIn(("reviews/unknown.json", "literary-engineering-workbench/unregistered/v9"), preview.retained_legacy)
            self.assertEqual(before, {path: path.read_bytes() for path in before})

            backup = Path(raw) / "backup"
            backed_up = migrate_project_schemas(root, action="backup", backup_root=backup)
            self.assertEqual(backed_up.backup_root, backup.resolve())
            self.assertTrue((backup / "files" / "project.yaml").is_file())
            self.assertEqual(before, {path: path.read_bytes() for path in before})

            applied_backup = Path(raw) / "apply-backup"
            applied = migrate_project_schemas(root, action="apply", backup_root=applied_backup)
            self.assertTrue(applied.applied)
            self.assertTrue((root / "project.yaml").read_text(encoding="utf-8").startswith(f"schema: {PROJECT_SCHEMA}\n"))
            self.assertIn(PROJECT_READING_SCHEMA, (root / "agentread.yaml").read_text(encoding="utf-8"))
            self.assertEqual(json.loads(completion.read_text(encoding="utf-8"))["schema"], COMPLETION_SCHEMA)
            self.assertEqual(json.loads(task.read_text(encoding="utf-8"))["schema"], TASK_SCHEMA_V2)
            self.assertEqual(json.loads(unknown.read_text(encoding="utf-8"))["schema"], "literary-engineering-workbench/unregistered/v9")

            repeated = migrate_project_schemas(root, action="apply", backup_root=Path(raw) / "unused-backup")
            self.assertFalse(repeated.changed)
            self.assertFalse(repeated.applied)
            self.assertIsNone(repeated.backup_root)

    def test_unknown_legacy_project_identity_is_reported_without_rewrite(self):
        with TemporaryDirectory() as raw:
            root = Path(raw) / "legacy"
            init_work_project(InitOptions(target=root, title="Unknown project schema"))
            descriptor = root / "project.yaml"
            descriptor.write_text(
                descriptor.read_text(encoding="utf-8").replace(
                    f"schema: {PROJECT_SCHEMA}",
                    "schema: literary-engineering-workbench/project/v99",
                    1,
                ),
                encoding="utf-8",
            )

            preview = migrate_project_schemas(root, action="preview")

            self.assertIn(
                ("project.yaml", "literary-engineering-workbench/project/v99"),
                preview.retained_legacy,
            )
            self.assertFalse(preview.changed)
            self.assertTrue(
                descriptor.read_text(encoding="utf-8").startswith(
                    "schema: literary-engineering-workbench/project/v99\n"
                )
            )

    def test_new_v2_task_storage_canonicalizes_registered_nested_schemas(self):
        with TemporaryDirectory() as raw:
            path = Path(raw) / "task.json"
            enriched = enrich_task_payload(_legacy_task_payload())
            write_task_payload(path, enriched, storage_schema=TASK_SCHEMA_V2)
            text = path.read_text(encoding="utf-8")
            self.assertIn(COMPLETION_SCHEMA, text)
            self.assertNotIn("literary-engineering-workbench/agent-task-completion/v1", text)


def _legacy_task_payload() -> dict[str, object]:
    fixture = json.loads((ROOT / "tests" / "fixtures" / "task_protocol" / "v1_route_envelopes.json").read_text(encoding="utf-8"))
    payload = dict(fixture["cases"][0]["payload"])
    payload["schema"] = TASK_SCHEMA_V1
    return payload


if __name__ == "__main__":
    unittest.main()
