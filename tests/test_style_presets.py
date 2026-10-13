from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from literary_engineering_studio.application.style.presets import StylePresetService
from literary_engineering_studio.application.style.stylometry_contracts import (
    StylePresetV1, StylePresetCollectionV1, StylometryProfile, StylometryVersion, CreatorStyleSnapshot,
)
from literary_engineering_studio.persistence.stylometry import FileStylometryRepository


class StylePresetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/"work"; self.root.mkdir(); (self.root/"project.yaml").write_text("title: 作品",encoding="utf-8")
        self.repo = FileStylometryRepository(Path(self.temp.name)/"data"); self.service = StylePresetService(self.repo)
        profile = str(uuid4()); self.version = str(uuid4())
        self.repo.save_profile(self.root, StylometryProfile(profile,"语料","now","{}","[]"))
        compiled=json.dumps({"compiler_version":"creator-1.1","profile_sha256":"profile","controls_sha256":"controls"})
        self.repo.save_version(self.root, StylometryVersion(self.version,profile,"世界叙述","世界经验","now","{}","",compiled,
            "让讲述者展开世界的时间与风俗。",sha256("让讲述者展开世界的时间与风俗。".encode()).hexdigest(),False))

    def test_versioned_catalog_selects_exact_measured_version_and_keeps_history(self):
        row=StylePresetV1("world-narration","世界叙述","让读者进入森林",("summary",),("R24",),self.version)
        self.service.save(self.root,StylePresetCollectionV1(0,True,row.preset_id,(row,)),0)
        first=self.service.snapshot(self.root,row.preset_id)
        self.assertTrue(first.enabled); self.assertEqual(first.version_id,self.version)
        self.service.save(self.root,StylePresetCollectionV1(0,True,row.preset_id,(replace(row,title="世界与风俗"),)),1)
        self.assertEqual(first.revision,1); self.assertEqual(self.service.catalog(self.root)["revision"],2)
        self.assertTrue((self.repo._directory(self.root)/"preset-history/1.json").is_file())
        with self.assertRaisesRegex(ValueError,"已更新"):
            self.service.save(self.root,StylePresetCollectionV1(0,True,row.preset_id,(row,)),1)

    def test_unknown_versions_and_duplicate_presets_do_not_mount(self):
        row=StylePresetV1("world-narration","世界","",(),(),str(uuid4()))
        with self.assertRaisesRegex(ValueError,"不存在"):
            self.service.save(self.root,StylePresetCollectionV1(0,True,row.preset_id,(row,)),0)
        with self.assertRaisesRegex(ValueError,"唯一"):
            self.service.save(self.root,StylePresetCollectionV1(0,True,row.preset_id,(row,row)),0)

    def test_existing_single_mount_is_a_compatible_default_preset(self):
        version=self.repo.version(self.root,self.version)
        self.repo.set_mount(self.root,CreatorStyleSnapshot(True,0,self.version,version.profile_id,"append","guide",
            version.fragment_text,version.content_sha256,"creator-1.1","profile","controls"),0)
        catalog=self.service.catalog(self.root)
        self.assertEqual(catalog["default_preset_id"],"default")
        self.assertEqual(catalog["presets"][0]["snapshot"]["version_id"],self.version)
