from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.literary.style.lab import active_project_style
from literary_engineering_studio_engine.literary.style.mount import (
    StyleVersionMountConflictError,
    mount_style_profile_version,
)
from literary_engineering_studio_engine.literary.style.version import (
    build_style_profile_version,
)
from literary_engineering_studio_engine.literary.style.version_inspection import (
    inspect_style_version_directory,
)
from tests.test_style_profile_version import _formal_reviewed_profile


class StyleVersionMountTests(unittest.TestCase):
    def test_exact_version_mount_is_atomic_audited_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )

            mounted = mount_style_profile_version(
                root,
                style_id=version.style_id,
                version_id=version.version_id,
                content_hash=version.content_hash,
            )

            self.assertTrue(mounted.created)
            self.assertTrue(mounted.receipt_path and mounted.receipt_path.is_file())
            manifest = active_project_style(root)
            self.assertEqual(manifest["schema"], "arcvellum/style-profile-version-mount/v1")
            self.assertEqual(manifest["style_id"], version.style_id)
            self.assertEqual(manifest["version_id"], version.version_id)
            self.assertEqual(manifest["content_hash"], version.content_hash)
            self.assertEqual(manifest["integrity"]["status"], "pass")
            self.assertTrue(manifest["prompt_exists"])
            mounted_manifest, errors = inspect_style_version_directory(
                mounted.mount_dir
            )
            self.assertEqual(errors, ())
            self.assertEqual(mounted_manifest["content_hash"], version.content_hash)
            project_yaml = (root / "project.yaml").read_text(encoding="utf-8")
            self.assertIn(f'active_style_version: "{version.version_id}"', project_yaml)
            self.assertIn(f'content_hash: "{version.content_hash}"', project_yaml)

            repeated = mount_style_profile_version(
                root,
                style_id=version.style_id,
                version_id=version.version_id,
                content_hash=version.content_hash,
            )
            self.assertFalse(repeated.created)
            self.assertIsNone(repeated.receipt_path)
            self.assertEqual(
                len(list((root / "style" / "mount_receipts").glob("*.json"))),
                1,
            )

    def test_hash_mismatch_and_tampered_version_never_activate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )

            with self.assertRaisesRegex(
                StyleVersionMountConflictError,
                "content hash",
            ):
                mount_style_profile_version(
                    root,
                    style_id=version.style_id,
                    version_id=version.version_id,
                    content_hash="0" * 64,
                )
            self.assertFalse((root / "style" / "active_style_skill.json").exists())

            (version.version_dir / "prompt.md").write_text(
                "tampered\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                StyleVersionMountConflictError,
                "integrity",
            ):
                mount_style_profile_version(
                    root,
                    style_id=version.style_id,
                    version_id=version.version_id,
                    content_hash=version.content_hash,
                )
            self.assertFalse((root / "style" / "active_style_skill.json").exists())

    def test_metadata_failure_removes_new_mount_and_restores_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )
            original_project = (root / "project.yaml").read_text(encoding="utf-8")

            with patch(
                "literary_engineering_studio_engine.literary.style.mount.atomic_write_batch",
                side_effect=OSError("simulated metadata failure"),
            ):
                with self.assertRaisesRegex(OSError, "metadata failure"):
                    mount_style_profile_version(
                        root,
                        style_id=version.style_id,
                        version_id=version.version_id,
                        content_hash=version.content_hash,
                    )

            mount_dir = (
                root
                / "style"
                / "mounted"
                / version.style_id
                / version.version_id
            )
            self.assertFalse(mount_dir.exists())
            self.assertFalse((root / "style" / "active_style_skill.json").exists())
            self.assertEqual(
                (root / "project.yaml").read_text(encoding="utf-8"),
                original_project,
            )

    def test_active_projection_blocks_a_tampered_mounted_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )
            mounted = mount_style_profile_version(
                root,
                style_id=version.style_id,
                version_id=version.version_id,
                content_hash=version.content_hash,
            )
            (mounted.mount_dir / "prompt.md").write_text(
                "tampered mounted prompt\n",
                encoding="utf-8",
            )

            active = active_project_style(root)

            self.assertEqual(active["integrity"]["status"], "conflict")
            self.assertFalse(active["prompt_exists"])
            self.assertEqual(active["prompt_path"], "")


if __name__ == "__main__":
    unittest.main()
