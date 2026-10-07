"""Recovery reuses only same-context saved source and never pays in reuse-only mode."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor


class SavedExtractionTests(unittest.TestCase):
    def test_valid_legacy_extract_is_revalidated_without_model_call(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            answer = "雨滴落在空碗里。"
            directory = root / "natural-answers" / sha256(answer.encode()).hexdigest()
            directory.mkdir(parents=True)
            fingerprint = sha256(json.dumps(["verbatim-commission-v3", "creator", {}, "整理"],
                ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            (directory / (fingerprint + ".extraction.md")).write_text(json.dumps({"prose": answer}), encoding="utf-8")
            processor = NaturalOutputProcessor(root, "整理", lambda *_: self.fail("recovery called a model"))
            result = processor.process(answer, kind="creator", context={}, reuse_only=True)
            self.assertEqual(result["prose"], answer)
            self.assertIn("reused_extraction", result)
            with self.assertRaisesRegex(ValueError, "no valid extraction"):
                processor.process(answer, kind="creator", context={"different": True}, reuse_only=True)

    def test_invalid_current_cache_does_not_call_model_during_recovery(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            answer = "雨滴落在空碗里。"
            directory = root / "natural-answers" / sha256(answer.encode()).hexdigest()
            directory.mkdir(parents=True)
            fingerprint = sha256(json.dumps(["verbatim-commission-v4", "creator", {}, "整理"],
                ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            (directory / (fingerprint + ".json")).write_text('{"prose":"改写的文字"}', encoding="utf-8")
            processor = NaturalOutputProcessor(root, "整理", lambda *_: self.fail("recovery called a model"))
            with self.assertRaisesRegex(ValueError, "changed prose"):
                processor.process(answer, kind="creator", context={}, reuse_only=True)
