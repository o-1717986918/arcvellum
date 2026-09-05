from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.memory_index import (
    build_memory_index,
    memory_index_is_fresh,
    search_memory,
    trust_tier_for_relative_path,
)


class MemoryTrustTierTests(unittest.TestCase):
    def test_default_generation_retrieval_excludes_candidate_and_diagnostic_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, text in {
                "project.yaml": "project: formal signal\n",
                "canon/world_rules.yaml": "formal signal\n",
                "drafts/candidates/scene_0001.md": "candidate signal\n",
                "reviews/scene_0001.md": "diagnostic signal\n",
            }.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            build_memory_index(root)

            default_hits = search_memory(root, "signal", top_k=10)
            self.assertTrue(default_hits)
            self.assertTrue(all(hit.trust_tier in {"formal", "approved"} for hit in default_hits))
            self.assertEqual(trust_tier_for_relative_path("drafts/candidates/scene_0001.md"), "candidate")
            self.assertEqual(trust_tier_for_relative_path("reviews/scene_0001.md"), "diagnostic")

            candidates = search_memory(root, "candidate signal", top_k=10, allowed_tiers={"candidate"})
            self.assertEqual([hit.trust_tier for hit in candidates], ["candidate"])

    def test_search_rebuilds_a_stale_content_bound_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "canon/world_rules.yaml"
            source.parent.mkdir(parents=True)
            source.write_text("rule: 旧潮线\n", encoding="utf-8")
            build_memory_index(root)
            self.assertTrue(memory_index_is_fresh(root))

            source.write_text("rule: 星潮新规\n", encoding="utf-8")
            self.assertFalse(memory_index_is_fresh(root))
            hits = search_memory(root, "星潮新规", top_k=5)

            self.assertTrue(memory_index_is_fresh(root))
            self.assertTrue(any("星潮新规" in hit.text for hit in hits))


if __name__ == "__main__":
    unittest.main()
