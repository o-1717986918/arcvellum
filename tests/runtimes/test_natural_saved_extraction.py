"""Recovery revalidates saved source against current scope and never pays in reuse-only mode."""
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
            cosmetic = processor.process(answer, kind="creator", context={"different": True}, reuse_only=True)
            self.assertEqual(cosmetic['prose'], answer)

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

    def test_actor_scope_change_rejects_an_otherwise_literal_cached_invitation(self):
        from tests.actor_card_fixtures import actor_card_payload
        card = actor_card_payload()
        answer = '请求阿青回应。\n' + '\n'.join(card['sections'].values())
        request = {'kind': 'actor', 'target': '阿青', 'purpose': '回应', 'scene_moment': '此刻',
                   'cue': '来话', 'author_prompt': '请求阿青回应。', 'character_card': card}
        context = {'briefing': {'scene_brief': {'participants': ['阿青']}}, 'eligible_actors': ['阿青']}
        with TemporaryDirectory() as temporary:
            root = Path(temporary); directory = root/'natural-answers'/sha256(answer.encode()).hexdigest()
            directory.mkdir(parents=True)
            digest = sha256(json.dumps(['verbatim-commission-v3', 'creator', context, '整理'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            (directory/(digest+'.extraction.md')).write_text(json.dumps({'material_requests': [request]}, ensure_ascii=False), encoding='utf-8')
            processor = NaturalOutputProcessor(root, '整理', lambda *_: self.fail('recovery called a model'))
            self.assertEqual(processor.process(answer, kind='creator', context=context, reuse_only=True)['material_requests'][0]['target'], '阿青')
            with self.assertRaisesRegex(ValueError, 'no valid extraction'):
                processor.process(answer, kind='creator', context={**context, 'eligible_actors': ['别人']}, reuse_only=True)
