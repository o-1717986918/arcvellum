from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.release_fingerprint import release_candidate_fingerprint
import literary_engineering_studio_engine.task_registry as task_registry
from literary_engineering_studio_engine.workflow_state import _export_package_step, _release_approval_step


def _write_export(root: Path, chapter_id: str = "chapter_0001") -> Path:
    folder = root / "exports" / chapter_id
    folder.mkdir(parents=True)
    outputs = {}
    for key, name, body in (
        ("novel", "novel.md", "# 第一章\n\n潮声抵达窗下。\n"),
        ("screenplay", "screenplay.md", "第一场：潮线。\n"),
        ("video_prompt_pack", "video.md", "镜头沿潮线推进。\n"),
    ):
        path = folder / name
        path.write_text(body, encoding="utf-8")
        outputs[key] = path.relative_to(root).as_posix()
    manifest = folder / "export_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/export-package/v0.1",
                "chapter_id": chapter_id,
                "generated_at": "volatile",
                "include_blocked": False,
                "exported_scenes": ["scene_0001"],
                "skipped_scenes": [],
                "outputs": outputs,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest


class ReleaseFingerprintTests(unittest.TestCase):
    def test_formal_export_state_rejects_legacy_markdown_only_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_export(root)
            self.assertEqual(_export_package_step(root, "chapter_0001", manifest)["status"], "blocked")
            self.assertTrue(task_registry._export_package_gate_errors(root, "chapter_0001"))

    def test_release_approval_becomes_stale_when_delivery_text_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_export(root)
            fingerprint = release_candidate_fingerprint(root, "chapter_0001")
            record_workflow_approval(root, "release-chapter_0001", "approve", subject_sha256=fingerprint)

            self.assertEqual(task_registry._release_approval_gate_errors(root, "chapter_0001"), [])
            self.assertEqual(_release_approval_step(root, "release-chapter_0001", manifest)["status"], "pass")

            (root / "exports" / "chapter_0001" / "novel.md").write_text("# 第一章\n\n潮声退去了。\n", encoding="utf-8")
            self.assertTrue(task_registry._release_approval_gate_errors(root, "chapter_0001"))
            self.assertEqual(_release_approval_step(root, "release-chapter_0001", manifest)["status"], "missing")

    def test_manifest_timestamp_does_not_invalidate_release_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_export(root)
            before = release_candidate_fingerprint(root, "chapter_0001")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["generated_at"] = "another volatile timestamp"
            manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(release_candidate_fingerprint(root, "chapter_0001"), before)


if __name__ == "__main__":
    unittest.main()
