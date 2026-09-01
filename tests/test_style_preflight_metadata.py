from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.style_metadata import (
    canonicalize_style_machine_metadata,
)
from literary_engineering_studio.sandbox import SandboxManifest


class StylePreflightMetadataTests(unittest.TestCase):
    def test_style_eval_does_not_rewrite_read_only_prompt_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            profile_rel = "style/atelier/author/profile"
            prompt_metadata = workspace / profile_rel / "style_prompt.agent.json"
            prompt_metadata.parent.mkdir(parents=True)
            prompt_metadata.write_text(
                json.dumps({"writer_session_id": "original-writer"}),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "style-eval-regression",
                    "route": "style-engineering",
                    "current_state": "style-eval-agent-task",
                    "profile_dir": profile_rel,
                    "source_paths": [f"{profile_rel}/style_prompt.agent.json"],
                    "expected_outputs": [
                        f"{profile_rel}/evaluation_results/formal/platform_agent_candidate.md",
                        f"{profile_rel}/evaluation_results/formal/platform_agent_candidate.prompt.json",
                    ],
                },
            )
            sandbox = SandboxManifest(
                run_id="style-eval-regression",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            before = prompt_metadata.read_text(encoding="utf-8")
            changes = canonicalize_style_machine_metadata(task, sandbox)

            self.assertEqual(changes, [])
            self.assertEqual(prompt_metadata.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
