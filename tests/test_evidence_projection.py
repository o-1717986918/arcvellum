from __future__ import annotations

import json
import unittest

from literary_engineering_studio.runtime.evidence_projection import project_evidence_body


class EvidenceProjectionTests(unittest.TestCase):
    def test_lossless_evidence_is_never_projected(self):
        body = '{"empty":"","body":"正文"}'
        self.assertEqual(project_evidence_body("candidate.json", body, fidelity="lossless"), body)

    def test_review_projection_removes_redundant_transport_but_keeps_gate_values(self):
        body = json.dumps(
            {
                "schema": "review-context/v1",
                "creative_quality_profile": {"duplicate": "exact-style"},
                "source_digests": {"scene": "abc"},
                "deterministic_evidence": {
                    "style_lint": {"status": "failed", "blocking": ["contrast"]},
                    "word_budget": {
                        "status": "pass",
                        "target_chinese_chars": 1000,
                        "machine_count_mapping": {"verbose": "diagnostic-only"},
                    },
                    "narrative_rhythm": {
                        "status": "pass",
                        "narrative_rhythm": {"duplicate": "exact-scene"},
                    },
                },
                "output_schema": {
                    "resource_sha256": "resource",
                    "contract_sha256": "contract",
                    "contract": {
                        "schema_id": "scene_review.v1",
                        "required": ["conclusion", "character_logic"],
                        "recommended": ["agent_confidence"],
                        "types": {
                            "conclusion": "str",
                            "character_logic": "list",
                            "agent_confidence": "str",
                        },
                    },
                },
            },
            ensure_ascii=False,
        )
        projected = json.loads(
            project_evidence_body("reviews/scene_review.context.json", body, fidelity="structured")
        )

        self.assertNotIn("creative_quality_profile", projected)
        self.assertNotIn("source_digests", projected)
        self.assertEqual(projected["deterministic_evidence"]["style_lint"]["blocking"], ["contrast"])
        self.assertEqual(projected["deterministic_evidence"]["word_budget"]["target_chinese_chars"], 1000)
        self.assertNotIn("machine_count_mapping", projected["deterministic_evidence"]["word_budget"])
        self.assertEqual(
            projected["output_schema"]["contract"]["required_type_groups"],
            {"str": ["conclusion"], "list": ["character_logic"]},
        )
        self.assertNotIn("required", projected["output_schema"]["contract"])
        self.assertNotIn("types", projected["output_schema"]["contract"])
        self.assertNotIn("recommended", projected["output_schema"]["contract"])
        self.assertEqual(projected["output_schema"]["contract_sha256"], "contract")


if __name__ == "__main__":
    unittest.main()
