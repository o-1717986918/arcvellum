from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import (
    write_agent_completion_marker,
    write_agent_tasks,
)
from literary_engineering_studio_engine.creative_quality import load_creative_quality_profile
from literary_engineering_studio_engine.flow_gates import FlowGateError
from literary_engineering_studio_engine.literary.scene.promotion.candidate import (
    candidate_generation_gate,
    candidate_review_gate,
    promote_scene_candidate,
)
from literary_engineering_studio_engine.literary.scene.promotion.historical import (
    validate_historical_promotion,
)
from literary_engineering_studio_engine.platform_agent_tasks import write_platform_scene_review_task
from literary_engineering_studio_engine.projects.demo import build_demo_project


class DeterministicProsePromotionE2ETests(unittest.TestCase):
    """Exercise the non-LLM half of candidate-to-draft promotion end to end.

    Agent-authored artifacts are controlled fixtures here. The production code
    still validates their provenance, exact candidate digest, task receipts,
    independent reviewer identity, quality contracts, and lint gate before it
    is allowed to promote a candidate.
    """

    def test_clean_candidate_is_promoted_only_after_all_deterministic_gates_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, candidate = self._prepared_candidate(Path(temporary))

            generation = candidate_generation_gate(root, "scene_0001", candidate)
            review = candidate_review_gate(root, "scene_0001", candidate)
            self.assertEqual(generation["status"], "pass", generation)
            self.assertEqual(review["status"], "pass", review)

            result = promote_scene_candidate(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                candidate=candidate.relative_to(root),
                overwrite=True,
            )

            self.assertTrue(result.draft_path.is_file())
            draft = result.draft_path.read_text(encoding="utf-8")
            self.assertIn("林舟把手电压低", draft)
            self.assertNotIn("[AGENT_TASK:", draft)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertFalse(manifest["allow_unreviewed"])
            self.assertFalse(manifest["allow_review_notes"])
            self.assertEqual(manifest["candidate_generation"]["status"], "pass")
            self.assertEqual(manifest["candidate_review"]["status"], "pass")
            historical = validate_historical_promotion(
                root,
                "scene_0001",
                manifest,
            )
            self.assertTrue(historical.passed, historical.errors)
            self.assertTrue(historical.current)

    def test_tampering_or_style_lint_failure_blocks_repromotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, candidate = self._prepared_candidate(Path(temporary))
            candidate.write_text(
                self._candidate_text("不是门后没有人，而是有人刚刚离开。"),
                encoding="utf-8",
            )

            stale = candidate_review_gate(root, "scene_0001", candidate)
            self.assertNotEqual(stale["status"], "pass", stale)
            self.assertEqual(stale["style_lint"]["status"], "blocking", stale)
            with self.assertRaises(FlowGateError):
                promote_scene_candidate(
                    root,
                    scene=Path("scenes/scene_0001.yaml"),
                    candidate=candidate.relative_to(root),
                    overwrite=True,
                )

    def test_cli_promote_candidate_runs_without_any_bypass_option(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, candidate = self._prepared_candidate(Path(temporary))
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "literary_engineering_studio_engine",
                    "promote-candidate",
                    str(root),
                    "--scene",
                    "scenes/scene_0001.yaml",
                    "--candidate",
                    candidate.relative_to(root).as_posix(),
                    "--overwrite",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("draft:", result.stdout)
            self.assertTrue((root / "drafts" / "scenes" / "scene_0001.md").is_file())

    def _prepared_candidate(self, root: Path) -> tuple[Path, Path]:
        build_demo_project(root, title="晋升端到端回归", run_agent_workflow=False)
        scene = root / "scenes" / "scene_0001.yaml"
        context = root / "memory" / "context_packets" / "scene_0001.md"
        candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(
            self._candidate_text(
                "林舟把手电压低，等巡逻灯从街口滑过去，才推开旧楼的门。门轴没有响，楼道里却有一截电流声。"
            ),
            encoding="utf-8",
        )
        profile = load_creative_quality_profile(root)
        prompt_manifest = candidate.with_suffix(".prompt.json")
        prompt_manifest.write_text(
            json.dumps(
                {
                    "generation_standards": {
                        "creative_quality_profile_digest": profile["digest"],
                        "narrative_rhythm_contract": {"status": "defaulted", "plan_digest": ""},
                        "reader_experience_contract": {"status": "not_required"},
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        generation_task = candidate.with_suffix(".agent_tasks.md")
        write_agent_tasks(
            generation_task,
            title="确定性晋升测试：正文候选",
            root=root,
            source_paths=[scene, context, prompt_manifest],
            tasks=[("正文候选", "写入候选正文和候选 manifest；不要绕过审查。")],
        )
        write_agent_completion_marker(generation_task, root=root, handled_by="deterministic-writer-fixture")
        candidate_manifest = {
            "schema": "literary-engineering-workbench/scene-candidate/v1",
            "formal_contract_revision": "2026-07-23.3",
            "generated_by": "platform-agent",
            "provider": "tool-layer-agent",
            "candidate": candidate.relative_to(root).as_posix(),
            "writer_session_id": "writer-e2e",
            "prompt_manifest": prompt_manifest.relative_to(root).as_posix(),
            "style_generation_standard_applied": True,
            "hard_constraints_applied": True,
            "anti_evasion_protocol_applied": True,
            "narrative_rhythm_standard_applied": True,
            "word_budget_standard_applied": False,
            "pass_with_notes_actions_applied": False,
            "creative_quality_profile_digest": profile["digest"],
            "canon_writeback": {
                "canon_change": False,
                "no_canon_change_reason": "本场仅推进已登记的旧楼线索，没有新增正式世界规则。",
            },
            "new_character_register": self._register("existing_only"),
        }
        candidate.with_suffix(".json").write_text(
            json.dumps(candidate_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        review_result = write_platform_scene_review_task(
            root,
            scene_path=scene,
            draft_path=candidate,
            materialization_scope="scene",
        )
        review = review_result.expected_json_path
        review_task = review_result.task_path
        candidate_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
        review_payload = {
            "schema": "literary-engineering-workbench/scene-review-agent/v1",
            "scene_id": "scene_0001",
            "candidate": candidate.relative_to(root).as_posix(),
            "candidate_sha256": candidate_sha256,
            "conclusion": "pass",
            "summary": "候选正文与当前场景目标、节奏和已知人物状态一致。",
            "blocking_issues": [],
            "warnings": [],
            "revision_actions": [],
            "character_logic": [],
            "canon_risks": [],
            "style_notes": [],
            "style_adherence": {"status": "pass", "deviations": [], "revision_actions": []},
            "word_budget_adherence": {"status": "not_required", "narrative_load_satisfied": True},
            "reader_experience_adherence": {"status": "not_required", "reader_promise_satisfied": True},
            "narrative_rhythm_adherence": {"status": "not_applicable", "rhythm_executed": True, "bridge_executed": True},
            "canon_writeback": {
                "status": "not_required",
                "canon_change": False,
                "no_canon_change_reason": "本场不确认新的世界规则。",
            },
            "new_character_register": self._register("existing_only"),
            "revision_integrity": {
                "status": "not_applicable",
                "anti_evasion_checked": True,
                "evasion_risks_unresolved": [],
            },
            "source_paths": [candidate.relative_to(root).as_posix()],
            "creative_quality_profile": {"digest": profile["digest"]},
            "reviewer_session_id": "reviewer-e2e",
        }
        review.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        review.with_suffix(".md").write_text("# 独立审查\n\n结论：通过。\n", encoding="utf-8")
        write_agent_completion_marker(review_task, root=root, handled_by="deterministic-reviewer-fixture")
        return root, candidate

    @staticmethod
    def _candidate_text(body: str) -> str:
        return (
            "# scene_0001 候选正文\n\n"
            "## 正文候选\n\n"
            f"{body}\n\n"
            "### 新增事实候选\n\n- 无。\n\n"
            "### 人物状态变化\n\n- 林舟决定进入旧楼。\n\n"
            "### 关系变化\n\n- 无。\n\n"
            "### 伏笔变化\n\n- 楼道电流声成为待查线索。\n\n"
            "### 需要人工确认\n\n- 无。\n"
        )

    @staticmethod
    def _register(status: str) -> dict[str, object]:
        return {
            "schema": "literary-engineering-workbench/new-character-register/v0.1",
            "status": status,
            "introduced": [],
            "ephemeral_waivers": [],
            "blocking_issues": [],
        }


if __name__ == "__main__":
    unittest.main()
