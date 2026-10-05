"""Actual Lab export targets round-trip through project storage and creator mounts."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.style.stylometry_contracts import CorpusTextSource
from literary_engineering_studio.application.style.stylometry_service import StylometryService
from literary_engineering_studio.infrastructure.stylometry_analysis import LabStylometryAnalysis
from literary_engineering_studio.persistence.stylometry import FileStylometryRepository
from stylometric_prompt_lab.dependency_metrics import seal_parse
from stylometric_prompt_lab.io import digest


class StylometryImportTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 导入", encoding="utf-8")
        self.repository = FileStylometryRepository(Path(self.folder.name) / "data")
        self.service = StylometryService(LabStylometryAnalysis(), self.repository)
        self.profile = self.service.analyze(self.root, (
            CorpusTextSource("train", "work-one", '她推开窗，看看河上的船。老人问：“有信吗？”她说：“我再等等。”' * 30),
            CorpusTextSource("hold", "work-two", "他站在门口。炉中的火响了一下，风吹过山。" * 30, split="holdout")), "河与山")

    def legacy(self):
        groups = {"axes": {}, "secondary_axes": {}, "lexical_targets": []}
        for row in self.profile["controls"]["targets"]:
            band = {key: row[key] for key in ("min", "max", "unit")}
            if row["id"].startswith("word:"):
                groups["lexical_targets"].append({"word": row["id"][5:], **band})
            else:
                group = "axes" if row["enabled"] else "secondary_axes"
                groups[group][row["id"]] = band
        return {"schema": "style-controls/v1", "profile_sha256": self.profile["controls"]["profile_sha256"], **groups}

    def ingest(self, parameters, **kwargs):
        return self.service.import_parameters(self.root, profile_json=self.profile["profile_json"],
            parameters_json=json.dumps(parameters, ensure_ascii=False), **kwargs)

    def test_all_legacy_primary_secondary_and_lexical_targets_mount_exactly(self):
        controls = self.legacy()
        controls["axes"]["sentence_length_han"].update(min=9.125, max=24.875)
        imported = self.ingest(controls, title="拖动参数", intent="围绕迟疑展开声音。")
        rows = {row["id"]: row for row in imported["controls"]["targets"]}
        self.assertEqual(len(rows), len(self.profile["controls"]["targets"]))
        self.assertTrue(all(row["enabled"] for row in rows.values()))
        self.assertEqual(rows["sentence_length_han"]["min"], 9.125)
        saved = self.service.save_version(self.root, imported["profile_id"], json.dumps(imported["controls"]),
                                         title="拖动参数", intent=imported["intent"])
        mount = self.service.mount(self.root, saved["version_id"], enabled=True, combine="append", usage="guide", expected_revision=0)
        self.assertIn("9.125–24.875", mount["fragment_text"])
        self.assertIn("围绕迟疑", mount["fragment_text"])
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["project.yaml"])
        raw = json.loads(self.repository.profile(self.root, imported["profile_id"]).document_json)
        self.assertEqual(json.loads(raw["import_source"]["parameters_json"]), controls)

    def test_parameter_card_keeps_selected_axes_and_requires_valid_hash(self):
        legacy = self.legacy()
        card = {"schema": "style-parameter-card/v1", "profile_sha256": legacy["profile_sha256"],
            "title": "慢声", "intent": "让停顿承接犹疑。", "axes": [
                {"id": key, "target": band} for key, band in legacy["axes"].items()],
            "secondary_axes": [{"id": "word_mattr_50", "target": legacy["secondary_axes"]["word_mattr_50"]}],
            "lexical_targets": legacy["lexical_targets"][:1]}
        card["card_sha256"] = digest(card)
        imported = self.ingest(card)
        self.assertEqual(imported["title"], "慢声")
        self.assertEqual(sum(row["enabled"] for row in imported["controls"]["targets"]), 6)
        card["axes"][0]["target"]["max"] += 1
        with self.assertRaisesRegex(ValueError, "摘要"):
            self.ingest(card)

    def test_wrong_profile_unit_bounds_and_duplicate_cards_do_not_persist(self):
        baseline = len(self.repository.profiles(self.root))
        for mutate in (lambda x: x.update(profile_sha256="wrong"),
            lambda x: x["axes"]["dialogue_share"].update(unit="percent"),
            lambda x: x["axes"]["dialogue_share"].update(max=2)):
            bad = self.legacy()
            mutate(bad)
            with self.assertRaises(ValueError):
                self.ingest(bad)
        tampered = json.loads(self.profile["profile_json"])
        tampered["label"] = "伪造"
        with self.assertRaises(ValueError):
            self.service.import_parameters(self.root, profile_json=json.dumps(tampered))
        self.assertEqual(len(self.repository.profiles(self.root)), baseline)

    def test_all_seven_dependency_targets_are_bound_to_imported_tree(self):
        forms = ["甲", "，", "乙", "丙", "。"]
        heads = [3, 3, 0, 3, 3]
        tokens = [{"id": i, "form": form, "head": head, "pos": "wp" if form in "，。" else "n",
                   "relation": "HED" if head == 0 else "WP" if form in "，。" else "ATT"}
                  for i, (form, head) in enumerate(zip(forms, heads), 1)]
        text = " ".join(forms)
        tree = seal_parse({"text": text, "sentences": [{"id": 1, "text": text, "start": 0, "end": len(text), "tokens": tokens}],
            "annotation_scheme": {"name": "manual_fixture", "punctuation_pos": ["wp"], "punctuation_relations": ["WP"]},
            "annotator": {"name": "manual_fixture", "domain_validity": "fixture_only"}})
        parameters = self.service.parameters(self.root, self.profile["profile_id"], json.dumps(tree))
        controls = self.legacy()
        controls.update(dependency_parse_hash=tree["parse_hash"], dependency_axes={row["id"][4:]:
            {key: row[key] for key in ("min", "max", "unit")} for row in parameters["controls"]["targets"] if row["id"].startswith("dep:")})
        with self.assertRaises(ValueError):
            self.ingest(controls)
        imported = self.ingest(controls, dependency_json=json.dumps(tree))
        self.assertEqual(len([row for row in imported["controls"]["targets"] if row["id"].startswith("dep:") and row["enabled"]]), 7)
        self.assertEqual(json.loads(imported["dependency_json"])["parse_hash"], tree["parse_hash"])

    def test_creator_controls_can_use_existing_profile_and_keep_disabled_targets(self):
        controls = deepcopy(self.profile["controls"])
        controls["targets"][0]["enabled"] = False
        imported = self.service.import_parameters(self.root, profile_id=self.profile["profile_id"], parameters_json=json.dumps(controls))
        self.assertEqual(imported["controls"], controls)
        with self.assertRaisesRegex(ValueError, "画像"):
            self.service.import_parameters(self.root, parameters_json=json.dumps(controls))
