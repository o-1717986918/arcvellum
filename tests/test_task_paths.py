from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.task_paths import (
    append_event,
    events_path,
    load_task,
    read_events,
    relative_path,
    render_events_markdown,
    resolve_project_path,
    task_id,
    task_json_path,
)
from literary_engineering_studio_engine.task_lifecycle import LifecycleServices, advance_workflow


class TaskPathTests(unittest.TestCase):
    def test_task_identity_paths_and_events_are_route_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identifier = task_id("scene-development", "scene_0001", "roleplay")
            self.assertEqual(identifier, "scene-development-scene-0001-roleplay")
            self.assertEqual(task_json_path(root, identifier).relative_to(root).as_posix(), f"workflow/tasks/{identifier}.task.json")
            self.assertEqual(resolve_project_path(root, "scenes/scene_0001.yaml"), root / "scenes" / "scene_0001.yaml")
            self.assertEqual(relative_path(root / "scenes" / "scene_0001.yaml", root), "scenes/scene_0001.yaml")

            append_event(root, "task_issued", identifier, {"route": "scene-development"})
            events = read_events(events_path(root))
            self.assertEqual(events[0]["event_type"], "task_issued")
            self.assertIn(identifier, render_events_markdown(events))

    def test_load_task_rejects_non_contract_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            path.write_text('{"schema":"wrong"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not an agent task registry file"):
                load_task(path)

    def test_lifecycle_refresh_delegates_route_state_without_manual_transition(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            class State:
                json_path = root / "workflow" / "dashboard.json"
                markdown_path = root / "workflow" / "dashboard.md"

            calls: list[tuple[Path, str]] = []

            def build_state(project: Path, *, route: str):
                calls.append((project, route))
                return State()

            def unused(*_args, **_kwargs):
                raise AssertionError("workflow refresh must not request task lifecycle dependencies")

            result = advance_workflow(
                root,
                route="scene_development",
                services=LifecycleServices(
                    supported_routes={"scene-development"},
                    build_workflow_state=build_state,
                    route_definition=unused,
                    workflow_payload=unused,
                    enrich_task_payload=unused,
                    render_task_markdown=unused,
                    task_contract_fingerprint=unused,
                    task_contract_revision="test",
                    block_task=unused,
                ),
            )
            self.assertEqual(calls, [(root, "scene-development")])
            self.assertEqual(result.status, "refreshed")
            self.assertEqual(read_events(events_path(root))[-1]["event_type"], "workflow_advanced")


if __name__ == "__main__":
    unittest.main()
