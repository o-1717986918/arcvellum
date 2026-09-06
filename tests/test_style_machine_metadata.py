from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.style_metadata import (
    canonicalize_style_machine_metadata,
)
from literary_engineering_studio.sandbox import SandboxManifest


class StyleMachineMetadataTests(unittest.TestCase):
    def test_markdown_holdout_is_bound_as_the_evaluation_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            profile = "style/atelier/arcvellum/clear-plain-prose"
            holdout_rel = f"{profile}/evaluation_inputs/holdout/reference.md"
            candidate_rel = f"{profile}/evaluation_results/formal/platform_agent_candidate.md"
            manifest_rel = f"{profile}/evaluation_results/formal/platform_agent_candidate.prompt.json"
            for relative, content in (
                (f"{profile}/style_prompt.md", "朴素、准确、流畅。"),
                (holdout_rel, "这是一份隔离的参考片段。"),
                ("project.yaml", "title: 测试作品\n"),
                (candidate_rel, "候选文本。"),
                (manifest_rel, "{}\n"),
            ):
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "style-engineering-default-style-eval-agent-task",
                    "route": "style-engineering",
                    "current_state": "style-eval-agent-task",
                    "task_type": "platform-agent-evaluation",
                    "profile_dir": profile,
                    "source_paths": [
                        f"{profile}/style_prompt.md",
                        holdout_rel,
                        "project.yaml",
                    ],
                    "expected_outputs": [candidate_rel, manifest_rel],
                },
            )
            sandbox = SandboxManifest(
                run_id="style-reference-test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_style_machine_metadata(task, sandbox)

            manifest = json.loads((workspace / manifest_rel).read_text(encoding="utf-8"))
            self.assertEqual(manifest["reference"], holdout_rel)
            self.assertEqual(
                manifest["reference_sha256"],
                hashlib.sha256((workspace / holdout_rel).read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
