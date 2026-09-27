from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from literary_engineering_studio.application.assets.creation import OwnerCreationService
from literary_engineering_studio.application.assets.loader import AssetLoader
from literary_engineering_studio.application.assets.owner_transactions import AssetVersionConflictError, OwnerTransactionService
from literary_engineering_studio.application.assets.recycle_bin import RecycleBinService
from literary_engineering_studio.application.assets.registry import AssetViewRegistry
from literary_engineering_studio.application.assets.structured_editor import StructuredAssetService, StructuredFieldError
from literary_engineering_studio.application.style.owner_directive import read_owner_style_directive, write_owner_style_directive
from literary_engineering_studio.project_agent.archive_actions import archive_change_action, archive_read_action
from literary_engineering_studio.project_agent.asset_reconcile_actions import asset_reconcile_action
from literary_engineering_studio.project_agent.contracts import ProjectAgentActionDependencies, ProjectAgentDependencies, ProjectAgentToolCall
from literary_engineering_studio.project_agent.read_models import dependencies_from_read_models
from literary_engineering_studio.project_agent.tools import ProjectAgentToolDispatcher, available_action_tools, available_read_tools
from literary_engineering_studio.projections.archive.service import ArchiveProjectionService
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_source_evidence import scene_source_evidence


class ProjectAgentOwnerPermissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "project.yaml").write_text("title: 试验作品\n", encoding="utf-8")
        (self.root / "characters").mkdir()
        (self.root / "characters/lin.yaml").write_text(
            "character_id: lin\nname: 林澈\nimportance: major\n", encoding="utf-8",
        )
        registry = AssetViewRegistry.default()
        loader = AssetLoader(registry)
        archive = SimpleNamespace(
            registry=registry, loader=loader,
            projections=ArchiveProjectionService(registry, loader, recycle_bin=RecycleBinService(registry, loader)),
            transactions=OwnerTransactionService(registry, loader),
            creation=OwnerCreationService(registry, loader),
            recycle_bin=RecycleBinService(registry, loader),
            structured_editor=StructuredAssetService(registry, loader),
        )
        self.read = archive_read_action(archive)
        self.change = archive_change_action(archive)

    def tearDown(self):
        self.temporary.cleanup()

    def test_existing_asset_edit_uses_exact_revision_and_owner_receipt(self):
        detail = self.read(self.root, {"section": "detail", "asset_id": "character:lin"})
        self.assertIn("character_id: lin", detail["content"])
        revision = detail["asset"]["revision"]
        changed = self.change(self.root, {
            "operation": "replace", "asset_id": "character:lin", "base_revision": revision,
            "content": "character_id: lin\nname: 林澈\nimportance: secondary\n",
            "reason": "作者调整人物在这一章的叙事分量。",
        })
        self.assertEqual(changed["receipt"]["authority"], "owner")
        self.assertTrue((self.root / changed["receipt"]["receipt_path"]).is_file())
        with self.assertRaises(AssetVersionConflictError):
            self.change(self.root, {
                "operation": "replace", "asset_id": "character:lin", "base_revision": revision,
                "content": "character_id: lin\nname: 林澈\nimportance: minor\n",
                "reason": "作者再次调整人物在这一章的叙事分量。",
            })

    def test_create_archive_restore_use_existing_services(self):
        created = self.change(self.root, {
            "operation": "create", "asset_type": "character", "local_id": "mei",
            "content": "character_id: mei\nname: 梅青\nimportance: minor\n",
            "reason": "作者增加推动支线的角色。",
        })
        self.assertEqual(created["asset_id"], "character:mei")
        detail = self.read(self.root, {"section": "detail", "asset_id": "character:mei"})
        archived = self.change(self.root, {
            "operation": "archive", "asset_id": "character:mei",
            "base_revision": detail["asset"]["revision"], "reason": "作者撤下尚未使用的角色。",
        })
        entries = self.read(self.root, {"section": "recycle_bin"})["items"]
        entry = next(item for item in entries if item["asset_id"] == "character:mei")
        restored = self.change(self.root, {
            "operation": "restore", "asset_id": "character:mei",
            "entry_id": entry["entry_id"], "reason": "作者决定恢复该角色的后续作用。",
        })
        self.assertEqual(archived["operation"], "archive")
        self.assertEqual(restored["operation"], "restore")

    def test_registered_fields_use_the_same_structured_editor_and_owner_receipt(self):
        (self.root / "characters/lin.yaml").write_text(
            "character_id: lin\nname: 林澈\nimportance: major\ncustom_note: 保留此行\n",
            encoding="utf-8",
        )
        fields = self.read(self.root, {"section": "fields", "asset_id": "character:lin"})
        self.assertEqual(fields["asset_id"], "character:lin")
        self.assertIn("background_story", {item["name"] for item in fields["fields"]})
        revised = self.change(self.root, {
            "operation": "fields", "asset_id": "character:lin",
            "base_revision": fields["source_revision"],
            "fields": {"background_story": {"formative_event": "少年时失去故乡"}},
            "reason": "补足人物童年的经历及其当下影响。",
        })
        self.assertEqual(revised["receipt"]["authority"], "owner")
        detail = self.read(self.root, {"section": "detail", "asset_id": "character:lin"})
        self.assertIn("custom_note: 保留此行", detail["content"])
        self.assertIn("少年时失去故乡", detail["content"])
        with self.assertRaises(AssetVersionConflictError):
            self.change(self.root, {
                "operation": "fields", "asset_id": "character:lin",
                "base_revision": fields["source_revision"],
                "fields": {"role": "主角"}, "reason": "调整人物在故事中的角色位置。",
            })
        with self.assertRaises(StructuredFieldError):
            self.change(self.root, {
                "operation": "fields", "asset_id": "character:lin",
                "base_revision": detail["asset"]["revision"],
                "fields": {"not_registered": "不应写入"},
                "reason": "检查未登记字段不能绕开编辑器。",
            })

    def test_world_rule_fields_are_available_without_a_special_agent_path(self):
        (self.root / "canon").mkdir()
        (self.root / "canon/world_rules.yaml").write_text(
            "world_name: 雾都\nrules: []\n", encoding="utf-8",
        )
        fields = self.read(self.root, {"section": "fields", "asset_id": "world-rule:world_rules"})
        changed = self.change(self.root, {
            "operation": "fields", "asset_id": "world-rule:world_rules",
            "base_revision": fields["source_revision"],
            "fields": {"rules": [{"name": "潮汐之门", "effect": "每夜只开启一次"}]},
            "reason": "明确世界机制及其时间限制。",
        })
        self.assertEqual(changed["receipt"]["asset_type"], "world-rule")

    def test_planned_asset_reconcile_is_a_registered_project_action(self):
        calls = []
        action = asset_reconcile_action(
            lambda root, **values: calls.append((root, values)) or {"characters_created": 1},
        )
        result = action(self.root, {
            "asset_id": "character:lin", "reason": "补齐规划中缺失的人物档案。",
        })
        self.assertEqual(result["characters_created"], 1)
        self.assertEqual(calls[0][1], {"target_asset_id": "character:lin"})
        actions = ProjectAgentActionDependencies(lambda _root, _args: {}, lambda _root, _args: {},
                                                 reconcile_assets=action)
        self.assertIn("project_assets_reconcile", available_action_tools(actions))
        dispatcher = ProjectAgentToolDispatcher(
            self.root, ProjectAgentDependencies(lambda _root, _args: {}, lambda _root, _args: {},
                                                lambda _root, _args: {}),
            enabled=("project_assets_reconcile",), actions=actions,
        )
        self.assertEqual(dispatcher(ProjectAgentToolCall(
            "reconcile-1", "turn", "project_assets_reconcile",
            {"asset_id": "character:lin", "reason": "补齐规划中缺失的人物档案。"},
        ))["operation"], "assets_reconcile")

    def test_owner_style_revision_and_detach(self):
        first = read_owner_style_directive(self.root)
        result = write_owner_style_directive(
            self.root, content="让情绪随人物语言与空间展开。",
            base_revision=first["revision"], reason="作者调整作品的表达方向。",
        )
        self.assertTrue(result["directive"]["active"])
        runtime = object.__new__(PiSceneTransactionRuntime)
        runtime._project_root = self.root
        self.assertIn("让情绪随人物语言与空间展开", runtime._style_reference({"status": "no-active-style"}))
        source = scene_source_evidence(
            self.root, SimpleNamespace(scene_id="scene_0001", source_refs=()),
            purpose="create", indexed_style=False,
        )
        self.assertIn("让情绪随人物语言与空间展开", source)
        with self.assertRaisesRegex(ValueError, "changed"):
            write_owner_style_directive(
                self.root, content="另一版", base_revision=first["revision"], reason="作者再次调整表达方向。",
            )
        detached = write_owner_style_directive(
            self.root, content="", base_revision=result["directive"]["revision"],
            reason="作者撤下临时文风指令。",
        )
        self.assertFalse(detached["directive"]["active"])

    def test_new_tools_are_available_through_agent_dispatch(self):
        noop = lambda _root, _arguments: {}
        reads = ProjectAgentDependencies(
            noop, noop, noop, archive_read=self.read,
            owner_style_read=lambda root, _arguments: read_owner_style_directive(root),
        )
        actions = ProjectAgentActionDependencies(
            noop, noop, archive_change=self.change,
            owner_style_write=lambda root, arguments: write_owner_style_directive(
                root, content=arguments["content"], base_revision=arguments["base_revision"],
                reason=arguments["reason"],
            ),
        )
        self.assertIn("project_archive_read", available_read_tools(reads))
        self.assertIn("project_archive_change", available_action_tools(actions))
        dispatcher = ProjectAgentToolDispatcher(
            self.root, reads, actions=actions,
            enabled=("project_archive_read", "project_owner_style_read", "project_owner_style_write"),
        )
        result = dispatcher(ProjectAgentToolCall(
            "r1", "turn", "project_archive_read", {"section": "detail", "asset_id": "character:lin"},
        ))
        self.assertEqual(result["asset"]["asset_id"], "character:lin")
        before = dispatcher(ProjectAgentToolCall("r2", "turn", "project_owner_style_read", {}))
        written = dispatcher(ProjectAgentToolCall(
            "r3", "turn", "project_owner_style_write",
            {"base_revision": before["revision"], "content": "情绪随关系起伏。", "reason": "作者强调人物情绪的文学表达。"},
        ))
        self.assertTrue(written["directive"]["active"])

    def test_style_catalog_exposes_exact_mount_identity(self):
        reads = dependencies_from_read_models(
            SimpleNamespace(),
            style_versions=lambda _root: {
                "schema": "arcvellum/style-version-catalog/v1", "revision": "r1",
                "versions": [{"style_id": "lush", "version_id": "v1-abc", "content_hash": "abc",
                              "state": "mountable", "internal_path": "should-not-leak"}],
                "active_mount": {}, "issues": [],
            },
            style_version_detail=lambda _root, style_id, version_id: {
                "style_id": style_id, "version_id": version_id,
                "integrity": {"status": "pass"},
            },
        )
        result = reads.style_versions(self.root, {})
        self.assertEqual(result["versions"][0]["style_id"], "lush")
        self.assertNotIn("internal_path", result["versions"][0])
        self.assertIn("project_style_versions", available_read_tools(reads))
        detail = reads.style_versions(self.root, {"style_id": "lush", "version_id": "v1-abc"})
        self.assertEqual(detail["integrity"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
