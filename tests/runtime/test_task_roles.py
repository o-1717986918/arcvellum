from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.sandbox import SandboxManifest
from literary_engineering_studio.runtime.task_roles import runtime_role_for_task
from literary_engineering_studio.runtime.worker import AgentWorker
from literary_engineering_studio.runtimes.base import RuntimeResult


def _task(
    root: Path,
    *,
    task_type: str,
    agent_role: str,
    agent_output: str = "",
    agent_output_kind: str = "agent-authored",
) -> TaskPackage:
    capabilities = ["read-task-sources"]
    output_contracts = []
    expected_outputs = []
    if agent_output:
        capabilities.append("write-expected-outputs")
        output_contracts.append(
            {
                "path": agent_output,
                "kind": agent_output_kind,
                "writeback_policy": "preview-required",
            }
        )
        expected_outputs.append(agent_output)
    payload = {
        "schema": "literary-engineering-workbench/agent-task/v1",
        "task_id": f"task-{task_type}",
        "route": "scene-development",
        "current_state": "candidate-generation-provenance",
        "task_type": task_type,
        "execution_policy": "agent-required",
        "agent_role": agent_role,
        "human_gate": {"required": False, "reasons": [], "source": "test"},
        "runtime_capabilities_required": capabilities,
        "output_contracts": output_contracts,
        "expected_outputs": expected_outputs,
    }
    task_json = root / "task.json"
    task_md = root / "task.md"
    task_json.write_text(json.dumps(payload), encoding="utf-8")
    task_md.write_text("# task\n", encoding="utf-8")
    return TaskPackage(root, task_json, task_md, payload)


class TaskRuntimeRoleTests(unittest.TestCase):
    def test_read_only_reviewer_and_planner_roles_are_isolated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(
                runtime_role_for_task(
                    _task(
                        root,
                        task_type="main-platform-agent-prose",
                        agent_role="main-creative-agent",
                    )
                ),
                "worker",
            )
            self.assertEqual(
                runtime_role_for_task(
                    _task(
                        root,
                        task_type="platform-agent-review",
                        agent_role="main-review-agent",
                    )
                ),
                "reviewer",
            )
            self.assertEqual(
                runtime_role_for_task(
                    _task(
                        root,
                        task_type="platform-agent",
                        agent_role="orchestration-planner",
                    )
                ),
                "planner",
            )

    def test_file_authoring_reviewer_uses_write_capable_worker_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(
                Path(temporary),
                task_type="platform-agent-review",
                agent_role="main-review-agent",
                agent_output="reviews/word_budget/word_budget_review.md",
            )

            self.assertEqual(runtime_role_for_task(task), "worker")

    def test_semantic_file_authoring_reviewer_uses_write_capable_worker_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(
                Path(temporary),
                task_type="platform-agent-review",
                agent_role="main-review-agent",
                agent_output="drafts/compositions/scene_0001_composition_review.json",
                agent_output_kind="composition-review",
            )

            self.assertEqual(runtime_role_for_task(task), "worker")

    def test_file_authoring_planner_uses_write_capable_worker_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(
                Path(temporary),
                task_type="platform-agent",
                agent_role="orchestration-planner",
                agent_output="plans/creative_execution_plan.json",
            )

            self.assertEqual(runtime_role_for_task(task), "worker")

    def test_inconsistent_write_contract_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(
                Path(temporary),
                task_type="platform-agent-review",
                agent_role="main-review-agent",
                agent_output="reviews/example.md",
            )
            task.payload["runtime_capabilities_required"] = ["read-task-sources"]

            with self.assertRaisesRegex(ValueError, "write-expected-outputs"):
                runtime_role_for_task(task)

    def test_unknown_role_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "unsupported formal Agent role"):
                runtime_role_for_task(
                    _task(
                        Path(temporary),
                        task_type="platform-agent",
                        agent_role="invented-role",
                    )
                )

    def test_worker_passes_write_capable_role_for_file_authoring_reviewer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(
                root,
                task_type="platform-agent-review",
                agent_role="main-review-agent",
                agent_output="reviews/example.md",
            )
            run_root = root / "run"
            workspace = run_root / "workspace"
            workspace.mkdir(parents=True)
            sandbox = SandboxManifest(
                run_id="run-reviewer",
                run_root=run_root,
                workspace=workspace,
                prompt_path=workspace / "AGENT_TASK.md",
                manifest_path=run_root / "run.json",
                baseline_path=run_root / "agent-baseline.json",
                expected_outputs=(),
            )
            runtime_result = RuntimeResult(
                runtime="host-agent",
                status="completed",
                returncode=0,
                command=(),
                output_path=None,
                message="review complete",
            )

            with (
                patch(
                    "literary_engineering_studio.runtime.worker.build_runtime"
                ) as build_runtime,
                patch(
                    "literary_engineering_studio.runtime.worker.update_run_manifest"
                ),
            ):
                build_runtime.return_value.execute.return_value = runtime_result
                result = AgentWorker(default_config())._execute_agent_runtime(
                    task,
                    sandbox,
                    "host-agent",
                )

            self.assertEqual(result, runtime_result)
            self.assertEqual(build_runtime.call_args.kwargs["role"], "worker")


if __name__ == "__main__":
    unittest.main()
