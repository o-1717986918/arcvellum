from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.worker_preparation import prepare_worker_task


class _Observer:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []
        self.reset_count = 0

    def reset_context_ledger(self) -> None:
        self.reset_count += 1

    def emit(self, event: str, payload: dict[str, object]) -> None:
        self.events.append((event, payload))


class WorkerPreparationTests(unittest.TestCase):
    def test_route_ready_stops_before_sandbox_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("schema: test\n", encoding="utf-8")
            observer = _Observer()

            task, sandbox, terminal = prepare_worker_task(
                project,
                route="scene-development",
                runtime_id="pi",
                task_id="",
                scene="",
                config={"worker": {}},
                bridge=object(),  # type: ignore[arg-type]
                observer=observer,  # type: ignore[arg-type]
                select_task=lambda *_args, **_kwargs: (None, "创作路线已完成"),
                prepared_context_cache=None,
            )

        self.assertIsNone(task)
        self.assertIsNone(sandbox)
        self.assertEqual(terminal.status, "route_ready")
        self.assertEqual(terminal.message, "创作路线已完成")
        self.assertEqual(observer.reset_count, 1)
        self.assertEqual(observer.events[0][0], "task.selecting")

    def test_human_gate_stops_before_sandbox_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("schema: test\n", encoding="utf-8")
            task_package = TaskPackage(
                project,
                project / "task.json",
                project / "task.md",
                {
                    "task_id": "decision-001",
                    "route": "scene-development",
                    "current_state": "human-choice",
                    "execution_policy": "agent-required",
                    "agent_role": "creative-director",
                    "human_gate": {
                        "required": True,
                        "reasons": ["human-choice"],
                        "source": "test",
                    },
                    "runtime_capabilities_required": [],
                    "output_contracts": [],
                },
            )
            observer = _Observer()

            task, sandbox, terminal = prepare_worker_task(
                project,
                route="scene-development",
                runtime_id="pi",
                task_id="decision-001",
                scene="scene_0001",
                config={"worker": {}},
                bridge=object(),  # type: ignore[arg-type]
                observer=observer,  # type: ignore[arg-type]
                select_task=lambda *_args, **_kwargs: (task_package, ""),
                prepared_context_cache=None,
            )

        self.assertIs(task, task_package)
        self.assertIsNone(sandbox)
        self.assertEqual(terminal.status, "waiting_human")
        self.assertIn("human-choice", terminal.message)
        self.assertEqual(
            [name for name, _payload in observer.events],
            ["task.selecting", "task.opened", "human.required"],
        )


if __name__ == "__main__":
    unittest.main()
