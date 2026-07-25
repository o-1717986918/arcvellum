from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.style.mount_service import (
    StyleMountApplicationService,
    StyleMountChoiceError,
)
from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import record_choice
from literary_engineering_studio_engine.literary.style.version import (
    build_style_profile_version,
)
from literary_engineering_studio_engine.project_interaction import (
    build_current_human_choices,
)
from tests.test_style_profile_version import _formal_reviewed_profile


class StyleMountApplicationServiceTests(unittest.TestCase):
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
                    "/style-lab/mount",
                    json={
                        "project_root": str(root),
                        "style_id": version.style_id,
                        "version_id": version.version_id,
                        "content_hash": version.content_hash,
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
