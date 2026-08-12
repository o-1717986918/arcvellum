from __future__ import annotations

import json
import unittest

from literary_engineering_studio.runtime.evidence_projection import project_evidence_body


class EvidenceProjectionTests(unittest.TestCase):
    def test_canon_review_projection_keeps_durable_fact_judgment(self):
        review = json.dumps(
            {
                "schema": "scene-review/v1",
                "scene_id": "scene_0001",
                "candidate_sha256": "abc",
                "conclusion": "pass",
                "summary": "正文通过，并产生持续世界事实。",
                "canon_writeback": {
                    "canon_change": True,
                    "candidate_patch": "特征码已被三组冗余校验确认。",
                },
                "canon_violations": [],
                "revision_actions": [],
                "style_adherence": {"large": "x" * 20_000},
                "reader_experience_adherence": {"large": "y" * 20_000},
            },
            ensure_ascii=False,
        )

        projected = json.loads(
            project_evidence_body(
                "reviews/agent/scene_0001_scene_review.json",
                review,
                fidelity="structured",
                projection="canon-scene-review",
            )
        )

        self.assertTrue(projected["canon_writeback"]["canon_change"])
        self.assertEqual(projected["candidate_sha256"], "abc")
        self.assertNotIn("style_adherence", projected)
        self.assertNotIn("reader_experience_adherence", projected)

    def test_state_review_projections_keep_writeback_causality_without_pipeline_replay(self):
        patch = json.dumps(
            {
                "schema": "state/v1",
                "generated_at": "volatile",
                "project_root": "machine-path",
                "scene_id": "scene_0001",
                "source_artifact": "drafts/scenes/scene_0001.md",
                "status": "pending_human_approval",
                "characters": [
                    {
                        "character_id": "lin",
                        "name": "林",
                        "file": "characters/lin.yaml",
                        "current_state": {"arc": {"current_stage": "守规"}},
                        "proposed_updates": {"arc": {"candidate_changes": ["林开始抗命"]}},
                        "confidence": "candidate",
                    }
                ],
                "source_changes": {"character_changes": ["林开始抗命"]},
                "source_change_sources": ["drafts/compositions/scene_0001_composition.json"],
                "guardrails": ["重复的流程说明"],
                "approval_required": ["重复的审批说明"],
            },
            ensure_ascii=False,
        )
        projected_patch = json.loads(
            project_evidence_body(
                "characters/state_patches/scene_0001_state_patch.json",
                patch,
                fidelity="structured",
                projection="state-patch",
            )
        )
        self.assertEqual(projected_patch["characters"][0]["character_id"], "lin")
        self.assertIn("source_changes", projected_patch)
        self.assertNotIn("project_root", projected_patch)
        self.assertNotIn("guardrails", projected_patch)
        self.assertNotIn("approval_required", projected_patch)

        character = """character_id: lin
name: 林
role: 主角
candidate:
  source_paths: [one, two]
background_story:
  summary: 曾因服从规程失去同伴
  formative_events: [冗长传记]
  behavior_influences: [先核验再行动]
  reveal_policy: implicit_only
bdi:
  belief: [证据重要]
psychology:
  fear: [再次失去同伴]
  moral_line: 不伪造证据
state:
  location: 站内
arc:
  current_stage: 守规
"""
        projected_character = project_evidence_body(
            "characters/lin.yaml",
            character,
            fidelity="structured",
            projection="state-character",
        )
        self.assertIn("behavior_influences", projected_character)
        self.assertIn("moral_line", projected_character)
        self.assertNotIn("formative_events", projected_character)
        self.assertNotIn("source_paths", projected_character)

        composition = json.dumps(
            {
                "scene_id": "scene_0001",
                "characters": [{"very": "large"}],
                "beats": [{"duplicate": "large"}],
                "writeback_candidates": {"character_changes": ["林开始抗命"]},
                "scene_bridge": {"outgoing_hook": "追责"},
            },
            ensure_ascii=False,
        )
        projected_composition = json.loads(
            project_evidence_body(
                "drafts/compositions/scene_0001_composition.json",
                composition,
                fidelity="structured",
                projection="state-composition",
            )
        )
        self.assertEqual(projected_composition["writeback_candidates"]["character_changes"], ["林开始抗命"])
        self.assertNotIn("characters", projected_composition)
        self.assertNotIn("beats", projected_composition)

    def test_prose_context_packet_keeps_hard_facts_and_drops_duplicate_transport_sections(self):
        body = """# 场景上下文包：scene_0002

## 项目配置

重复的项目配置。

## 当前场景

重复的场景契约。

## 硬约束：Canon 与时间线

### canon/world_rules.yaml

rules:
  - id: fuel_deadline
    description: 改轨后不能同时救人并返航。
  - id: candidate_not_confirmed
    description: 本候选资产未经 schema 审查与人工批准不得晋升。

## 人物状态

### 加载策略

- 这是 Context Broker 的传输说明。

### 主要角色常驻档案

### protagonist.yaml（主要角色常驻）

```yaml
name: 林
background_story:
  summary: 曾因服从规程失去同伴。
```

### 本场景省略的次要角色

- unrelated-cameo

## 剧情状态

整本大纲的重复内容。

## 上一场正式交接

- 未完成动作：等待对接口令。

## 风格约束

重复的风格文件。

## 软记忆检索

重复检索回显。
"""

        projected = project_evidence_body(
            "memory/context_packets/scene_0002.md",
            body,
            fidelity="structured",
            projection="prose-context-packet",
        )

        self.assertIn("fuel_deadline", projected)
        self.assertNotIn("candidate_not_confirmed", projected)
        self.assertIn("background_story", projected)
        self.assertIn("等待对接口令", projected)
        self.assertNotIn("项目配置", projected)
        self.assertNotIn("当前场景\n", projected)
        self.assertNotIn("加载策略", projected)
        self.assertNotIn("unrelated-cameo", projected)
        self.assertNotIn("整本大纲", projected)
        self.assertNotIn("软记忆检索", projected)

    def test_prose_budget_projection_uses_declared_chapter_and_drops_stale_inventory_issues(self):
        body = json.dumps(
            {
                "schema": "word-budget/v1",
                "status": "needs_expansion",
                "target": {"target_chinese_chars": 6000},
                "totals": {"chapter_count": 2},
                "chapter_budgets": [
                    {"chapter_id": "chapter_0001", "target_words": 2700},
                    {"chapter_id": "chapter_0002", "target_words": 3300},
                ],
                "scene_inventory_binding": {
                    "chapter_rows": [
                        {"chapter_id": "chapter_0001", "scene_ids": [], "missing_scene_count": 2},
                        {"chapter_id": "chapter_0002", "scene_ids": [], "missing_scene_count": 2},
                    ]
                },
                "issues": [{"message": "stale pre-materialization inventory warning"}],
            },
            ensure_ascii=False,
        )

        projected = json.loads(
            project_evidence_body(
                "plot/word_budget/word_budget.json",
                body,
                fidelity="structured",
                projection="prose-word-budget",
                scene_id="scene_0001",
                chapter_id="chapter_0001",
            )
        )

        self.assertEqual(projected["current_chapter_budget"]["target_words"], 2700)
        self.assertNotIn("status", projected)
        self.assertNotIn("issues", projected)
        self.assertNotIn("status", projected["current_chapter_inventory"])
        self.assertNotIn("missing_scene_count", projected["current_chapter_inventory"])
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
                        "object_shapes": {
                            "canon_writeback": {
                                "status": "str",
                                "canon_change": "bool | str",
                            }
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
        self.assertEqual(
            projected["output_schema"]["contract"]["object_shapes"]["canon_writeback"],
            {"status": "str", "canon_change": "bool | str"},
        )
        self.assertEqual(projected["output_schema"]["contract_sha256"], "contract")

    def test_prose_composition_projection_keeps_literary_contract_without_nested_copies(self):
        body = json.dumps(
            {
                "schema": "composition/v1",
                "generated_at": "transport-only",
                "project_root": "machine-path",
                "scene_id": "scene_0001",
                "selected_branch": "branch-a",
                "scene_facts": {"scene_goal": "改变人物选择"},
                "characters": [
                    {
                        "name": "林",
                        "belief": ["规程可靠"],
                        "background_story": {"summary": "曾因违令失去同伴"},
                    }
                ],
                "beats": [{"visible_action": "林关闭舱门", "pace": "fast"}],
                "composition_obligations": {"word_target_hanzi": 1400},
                "prose_seed": ["没有突然爆发，它只是一步一步逼近。"],
                "narrative_rhythm": {"scene_turn": "服从转为抗命"},
                "scene_bridge": {"outgoing_hook": "追责信号抵达"},
                "reader_experience_contract": {
                    "status": "pass",
                    "required": True,
                    "chapter_obligation": {"duplicate": "whole chapter"},
                    "reader_experience": {"reader_question": "他会抗命吗？"},
                },
                "word_budget_contract": {
                    "scene_id": "scene_0001",
                    "target_chinese_chars": 1400,
                    "status": "needs_expansion",
                    "message": "stale pre-materialization warning",
                    "machine_count_mapping": {"diagnostic": "verbose"},
                },
                "revision_targets": ["旧的流程修订提示"],
                "guardrails": ["等待 CLI 门禁"],
                "creative_quality_profile": {"duplicate": "exact profile"},
                "prose_execution_contract": {
                    "status": "pass",
                    "input_contract_digest": "abc",
                    "beats": [{"duplicate": "beats"}],
                },
            },
            ensure_ascii=False,
        )
        projected = json.loads(
            project_evidence_body(
                "drafts/compositions/scene_0001_composition.json",
                body,
                fidelity="structured",
                projection="prose-composition",
                scene_id="scene_0001",
            )
        )

        self.assertEqual(projected["characters"][0]["background_story"]["summary"], "曾因违令失去同伴")
        self.assertEqual(projected["narrative_rhythm"]["scene_turn"], "服从转为抗命")
        self.assertEqual(projected["scene_bridge"]["outgoing_hook"], "追责信号抵达")
        self.assertEqual(projected["word_budget_contract"]["target_chinese_chars"], 1400)
        self.assertNotIn("status", projected["word_budget_contract"])
        self.assertNotIn("message", projected["word_budget_contract"])
        self.assertEqual(
            projected["reader_experience_contract"]["reader_experience"]["reader_question"],
            "他会抗命吗？",
        )
        self.assertNotIn("chapter_obligation", projected["reader_experience_contract"])
        self.assertNotIn("creative_quality_profile", projected)
        self.assertNotIn("generated_at", projected)
        self.assertNotIn("revision_targets", projected)
        self.assertNotIn("guardrails", projected)
        self.assertNotIn("prose_seed", projected)
        self.assertNotIn("beats", projected["prose_execution_contract"])

    def test_prose_chapter_projection_keeps_payoff_and_non_resolution_obligations(self):
        body = json.dumps(
            {
                "schema": "chapter-obligation/v1",
                "chapter_id": "chapter_0001",
                "chapter_function": "建立救援代价",
                "must_payoff": ["兑现第一次承诺"],
                "must_not_resolve": ["不得揭晓救援成败"],
                "reader_experience_by_scene": [{"verbose": "duplicated elsewhere"}],
                "source_paths": ["implementation detail"],
            },
            ensure_ascii=False,
        )
        projected = json.loads(
            project_evidence_body(
                "plot/chapter_obligations/chapter_0001.json",
                body,
                fidelity="structured",
                projection="prose-chapter-obligation",
            )
        )
        self.assertEqual(projected["must_payoff"], ["兑现第一次承诺"])
        self.assertEqual(projected["must_not_resolve"], ["不得揭晓救援成败"])
        self.assertNotIn("reader_experience_by_scene", projected)
        self.assertNotIn("source_paths", projected)


if __name__ == "__main__":
    unittest.main()
