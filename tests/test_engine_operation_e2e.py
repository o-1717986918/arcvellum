from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_bridge import CoreBridge
from literary_engineering_studio_engine.public.tasking import EngineOperation


class EngineOperationE2ETests(unittest.TestCase):
    def test_two_scene_context_preparation_uses_structured_operations(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "双场景 连续验收"
            _write(project / "project.yaml", "project:\n  title: 双场景验收\n")
            _write(
                project / "scenes/scene_0001.yaml",
                "scene_id: scene_0001\nchapter_id: chapter_0001\n"
                "scene_goal: 找到失踪者留下的第一条线索\n",
            )
            _write(
                project / "scenes/scene_0002.yaml",
                "scene_id: scene_0002\nchapter_id: chapter_0001\n"
                "scene_goal: 验证线索并承担错误判断的代价\n",
            )
            bridge = CoreBridge(default_config())

            for scene_id in ("scene_0001", "scene_0002"):
                operation = EngineOperation(
                    "arcvellum.engine/context.v1",
                    {
                        "argv": [
                            "context",
                            "<project>",
                            "--scene",
                            f"scenes/{scene_id}.yaml",
                        ]
                    },
                )
                result = bridge.execute_task_operation(operation, project)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(
                    (project / f"memory/context_packets/{scene_id}.md").is_file()
                )
                self.assertTrue(
                    (project / f"memory/context_packets/{scene_id}.trace.json").is_file()
                )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
