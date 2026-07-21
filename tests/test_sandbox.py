import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.sandbox import (
    apply_expected_outputs,
    capture_core_managed_outputs,
    import_expected_outputs,
    inspect_expected_outputs,
    rollback_expected_outputs,
    restore_core_managed_outputs,
    stage_task,
)
from literary_engineering_studio_engine.task_registry import _enrich_task_payload


class SandboxTests(unittest.TestCase):
    def _task(self, root: Path):
        (root / "project.yaml").write_text("title: Demo\n", encoding="utf-8")
        source = root / "scenes" / "scene_0001.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("scene_id: scene_0001\n", encoding="utf-8")
        task_dir = root / "workflow" / "tasks"
        task_dir.mkdir(parents=True)
        markdown = task_dir / "demo.agent_tasks.md"
        markdown.write_text("# Demo task\n", encoding="utf-8")
        payload = {
            "schema": "literary-engineering-workbench/agent-task/v1",
            "task_id": "demo",
            "status": "opened",
            "route": "scene-development",
            "current_state": "prose-generation",
            "task_type": "platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.generate.v1",
            "required_reading": [],
            "source_paths": ["scenes/scene_0001.yaml"],
            "expected_outputs": ["drafts/candidates/scene_0001.md"],
            "submission_command": "lew task-submit",
            "completion_command": "lew task-complete",
            "validation_gates": [],
            "forbidden_shortcuts": [],
            "task_markdown": "workflow/tasks/demo.agent_tasks.md",
        }
        task_json = task_dir / "demo.task.json"
        task_json.write_text(json.dumps(payload), encoding="utf-8")
        return load_task_package(root, task_json)

    def test_imports_only_expected_output(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-good")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("正文。\n", encoding="utf-8")
            imported = import_expected_outputs(task, sandbox)
            self.assertEqual(imported, ("drafts/candidates/scene_0001.md",))
            self.assertEqual((task.project_root / imported[0]).read_text(encoding="utf-8"), "正文。\n")

    def test_rejects_source_modification(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-bad")
            source = sandbox.workspace / "scenes" / "scene_0001.yaml"
            source.write_text("scene_id: changed\n", encoding="utf-8")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("正文。\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                import_expected_outputs(task, sandbox)

    def test_preview_precedes_writeback_and_detects_stale_target(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            target = task.project_root / "drafts" / "candidates" / "scene_0001.md"
            target.parent.mkdir(parents=True)
            target.write_text("旧正文。\n", encoding="utf-8")
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-preview")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.write_text("新正文。\n", encoding="utf-8")
            preview = inspect_expected_outputs(task, sandbox)
            self.assertEqual(preview.policy, "preview-required")
            self.assertIn("-旧正文。", str(preview.changes[0]["diff"]))
            self.assertEqual(target.read_text(encoding="utf-8"), "旧正文。\n")
            target.write_text("项目后来被修改。\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                apply_expected_outputs(task, sandbox, preview)

    def test_rollback_restores_preexisting_output(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            target = task.project_root / "drafts" / "candidates" / "scene_0001.md"
            target.parent.mkdir(parents=True)
            target.write_text("旧正文。\n", encoding="utf-8")
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-rollback")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.write_text("新正文。\n", encoding="utf-8")
            preview = inspect_expected_outputs(task, sandbox)
            imported = apply_expected_outputs(task, sandbox, preview)
            rollback_expected_outputs(task, sandbox, imported)
            self.assertEqual(target.read_text(encoding="utf-8"), "旧正文。\n")

    def test_exact_prompt_omits_host_manuals_but_keeps_domain_references(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["required_reading"] = [
                "SKILL.md",
                "references/workflows.md",
                "docs/modules/domain-guide.md",
            ]
            payload.pop("prompt_asset", None)
            payload = _enrich_task_payload(payload)
            task.task_json_path.write_text(json.dumps(payload), encoding="utf-8")
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            (root / "references").mkdir()
            (root / "references/workflows.md").write_text("large workflow map", encoding="utf-8")
            (root / "docs/modules").mkdir(parents=True)
            (root / "docs/modules/domain-guide.md").write_text("domain constraints", encoding="utf-8")

            compact_task = load_task_package(root, task.task_json_path)
            sandbox = stage_task(compact_task, Path(runs), runtime="opencode", run_id="run-compact")
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            context = json.loads((sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reference_paths"], ["docs/modules/domain-guide.md"])
            self.assertEqual(context["reference_paths"], ["docs/modules/domain-guide.md"])
            self.assertFalse((sandbox.workspace / "SKILL.md").exists())
            self.assertFalse((sandbox.workspace / "references/workflows.md").exists())
            self.assertTrue((sandbox.workspace / "docs/modules/domain-guide.md").is_file())

    def test_restores_cli_managed_outputs_after_agent_mutation(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["expected_outputs"] = [
                "drafts/candidates/scene_0001.md",
                "drafts/candidates/scene_0001.prompt.json",
            ]
            payload["core_managed_outputs"] = ["drafts/candidates/scene_0001.prompt.json"]
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            task = load_task_package(root, task.task_json_path)
            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="run-protected")
            protected = sandbox.workspace / "drafts" / "candidates" / "scene_0001.prompt.json"
            protected.parent.mkdir(parents=True, exist_ok=True)
            protected.write_text('{"source":"cli"}\n', encoding="utf-8")

            self.assertEqual(capture_core_managed_outputs(task, sandbox), ("drafts/candidates/scene_0001.prompt.json",))
            protected.write_text('{"source":"agent"}\n', encoding="utf-8")

            self.assertEqual(restore_core_managed_outputs(sandbox), ("drafts/candidates/scene_0001.prompt.json",))
            self.assertEqual(protected.read_text(encoding="utf-8"), '{"source":"cli"}\n')


if __name__ == "__main__":
    unittest.main()
