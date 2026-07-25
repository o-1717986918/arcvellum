from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.style.mount import (
    mount_style_profile_version,
)
from literary_engineering_studio_engine.literary.style.mount_contracts import (
    StyleVersionMountConflictError,
)
from literary_engineering_studio_engine.literary.style.snapshot import (
    STYLE_MOUNT_SNAPSHOT_SCHEMA,
    active_style_evidence_paths,
    active_style_mount_snapshot,
    active_style_prompt_path,
    validate_style_mount_snapshot,
)
from literary_engineering_studio_engine.literary.style.version import (
    build_style_profile_version,
)
from tests.test_style_profile_version import _formal_reviewed_profile


class StyleMountSnapshotTests(unittest.TestCase):
    def test_snapshot_binds_exact_version_and_prompt_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            version = build_style_profile_version(root, profile, target_id=target_id)
            mount_style_profile_version(
                root,
                style_id=version.style_id,
                version_id=version.version_id,
                content_hash=version.content_hash,
            )

            snapshot = active_style_mount_snapshot(root)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            payload = snapshot.as_dict()
            self.assertEqual(payload["schema"], STYLE_MOUNT_SNAPSHOT_SCHEMA)
            self.assertEqual(payload["style_id"], version.style_id)
            self.assertEqual(payload["version_id"], version.version_id)
            self.assertEqual(payload["content_hash"], version.content_hash)
            self.assertEqual(len(payload["prompt_sha256"]), 64)
            self.assertEqual(len(payload["digest"]), 64)
            self.assertEqual(active_style_prompt_path(root), snapshot.prompt_path)
            evidence = active_style_evidence_paths(root)
            self.assertIn(root / "style" / "active_style_skill.json", evidence)
            self.assertIn(snapshot.prompt_path, evidence)
            self.assertTrue(validate_style_mount_snapshot(root, payload).passed)

            stale = dict(payload)
            stale["digest"] = "0" * 64
            self.assertEqual(
                validate_style_mount_snapshot(root, stale).status,
                "stale",
            )

    def test_tampered_version_mount_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            version = build_style_profile_version(root, profile, target_id=target_id)
            mounted = mount_style_profile_version(
                root,
                style_id=version.style_id,
                version_id=version.version_id,
                content_hash=version.content_hash,
            )
            (mounted.mount_dir / "prompt.md").write_text(
                "tampered prompt\n",
                encoding="utf-8",
            )

            with self.assertRaises(StyleVersionMountConflictError):
                active_style_mount_snapshot(root)
            with self.assertRaises(StyleVersionMountConflictError):
                active_style_prompt_path(root)
            self.assertEqual(
                validate_style_mount_snapshot(root, {}).status,
                "conflict",
            )

    def test_legacy_mount_keeps_compatibility_without_claiming_a_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt = root / "style" / "legacy" / "prompt.md"
            prompt.parent.mkdir(parents=True)
            prompt.write_text("legacy prompt\n", encoding="utf-8")
            (root / "style" / "active_style_skill.json").write_text(
                json.dumps(
                    {
                        "style_id": "legacy-style",
                        "prompt": "style/legacy/prompt.md",
                    }
                ),
                encoding="utf-8",
            )

            self.assertIsNone(active_style_mount_snapshot(root))
            self.assertEqual(active_style_prompt_path(root), prompt)
            self.assertEqual(
                validate_style_mount_snapshot(root, {}).status,
                "legacy_unverified",
            )


if __name__ == "__main__":
    unittest.main()
