import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.scene.context.broker import CONTEXT_TRACE_SCHEMA
from literary_engineering_studio_engine.routes.scene.support import _context_source_paths


class SceneContextTraceDependencyTests(unittest.TestCase):
    def test_context_sources_include_exact_retrieval_files_recorded_in_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary = root / "scenes" / "scene_0001.yaml"
            retrieved = root / "scenes" / "scene_0002.yaml"
            primary.parent.mkdir(parents=True)
            primary.write_text("scene_id: scene_0001\n", encoding="utf-8")
            retrieved.write_text("scene_id: scene_0002\n", encoding="utf-8")
            (root / "project.yaml").write_text("title: Trace fixture\n", encoding="utf-8")

            trace = root / "memory" / "context_packets" / "scene_0001.trace.json"
            trace.parent.mkdir(parents=True)
            trace.write_text(
                json.dumps(
                    {
                        "schema": CONTEXT_TRACE_SCHEMA,
                        "scene_id": "scene_0001",
                        "context_packet": "memory/context_packets/scene_0001.md",
                        "loaded_files": ["scenes/scene_0001.yaml", "scenes/scene_0002.yaml"],
                        "loaded_sources": [
                            {
                                "relative_path": "scenes/scene_0002.yaml",
                                "sha256": hashlib.sha256(retrieved.read_bytes()).hexdigest(),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            sources = _context_source_paths(root, "scenes/scene_0001.yaml")

            self.assertIn("scenes/scene_0001.yaml", sources)
            self.assertIn("scenes/scene_0002.yaml", sources)


if __name__ == "__main__":
    unittest.main()
