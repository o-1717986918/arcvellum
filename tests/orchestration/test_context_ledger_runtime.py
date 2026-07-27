from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from literary_engineering_studio.agent_session_tracking import track_agent_session_event
from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.observability.context_ledger import parse_context_ledger
from literary_engineering_studio.observability.context_ledger_tracking import (
    persist_context_ledger_from_run,
)
from literary_engineering_studio.sandbox import stage_task
from literary_engineering_studio.sandbox import materialize_agent_workspace
from literary_engineering_studio_engine.task_registry import _enrich_task_payload


class RuntimeContextLedgerTests(unittest.TestCase):
    def test_prompt_workspace_and_ledger_share_actual_copied_sources(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = _task(root, include_missing=True)

            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="context-selection")
            prompt = sandbox.prompt_path.read_text(encoding="utf-8")
            payload = json.loads((sandbox.run_root / "context-ledger.json").read_text(encoding="utf-8"))
            ledger = parse_context_ledger(payload)
            entries = {item.source_ref: item for item in ledger.entries}

            self.assertTrue((sandbox.workspace / "scenes/scene_0001.yaml").is_file())
            self.assertFalse((sandbox.workspace / "scenes/missing.yaml").exists())
            self.assertIn("`scenes/scene_0001.yaml`", prompt)
            self.assertNotIn("scenes/missing.yaml", prompt)
            self.assertTrue(entries["scenes/scene_0001.yaml"].included)
            self.assertEqual(
                entries["scenes/scene_0001.yaml"].visibility_tier,
                "must_inline",
            )
            self.assertFalse(entries["scenes/missing.yaml"].included)
            self.assertEqual(entries["scenes/missing.yaml"].note, "missing_or_not_materialized")
            self.assertEqual(
                entries["scenes/missing.yaml"].visibility_tier,
                "excluded",
            )
            for machine_path in (
                "AGENT_TASK.md",
                "TASK_CONTEXT.json",
                "_task/task.json",
                "_task/task.agent_tasks.md",
                "_task/execution_contract.json",
                "_task/capability_manifest.json",
                "_task/resource_claim.json",
                "project.yaml",
            ):
                self.assertTrue(entries[machine_path].included, machine_path)
            self.assertEqual(
                ledger.assembled_sha256,
                hashlib.sha256(sandbox.prompt_path.read_bytes()).hexdigest(),
            )
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            task_context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["agent_prompt_source_paths"], ["scenes/scene_0001.yaml"])
            self.assertEqual(manifest["context_ledger_id"], ledger.ledger_id)
            self.assertEqual(manifest["context_ledger_digest"], ledger.digest)
            self.assertEqual(
                manifest["execution_context"]["digest"],
                ledger.execution_context_digest,
            )
            self.assertEqual(
                task_context["execution_context"]["context_digest"],
                ledger.execution_context_digest,
            )
            self.assertIn(ledger.execution_context_digest, prompt)

    def test_changed_context_produces_a_new_prompt_and_ledger_digest(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = _task(root)
            first = stage_task(task, Path(runs), runtime="opencode", run_id="context-first")
            first_payload = json.loads((first.run_root / "context-ledger.json").read_text(encoding="utf-8"))

            (root / "scenes/scene_0001.yaml").write_text(
                "scene_id: scene_0001\nobjective: changed\n",
                encoding="utf-8",
            )
            second = stage_task(task, Path(runs), runtime="opencode", run_id="context-second")
            second_payload = json.loads((second.run_root / "context-ledger.json").read_text(encoding="utf-8"))

            self.assertNotEqual(first_payload["assembled_sha256"], second_payload["assembled_sha256"])
            self.assertNotEqual(first_payload["digest"], second_payload["digest"])
            first_entry = next(
                item for item in first_payload["entries"] if item["source_ref"] == "scenes/scene_0001.yaml"
            )
            second_entry = next(
                item for item in second_payload["entries"] if item["source_ref"] == "scenes/scene_0001.yaml"
            )
            self.assertNotEqual(first_entry["sha256"], second_entry["sha256"])

    def test_same_run_rematerialization_gets_a_new_ledger_identity(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = _task(root)
            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="context-rematerialized")
            first = json.loads((sandbox.run_root / "context-ledger.json").read_text(encoding="utf-8"))
            store = JobStore(Path(temporary) / "studio.sqlite3")
            store.record_context_ledger(str(root), first)

            (sandbox.control_workspace / "scenes/scene_0001.yaml").write_text(
                "scene_id: scene_0001\nobjective: command-produced-change\n",
                encoding="utf-8",
            )
            materialize_agent_workspace(task, sandbox)
            second = json.loads((sandbox.run_root / "context-ledger.json").read_text(encoding="utf-8"))
            store.record_context_ledger(str(root), second)

            self.assertNotEqual(first["assembled_sha256"], second["assembled_sha256"])
            self.assertNotEqual(first["ledger_id"], second["ledger_id"])
            self.assertNotEqual(first["digest"], second["digest"])
            self.assertEqual(len(store.list_context_ledgers(str(root))), 2)

    def test_sqlite_persists_redacted_metadata_and_session_binding(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = _task(root, source_text="api_key=test-placeholder-secret-value\nscene_id: scene_0001\n")
            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="context-persist")
            store = JobStore(Path(temporary) / "studio.sqlite3")

            self.assertIsNone(
                track_agent_session_event(
                    store,
                    project_root=str(root),
                    role="worker",
                    runtime="opencode",
                    controller_id="worker-job",
                    task_id=task.task_id,
                    route=task.route,
                    event="sandbox.context_ready",
                    data={
                        "run_root": str(sandbox.run_root),
                        "context_ledger": str(sandbox.run_root / "context-ledger.json"),
                    },
                )
            )
            persisted = store.read_context_ledger(
                json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))["context_ledger_id"]
            )
            self.assertEqual(
                persisted,
                persist_context_ledger_from_run(
                    store,
                    project_root=str(root),
                    run_root=sandbox.run_root,
                ),
            )
            with self.assertRaisesRegex(ValueError, "different project"):
                persist_context_ledger_from_run(
                    store,
                    project_root=str(root / "other-work"),
                    run_root=sandbox.run_root,
                )
            serialized = json.dumps(persisted, ensure_ascii=False)
            self.assertNotIn("test-placeholder-secret-value", serialized)
            self.assertIn("[REDACTED]", serialized)
            self.assertEqual(
                persisted["execution_context_digest"],
                json.loads(
                    sandbox.manifest_path.read_text(encoding="utf-8")
                )["execution_context"]["digest"],
            )
            self.assertIn(
                "must_inline",
                {item["visibility_tier"] for item in persisted["entries"]},
            )

            common = {
                "project_root": str(root),
                "role": "worker",
                "runtime": "opencode",
                "controller_id": "worker-job",
                "task_id": task.task_id,
                "route": task.route,
            }
            track_agent_session_event(
                store,
                **common,
                event="runner.session.created",
                data={
                    "session_id": "session-context-ledger",
                    "context_ledger_id": persisted["ledger_id"],
                    "context_ledger_digest": persisted["digest"],
                },
            )
            session = store.read_agent_session("session-context-ledger")
            self.assertEqual(session["context_ledger_id"], persisted["ledger_id"])
            self.assertEqual(session["context_ledger_digest"], persisted["digest"])

            connection = sqlite3.connect(store.path)
            try:
                rows = connection.execute(
                    "SELECT preview FROM context_ledger_entries"
                ).fetchall()
            finally:
                connection.close()
            self.assertNotIn("test-placeholder-secret-value", json.dumps(rows))


def _task(
    root: Path,
    *,
    include_missing: bool = False,
    source_text: str = "scene_id: scene_0001\n",
):
    (root / "project.yaml").write_text("title: Context Demo\n", encoding="utf-8")
    source = root / "scenes/scene_0001.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(source_text, encoding="utf-8")
    reference = root / "docs/domain-guide.md"
    reference.parent.mkdir(parents=True)
    reference.write_text("domain rule\n", encoding="utf-8")
    task_dir = root / "workflow/tasks"
    task_dir.mkdir(parents=True)
    task_markdown = task_dir / "context-demo.agent_tasks.md"
    task_markdown.write_text("# Context task\n", encoding="utf-8")
    agent_sources = ["scenes/scene_0001.yaml"]
    if include_missing:
        agent_sources.append("scenes/missing.yaml")
    payload = _enrich_task_payload(
        {
            "schema": "literary-engineering-workbench/agent-task/v1",
            "task_id": "context-demo",
            "status": "opened",
            "route": "scene-development",
            "current_state": "prose-generation",
            "task_type": "platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.generate.v1",
            "required_reading": ["docs/domain-guide.md"],
            "source_paths": ["scenes/scene_0001.yaml"],
            "agent_source_paths": agent_sources,
            "expected_outputs": ["drafts/candidates/scene_0001.md"],
            "submission_command": "lew task-submit",
            "completion_command": "lew task-complete",
            "validation_gates": [],
            "forbidden_shortcuts": [],
            "task_markdown": "workflow/tasks/context-demo.agent_tasks.md",
        }
    )
    task_json = task_dir / "context-demo.task.json"
    task_json.write_text(json.dumps(payload), encoding="utf-8")
    return load_task_package(root, task_json)


if __name__ == "__main__":
    unittest.main()
