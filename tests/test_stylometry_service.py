import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.style.stylometry_contracts import CorpusTextSource
from literary_engineering_studio.application.style.stylometry_service import StylometryService
from literary_engineering_studio.infrastructure.stylometry_analysis import LabStylometryAnalysis
from literary_engineering_studio.persistence.stylometry import FileStylometryRepository
from stylometric_prompt_lab.integration import analyze_text, analyze_corpus


class StylometryServiceTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 测试作品", encoding="utf-8")
        self.repository = FileStylometryRepository(Path(self.folder.name) / "data")
        self.service = StylometryService(LabStylometryAnalysis(), self.repository)

    def _profile(self):
        return self.service.analyze(self.root, (
            CorpusTextSource("train-one", "work-one", "风从河面吹来。她把门推开，看看炉中的火。" * 30),
            CorpusTextSource("holdout-one", "work-two", "他循着山路走过去。石头上落着水，远处传来鸟叫。" * 30,
                             split="holdout")), "河与山")

    def test_single_text_matches_lab_and_does_not_create_profile(self):
        text = "炉火响了一声。她抬起头，望见窗上的雪。"
        result = self.service.analyze(self.root, (CorpusTextSource("text-one", "work-one", text),), "片段")
        self.assertEqual(result["result"], analyze_text(text))
        self.assertEqual(self.service.workbench(self.root)["profiles"], [])

    def test_windows_line_endings_match_native_lab_files(self):
        sources = (CorpusTextSource("train-one", "work-one", "窗子开着。\r\n河水在响。\r\n\r\n她提起碗。" * 30),
            CorpusTextSource("holdout-one", "work-two", "门外有脚步。\r\n门房抬头。\r\n\r\n他等她问。" * 30, split="holdout"))
        native = Path(self.folder.name) / "native"
        native.mkdir()
        rows = []
        for index, source in enumerate(sources):
            name = f"source-{index}.txt"
            (native / name).write_bytes(source.text.encode("utf-8"))
            rows.append({"source_id": source.source_id, "work_id": source.work_id, "path": name,
                "split": source.split, "topic": source.topic, "genre": source.genre})
        manifest = native / "manifest.json"
        manifest.write_text(json.dumps({"schema": "corpus-manifest/v1", "label": "换行", "sources": rows}), encoding="utf-8")
        expected = analyze_corpus(manifest)["profile"]
        actual = json.loads(LabStylometryAnalysis().analyze(sources, "换行").json_text)["profile"]
        self.assertEqual(actual, expected)

    def test_profile_version_mount_and_measure_are_independent_from_formal_archives(self):
        profile = self._profile()
        parameters = self.service.parameters(self.root, profile["profile_id"])
        self.assertGreater(len(parameters["metrics"]), 13)
        controls = json.dumps(parameters["controls"], ensure_ascii=False)
        version = self.service.save_version(self.root, profile["profile_id"], controls, title="舒缓")
        mounted = self.service.mount(self.root, version["version_id"], enabled=True,
            combine="append", usage="guide", expected_revision=0)
        self.assertEqual(mounted["fragment_text"], version["fragment_text"])
        self.assertEqual(self.repository.snapshot(self.root).revision, 1)
        report = self.service.measure(self.root, "河水结冰了。她站在门口。", version_id=version["version_id"])
        self.assertTrue(report["targets"])
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["project.yaml"])

    def test_free_edit_new_version_stale_mount_and_project_isolation(self):
        profile = self._profile()
        controls = json.dumps(profile["controls"], ensure_ascii=False)
        version = self.service.save_version(self.root, profile["profile_id"], controls,
            title="自定", fragment_override="将句子的呼吸交给眼前的风。")
        self.assertTrue(version["user_edited"])
        self.service.mount(self.root, version["version_id"], enabled=True,
                           combine="replace", usage="observe", expected_revision=0)
        with self.assertRaisesRegex(ValueError, "已更新"):
            self.service.mount(self.root, "", enabled=False, combine="append", usage="guide", expected_revision=0)
        other = Path(self.folder.name) / "other"
        other.mkdir()
        (other / "project.yaml").write_text("title: other")
        self.assertFalse(self.service.workbench(other)["mount"]["enabled"])
        with self.assertRaises(ValueError):
            self.service.version(other, version["version_id"])
        with self.assertRaises(ValueError):
            self.service.version(self.root, "../../project")

    def test_tampered_version_is_rejected_and_all_off_compiles(self):
        profile = self._profile()
        for row in profile["controls"]["targets"]:
            row["enabled"] = False
        version = self.service.save_version(self.root, profile["profile_id"], json.dumps(profile["controls"]), title="观察")
        self.assertEqual(json.loads(version["compiled_json"])["targets"], [])
        path = self.repository._path(self.root, "versions", version["version_id"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["payload"]["fragment_text"] = "篡改"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "摘要"):
            self.service.version(self.root, version["version_id"])


if __name__ == "__main__":
    unittest.main()
