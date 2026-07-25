from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.assets.contracts import (
    OwnerOverrideTransaction,
    SemanticReview,
)
from literary_engineering_studio.application.assets.loader import AssetLoader
from literary_engineering_studio.application.assets.owner_transactions import (
    AssetVersionConflictError,
    OwnerTransactionService,
)
from literary_engineering_studio.application.assets.registry import AssetViewRegistry
from literary_engineering_studio.application.assets.revisions import AssetRevisionService
from literary_engineering_studio.application.assets.validation import validate_asset_content
from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.projections.archive.service import ArchiveProjectionService
from literary_engineering_studio_engine.context_broker import (
    context_trace_status,
    write_context_trace,
)
from literary_engineering_studio_engine.workflow_state import build_workflow_state


class ArchiveAssetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
        (self.root / "characters").mkdir()
        (self.root / "characters" / "lin.yaml").write_text(
            "character_id: lin\nname: 林澈\nimportance: major\n",
            encoding="utf-8",
        )
        (self.root / "scenes").mkdir()
        (self.root / "scenes" / "scene_0001.yaml").write_text(
            "scene_id: scene_0001\nchapter_id: chapter_0001\nparticipant_refs: [lin]\n",
            encoding="utf-8",
        )
        self.registry = AssetViewRegistry.default()
        self.loader = AssetLoader(self.registry)

    def tearDown(self):
        self.temporary.cleanup()

    def test_registry_and_projection_expose_stable_ids_without_absolute_paths(self):
        projection = ArchiveProjectionService(self.registry, self.loader)
        tree = projection.tree(self.root)
        character = next(item for item in tree["items"] if item["asset_id"] == "character:lin")
        self.assertEqual(character["asset_type"], "character")
        self.assertEqual(character["title"], "林澈")
        self.assertNotIn(str(self.root), str(tree))

        detail = projection.detail(self.root, "character:lin")
        self.assertEqual(detail["asset"]["revision"], self.loader.load(self.root, "character:lin").revision)
        self.assertIn("character_id: lin", detail["asset"]["content"])
        self.assertNotIn(str(self.root), str(detail))

    def test_loader_rejects_unknown_ids_and_symlink_escape(self):
        with self.assertRaises(ValueError):
            self.loader.load(self.root, "../project.yaml")
        with self.assertRaises(ValueError):
            self.loader.load(self.root, "character:../../project")

        outside = Path(self.temporary.name) / "outside.yaml"
        outside.write_text("character_id: escaped\nname: 越界\n", encoding="utf-8")
        link = self.root / "characters" / "escaped.yaml"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation is unavailable on this Windows environment")
        with self.assertRaises(ValueError):
            self.loader.load(self.root, "character:escaped")

    def test_registry_accepts_unicode_stable_ids_without_weakening_path_safety(self):
        unicode_asset = self.root / "characters" / "scene-0001-叙述者.yaml"
        unicode_asset.write_text(
            "character_id: scene-0001-叙述者\nname: 叙述者\nimportance: secondary\n",
            encoding="utf-8",
        )

        tree = ArchiveProjectionService(self.registry, self.loader).tree(self.root)

        self.assertIn(
            "character:scene-0001-叙述者",
            {item["asset_id"] for item in tree["items"]},
        )
        for unsafe_id in (
            "character:../叙述者",
            "character:角色/叙述者",
            "character:角色\\叙述者",
            "character:角色:叙述者",
            "character: 叙述者",
        ):
            with self.subTest(unsafe_id=unsafe_id):
                with self.assertRaises(ValueError):
                    self.registry.parse_asset_id(unsafe_id)

    def test_validation_keeps_structural_rules_even_when_owner_waives_semantic_review(self):
        definition = self.registry.definition("character")
        result = validate_asset_content(
            self.root,
            definition,
            "lin",
            "character_id: other\nname: 林澈\n",
        )
        self.assertFalse(result.valid)
        self.assertIn("asset_id_mismatch", {issue.code for issue in result.issues})

        result = validate_asset_content(self.root, definition, "lin", "character_id: lin\0\n")
        self.assertFalse(result.valid)
        self.assertIn("nul_byte", {issue.code for issue in result.issues})

    def test_owner_override_is_atomic_and_rejects_stale_base_revision(self):
        service = OwnerTransactionService(self.registry, self.loader)
        before = self.loader.load(self.root, "character:lin")
        transaction = OwnerOverrideTransaction.create(
            asset_id="character:lin",
            asset_type="character",
            base_revision=before.revision,
            content="character_id: lin\nname: 林澈\nimportance: secondary\n",
            semantic_review=SemanticReview.WAIVED,
            reason="作者决定降低角色在第一卷的叙事权重。",
        )

        preview = service.preview(self.root, transaction)
        self.assertTrue(preview["validation"]["valid"])
        self.assertEqual(before.content, (self.root / "characters" / "lin.yaml").read_text(encoding="utf-8"))

        receipt = service.commit(self.root, transaction)
        self.assertEqual(receipt["authority"], "owner")
        self.assertNotEqual(receipt["base_revision"], receipt["new_revision"])
        self.assertIn("importance: secondary", (self.root / "characters" / "lin.yaml").read_text(encoding="utf-8"))
        self.assertTrue((self.root / receipt["receipt_path"]).is_file())
        self.assertTrue((self.root / receipt["before_snapshot"]).is_file())
        self.assertTrue((self.root / receipt["after_snapshot"]).is_file())

        with self.assertRaises(AssetVersionConflictError):
            service.commit(self.root, transaction)
        self.assertIn("importance: secondary", (self.root / "characters" / "lin.yaml").read_text(encoding="utf-8"))

    def test_required_semantic_review_cannot_be_silently_committed(self):
        service = OwnerTransactionService(self.registry, self.loader)
        before = self.loader.load(self.root, "character:lin")
        transaction = OwnerOverrideTransaction.create(
            asset_id="character:lin",
            asset_type="character",
            base_revision=before.revision,
            content="character_id: lin\nname: 林澈\nimportance: secondary\n",
            semantic_review=SemanticReview.REQUIRED,
            reason="等待正式语义审查。",
        )
        with self.assertRaisesRegex(ValueError, "semantic review"):
            service.commit(self.root, transaction)

    def test_revision_index_rebuilds_from_project_receipts(self):
        before = self.loader.load(self.root, "character:lin")
        transaction = OwnerOverrideTransaction.create(
            asset_id="character:lin",
            asset_type="character",
            base_revision=before.revision,
            content="character_id: lin\nname: 林澈\nimportance: secondary\n",
            semantic_review=SemanticReview.WAIVED,
            reason="作者调整角色权重以验证历史重建。",
        )
        receipt = OwnerTransactionService(self.registry, self.loader).commit(self.root, transaction)
        index = JobStore(Path(self.temporary.name) / "history.sqlite3")
        revisions = AssetRevisionService(index)

        history = revisions.history(self.root, "character:lin")

        self.assertEqual(history["synchronization"]["indexed"], 1)
        self.assertEqual(history["transactions"][0]["transaction_id"], receipt["transaction_id"])
        restored, _ = revisions.snapshot_content(self.root, "character:lin", before.revision)
        self.assertEqual(restored, before.content)

    def test_index_failure_keeps_committed_project_truth_and_marks_rebuild(self):
        class FailingRevisionService:
            def index_receipt(self, _root, _receipt):
                raise RuntimeError("index unavailable")

        before = self.loader.load(self.root, "character:lin")
        transaction = OwnerOverrideTransaction.create(
            asset_id="character:lin",
            asset_type="character",
            base_revision=before.revision,
            content="character_id: lin\nname: 林澈\nimportance: secondary\n",
            semantic_review=SemanticReview.WAIVED,
            reason="作者提交不能被派生索引故障伪装成失败。",
        )
        service = OwnerTransactionService(
            self.registry,
            self.loader,
            FailingRevisionService(),
        )

        receipt = service.commit(self.root, transaction)

        self.assertIn("importance: secondary", self.loader.load(self.root, "character:lin").content)
        self.assertEqual(receipt["history_index"]["status"], "rebuild-required")
        persisted = __import__("json").loads(
            (self.root / receipt["receipt_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(persisted["history_index"]["status"], "rebuild-required")

    def test_owner_override_uses_engine_context_trace_for_formal_stale_propagation(self):
        context = self.root / "memory" / "context_packets" / "scene_0001.md"
        context.parent.mkdir(parents=True)
        context.write_text("已加载角色林澈。\n", encoding="utf-8")
        character = self.root / "characters" / "lin.yaml"
        write_context_trace(
            context.with_suffix(".trace.json"),
            {
                "scene_id": "scene_0001",
                "context_packet": "memory/context_packets/scene_0001.md",
                "loaded_files": [
                    "project.yaml",
                    "scenes/scene_0001.yaml",
                    "characters/lin.yaml",
                ],
                "loaded_sources": [
                    {
                        "relative_path": relative,
                        "sha256": __import__("hashlib").sha256((self.root / relative).read_bytes()).hexdigest(),
                    }
                    for relative in (
                        "project.yaml",
                        "scenes/scene_0001.yaml",
                        "characters/lin.yaml",
                    )
                ],
                "missing_required_context": [],
            },
        )
        self.assertTrue(context_trace_status(self.root, "scene_0001", context).passed)
        service = OwnerTransactionService(self.registry, self.loader)
        before = self.loader.load(self.root, "character:lin")
        transaction = OwnerOverrideTransaction.create(
            asset_id="character:lin",
            asset_type="character",
            base_revision=before.revision,
            content="character_id: lin\nname: 林澈\nimportance: secondary\n",
            semantic_review=SemanticReview.WAIVED,
            reason="作者调整人物在本章中的叙事权重。",
        )

        receipt = service.commit(self.root, transaction)

        self.assertEqual(context_trace_status(self.root, "scene_0001", context).status, "stale")
        propagation = receipt["stale_propagation"]
        self.assertEqual(propagation["status"], "propagated")
        self.assertEqual(propagation["scene_ids"], ["scene_0001"])
        self.assertEqual(propagation["mechanism"], "engine-context-trace-sha256")
        state_path = self.root / "workflow" / "archive-stale-state.json"
        build_workflow_state(
            self.root,
            route="scene-development",
            scene="scenes/scene_0001.yaml",
            output=self.root / "workflow" / "archive-stale-state.md",
            json_output=state_path,
        )
        state = __import__("json").loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["scenes"][0]["current_step"], "context-trace")


if __name__ == "__main__":
    unittest.main()
