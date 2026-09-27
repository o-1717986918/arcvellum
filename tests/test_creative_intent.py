import unittest

from literary_engineering_studio_engine.public.literary import CreativeIntentV1


class CreativeIntentContractTests(unittest.TestCase):
    def test_revision_preserves_free_literary_language_without_becoming_scene_delta(self):
        first = CreativeIntentV1.from_payload({
            "reader_experience": "  让 晚饭 后 的 沉默 显得 安心  ",
            "reader_misreads": "读者暂信她没有察觉",
            "withheld": "杯子为何换了位置",
        })
        second = CreativeIntentV1.from_payload({
            "reader_experience": "让熟悉的沉默变得可疑",
            "reader_knows": "杯子已被换过",
        }, prior=first)
        self.assertEqual(first.revision, 1)
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.to_dict()["schema"], CreativeIntentV1.SCHEMA)
        self.assertNotIn("scene_delta", second.to_dict())

    def test_empty_statement_and_unknown_schema_are_rejected(self):
        with self.assertRaises(ValueError):
            CreativeIntentV1.from_payload({"reader_experience": " "})
        with self.assertRaises(ValueError):
            CreativeIntentV1.from_payload({"schema": "v2", "reader_experience": "停留"})


if __name__ == "__main__":
    unittest.main()
