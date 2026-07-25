from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.style.task_service import StyleTaskService
from literary_engineering_studio.application.style.transactions import StyleAuthoringService
from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_bridge import task_command_parameters
from literary_engineering_studio.core_read_models import install_core_import_path
from literary_engineering_studio.worker import AgentWorker
from literary_engineering_studio_engine.init_project import InitOptions, init_work_project
from literary_engineering_studio_engine.literary.style.session import (
    StyleSessionSourceError,
    StyleSourceSelection,
    prepare_style_engineering_session,
)
from literary_engineering_studio_engine.style_engineering_route import build_task_payload
from literary_engineering_studio_engine.workflow_state import _style_engineering_state


class StyleTaskServiceTests(unittest.TestCase):
    def test_session_is_atomic_rights_bound_and_holdout_isolated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, library, authoring, training, holdout = _fixture(Path(temporary))
            session = prepare_style_engineering_session(
                root,
                library,
                author_id="classic-author",
                profile_id="measured-prose",
                display_name="Measured prose",
                training_sources=[StyleSourceSelection(**training)],
                holdout_sources=[StyleSourceSelection(**holdout)],
            )

            manifest = json.loads(session.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], "arcvellum/style-engineering-session/v1")
            self.assertEqual(manifest["training_sources"][0]["identity"], "training-work/" + training["source_id"])
            self.assertEqual(manifest["holdout_sources"][0]["identity"], "holdout-work/" + holdout["source_id"])
            self.assertTrue((session.profile_dir / manifest["training_sources"][0]["path"]).is_file())
            self.assertTrue((session.profile_dir / manifest["holdout_sources"][0]["path"]).is_file())
            self.assertFalse(
                str(manifest["holdout_sources"][0]["path"]).startswith("corpus/")
            )
            self.assertIn("rights", manifest["training_sources"][0])

            repeated = prepare_style_engineering_session(
                root,
                library,
                author_id="classic-author",
                profile_id="measured-prose",
                display_name="Measured prose",
                training_sources=[StyleSourceSelection(**training)],
                holdout_sources=[StyleSourceSelection(**holdout)],
            )
            self.assertFalse(repeated.created)
            self.assertEqual(repeated.request_digest, session.request_digest)

            with self.assertRaisesRegex(StyleSessionSourceError, "disjoint"):
                prepare_style_engineering_session(
                    root,
                    library,
                    author_id="classic-author",
                    profile_id="invalid-overlap",
                    display_name="Invalid overlap",
                    training_sources=[StyleSourceSelection(**training)],
                    holdout_sources=[StyleSourceSelection(**training)],
                )

    def test_formal_route_compiles_new_session_without_unresolved_placeholders(self):
        config = default_config()
        install_core_import_path(config)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, library, _, training, holdout = _fixture(base)
            session = prepare_style_engineering_session(
                root,
                library,
                author_id="classic-author",
                profile_id="formal-route",
                display_name="Formal route",
                training_sources=[StyleSourceSelection(**training)],
                holdout_sources=[StyleSourceSelection(**holdout)],
            )
            state = _style_engineering_state(root, session.profile_dir)
            self.assertEqual(state["current_step"], "style-profile")
            task = build_task_payload(root, "style-engineering", state)
            self.assertEqual(task_command_parameters(str(task["command"])), ())
            self.assertIn("/corpus", str(task["command"]).replace("\\", "/"))
            self.assertNotIn("evaluation_inputs/holdout", str(task["command"]).replace("\\", "/"))
            self.assertIn(
                session.manifest_path.relative_to(root).as_posix(),
                task["source_paths"],
            )
            self.assertTrue(
                any("evaluation_inputs/holdout" in path for path in task["source_paths"])
            )

            config["worker"]["runs_root"] = str(base / "runs")
            with patch(
                "literary_engineering_studio.worker.build_runtime",
                side_effect=AssertionError("runtime must not run for deterministic compilation"),
            ):
                result = AgentWorker(config).run_once(
                    root,
                    route="style-engineering",
                    runtime_id="opencode",
                    scene=session.profile_dir.relative_to(root).as_posix(),
                )
            self.assertEqual(result.status, "complete")
            self.assertEqual(result.runtime, "deterministic-engine")
            self.assertTrue((session.profile_dir / "style-profile.md").is_file())
            self.assertTrue((session.profile_dir / "style_metrics.json").is_file())
            self.assertTrue((session.profile_dir / "corpus_manifest.yaml").is_file())
            self.assertTrue((session.profile_dir / "evaluation_cases/blind_review.md").is_file())
            next_state = _style_engineering_state(root, session.profile_dir)
            self.assertEqual(next_state["current_step"], "style-prompt-task-file")

    def test_application_service_returns_worker_job_instead_of_pending_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, library, _, training, holdout = _fixture(Path(temporary))
            requests: list[dict[str, str]] = []

            def launch(request: dict[str, str]) -> dict[str, object]:
                requests.append(request)
                return {"ok": True, "job_id": "job-style-1", "status": "queued"}

            result = StyleTaskService(launch).compile(
                root,
                library,
                author_id="classic-author",
                profile_id="studio-task",
                display_name="Studio task",
                training_sources=[training],
                holdout_sources=[holdout],
                runtime="opencode",
            )
            self.assertEqual(result["job"]["job_id"], "job-style-1")
            self.assertEqual(result["job"]["status"], "queued")
            self.assertNotIn("pending_platform_agent", json.dumps(result))
            self.assertEqual(requests[0]["route"], "style-engineering")
            self.assertEqual(requests[0]["scene"], "style/atelier/classic-author/studio-task")
            self.assertTrue(requests[0]["idempotency_key"].startswith("style-compile:"))


def _fixture(
    base: Path,
) -> tuple[Path, Path, StyleAuthoringService, dict[str, str], dict[str, str]]:
    root = base / "work"
    init_work_project(InitOptions(target=root, title="Style Session Verification", target_length=30000))
    library = base / "style-library"
    authoring = StyleAuthoringService()
    authoring.create_author(
        library,
        author_id="classic-author",
        name="Classic Author",
        rights_mode="public-domain",
        rights_declaration="Public-domain source evidence for verification.",
    )
    selections: list[dict[str, str]] = []
    for work_id, title, body in (
        (
            "training-work",
            "Training Work",
            "旧城的钟声从河面慢慢传来。守门人没有回头，只把钥匙放回原处。" * 60,
        ),
        (
            "holdout-work",
            "Holdout Work",
            "雨停以后，石阶上留下细窄的水纹。来客看了一会儿，才敲第二次门。" * 60,
        ),
    ):
        authoring.create_work(
            library,
            author_id="classic-author",
            work_id=work_id,
            title=title,
        )
        receipt = authoring.import_source(
            library,
            author_id="classic-author",
            work_id=work_id,
            filename=f"{work_id}.txt",
            media_type="text/plain",
            content=body,
            rights_mode="public-domain",
            rights_declaration="Public-domain source evidence for verification.",
        )
        selections.append(
            {
                "work_id": work_id,
                "source_id": str(receipt["subject"]["source_id"]),
            }
        )
    return root, library, authoring, selections[0], selections[1]


if __name__ == "__main__":
    unittest.main()
