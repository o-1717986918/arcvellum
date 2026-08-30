import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config
from literary_engineering_studio.narrative_projection_v3 import (
    build_narrative_projection_v3,
)
from literary_engineering_studio_engine.project_library import (
    build_narrative_evidence,
    build_project_library,
)


class NarrativeEvidenceProjectionTests(unittest.TestCase):
    def test_complete_evidence_preserves_scenes_beyond_the_library_display_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_project(root, 300)
            library = build_project_library(root)
            evidence = build_narrative_evidence(root)
            projection = build_narrative_projection_v3(
                {},
                root,
                level="scene",
                focus="scene_0300",
                grammar="spine",
                dashboard_payload={},
                library_payload=evidence,
            )

        self.assertEqual(len(library["sections"]["scenes"]), 250)
        self.assertEqual(library["sections"]["scenes"][0]["title"], "场景 1")
        self.assertEqual(len(evidence["sections"]["scenes"]), 300)
        self.assertEqual(projection["summary"]["scene_count"], 300)
        self.assertIn("scene:scene_0300", {item["node_id"] for item in projection["nodes"]})

    def test_api_v3_uses_narrative_evidence_instead_of_the_display_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_root = Path(temporary)
            project = data_root / "project"
            _write_project(project, 300)
            config = default_config()
            config["application"]["data_root"] = str(data_root)
            config["application"]["database_path"] = str(data_root / "studio.sqlite3")
            config["application"]["projects_root"] = str(data_root / "projects")
            config["worker"]["runs_root"] = str(data_root / "runs")
            config["agent_runners"]["opencode"]["data_root"] = str(data_root)
            with patch(
                "literary_engineering_studio.projections.api_read_models.build_narrative_evidence",
                side_effect=lambda _config, root: {"ok": True, **build_narrative_evidence(root)},
            ) as evidence_builder:
                with TestClient(create_app(config)) as client:
                    response = client.get(
                        "/narrative/projection/v3",
                        params={
                            "project_root": str(project),
                            "level": "scene",
                            "focus": "scene_0300",
                            "grammar": "spine",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["scene_count"], 300)
        evidence_builder.assert_called()


def _write_project(root: Path, scene_count: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("project.yaml").write_text(
        "project:\n  title: Narrative Evidence Fixture\n  type: novel\n  target_length: 1200000\n",
        encoding="utf-8",
    )
    scenes = root / "scenes"
    scenes.mkdir()
    for index in range(1, scene_count + 1):
        chapter = (index - 1) // 10 + 1
        scenes.joinpath(f"scene_{index:04d}.yaml").write_text(
            "\n".join(
                [
                    f"scene_id: scene_{index:04d}",
                    f"chapter_id: chapter_{chapter:04d}",
                    f"title: 场景 {index}",
                    "status: planned",
                    "word_count_target: 1400",
                    f"timeline_order: {index}",
                    "participants: []",
                    "participant_refs: []",
                    "",
                ]
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
