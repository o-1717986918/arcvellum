from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.style.mount_service import (
    StyleMountApplicationService,
    StyleMountChoiceError,
    StyleMountPreviewError,
)
from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import record_choice
from literary_engineering_studio_engine.literary.style.version import (
    build_style_profile_version,
)
from literary_engineering_studio_engine.literary.style.snapshot import (
    active_style_mount_snapshot_payload,
)
from literary_engineering_studio_engine.project_interaction import (
    build_current_human_choices,
)
from tests.test_style_profile_version import _formal_reviewed_profile


class StyleMountApplicationServiceTests(unittest.TestCase):
    def test_preview_compares_exact_version_and_reports_unpromoted_stale_impact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            first = build_style_profile_version(root, profile, target_id=target_id)
            review = (
                profile
                / "evaluation_results"
                / "formal"
                / "style_semantic_review.json"
            )
            review_payload = json.loads(review.read_text(encoding="utf-8"))
            review_payload["summary"] = (
                str(review_payload.get("summary") or "")
                + " 新版本增加了对段落余波的约束。"
            )
            review.write_text(
                json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            second = build_style_profile_version(root, profile, target_id=target_id)
            service = StyleMountApplicationService()
            service.mount(
                root,
                style_id=first.style_id,
                version_id=first.version_id,
                content_hash=first.content_hash,
            )
            candidates = root / "drafts" / "candidates"
            candidates.mkdir(parents=True, exist_ok=True)
            (candidates / "scene_0007-platform-agent.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/scene-candidate-manifest/v1",
                        "scene_id": "scene_0007",
                        "style_mount_snapshot": active_style_mount_snapshot_payload(root),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            preview = service.preview(
                root,
                style_id=second.style_id,
                version_id=second.version_id,
                content_hash=second.content_hash,
            )

            self.assertEqual(preview["status"], "confirmation-required")
            self.assertEqual(preview["current"]["version_id"], first.version_id)
            self.assertEqual(preview["target"]["version_id"], second.version_id)
            self.assertEqual(preview["impact"]["affected_scene_count"], 1)
            self.assertEqual(
                preview["impact"]["entries"][0]["scene_id"],
                "scene_0007",
            )
            self.assertEqual(preview["impact"]["historical_prose"], "preserved")
            with self.assertRaises(StyleMountPreviewError):
                service.mount_confirmed(
                    root,
                    style_id=second.style_id,
                    version_id=second.version_id,
                    content_hash=second.content_hash,
                    preview_revision="",
                )

            mounted = service.mount_confirmed(
                root,
                style_id=second.style_id,
                version_id=second.version_id,
                content_hash=second.content_hash,
                preview_revision=preview["revision"],
            )

            self.assertEqual(mounted["status"], "mounted")
            self.assertEqual(mounted["preview_revision"], preview["revision"])
            self.assertEqual(mounted["impact"]["affected_scene_count"], 1)

    def test_exact_choice_materializes_one_versioned_mount(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(
                Path(temporary)
            )
            version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )
            choices = build_current_human_choices(
                root,
                route="style-engineering",
            )["choices"]
            choice = next(
                item
                for item in choices
                if item.get("decision_type") == "style_mount"
            )
            option = choice["options"][0]
            self.assertEqual(option["style_id"], version.style_id)
            self.assertEqual(option["version_id"], version.version_id)
            self.assertEqual(option["content_hash"], version.content_hash)

            result = record_choice(
                default_config(),
                root,
                {
                    **choice,
                    "selected": option["id"],
                    "rationale": "使用通过正式审查的明确版本。",
                    "actor": "arcvellum-user",
                },
                style_mount_service=StyleMountApplicationService(),
            )

            self.assertTrue(result["consumed"])
            self.assertEqual(result["effect"]["kind"], "style-mounted")
            self.assertEqual(
                result["style_mount"]["version_id"],
                version.version_id,
            )
            status = StyleMountApplicationService().status(root)
            self.assertEqual(status["status"], "active")
            self.assertEqual(
                status["active_mount"]["content_hash"],
                version.content_hash,
            )
            self.assertNotIn(str(root), str(status))

    def test_choice_rejects_an_undeclared_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.mkdir(exist_ok=True)
            (root / "project.yaml").write_text(
                "title: Choice\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                StyleMountChoiceError,
                "not one of",
            ):
                StyleMountApplicationService().mount_choice(
                    root,
                    {
                        "selected": "v1-00000000000000000000",
                        "options": [],
                    },
                )

    def test_api_accepts_only_exact_identity_and_maps_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, profile, target_id = _formal_reviewed_profile(base)
            version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )
            config = _config(base)
            with TestClient(create_app(config)) as client:
                rejected_path = client.post(
                    "/style-lab/mount",
                    json={
                        "project_root": str(root),
                        "style_library_root": str(root / "style"),
                        "style_id": version.style_id,
                        "version_id": version.version_id,
                        "content_hash": version.content_hash,
                    },
                )
                self.assertEqual(rejected_path.status_code, 422)

                conflict = client.post(
                    "/style-lab/mount",
                    json={
                        "project_root": str(root),
                        "style_id": version.style_id,
                        "version_id": version.version_id,
                        "content_hash": "0" * 64,
                    },
                )
                self.assertEqual(conflict.status_code, 409)
                self.assertEqual(
                    conflict.json()["detail"]["code"],
                    "style_version_mount_conflict",
                )

                mounted = client.post(
                    "/style-lab/mount-preview",
                    json={
                        "project_root": str(root),
                        "style_id": version.style_id,
                        "version_id": version.version_id,
                        "content_hash": version.content_hash,
                    },
                )
                self.assertEqual(mounted.status_code, 200)
                preview_revision = mounted.json()["revision"]

                unconfirmed = client.post(
                    "/style-lab/mount",
                    json={
                        "project_root": str(root),
                        "style_id": version.style_id,
                        "version_id": version.version_id,
                        "content_hash": version.content_hash,
                    },
                )
                self.assertEqual(unconfirmed.status_code, 409)
                self.assertEqual(
                    unconfirmed.json()["detail"]["code"],
                    "style_mount_preview_stale",
                )

                mounted = client.post(
                    "/style-lab/mount",
                    json={
                        "project_root": str(root),
                        "style_id": version.style_id,
                        "version_id": version.version_id,
                        "content_hash": version.content_hash,
                        "preview_revision": preview_revision,
                    },
                )
                self.assertEqual(mounted.status_code, 200)
                payload = mounted.json()
                self.assertEqual(payload["status"], "mounted")
                self.assertEqual(payload["version_id"], version.version_id)
                self.assertTrue(payload["receipt"])

                status = client.get(
                    "/style-lab/mounts",
                    params={"project_root": str(root)},
                )
                self.assertEqual(status.status_code, 200)
                self.assertEqual(status.json()["status"], "active")
                self.assertNotIn(str(root), status.text)


def _config(root: Path) -> dict[str, object]:
    config = default_config()
    config["application"]["data_root"] = str(root / "data")
    config["application"]["database_path"] = str(
        root / "data" / "studio.sqlite3"
    )
    config["worker"]["runs_root"] = str(root / "runs")
    return config


if __name__ == "__main__":
    unittest.main()
