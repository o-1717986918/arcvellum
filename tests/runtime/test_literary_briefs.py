from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.evidence_compiler import EvidenceCompilation
from literary_engineering_studio.runtime.execution_context import ExecutionContextEnvelope
from literary_engineering_studio.runtime.literary_briefs import compile_literary_brief
from literary_engineering_studio.runtime.prompt_compiler import compile_prompt_program
from literary_engineering_studio.runtime.prompt_program import PromptEvidence


class _StubEvidenceProvider:
    def __init__(self, evidence: tuple[PromptEvidence, ...]) -> None:
        self.evidence = evidence
        self.calls = 0

    def provide(self, task, workspace, envelope, *, audience):
        self.calls += 1
        return EvidenceCompilation(
            self.evidence, (), 0, 0, 0, 0, 0, 0
        )


class LiteraryBriefTests(unittest.TestCase):
    def test_scene_brief_compiles_literary_contract_with_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(Path(temporary), route="scene-development", state="generation-agent-task")
            context = _context()
            evidence = (
                _evidence("E001", "scene", "scenes/scene_0001.yaml", {
                    "scene_id": "scene_0001",
                    "scene_goal": "迫使林作出选择",
                    "conflict": "服从命令或救人",
                    "narrative_rhythm": {"pace": "slow_to_fast"},
                    "scene_bridge": {"outgoing_hook": "信号中断"},
                }),
                _evidence("E002", "composition_contract", "drafts/compositions/scene_0001.json", {
                    "characters": [{"name": "林", "intention": "救人"}],
                    "word_budget_contract": {"target_chinese_chars": 3000},
                }),
                _evidence("E003", "canon", "canon/world_rules.yaml", {"rules": ["不能超光速"]}),
                _evidence("E004", "mounted_style", "style/style-profile.md", {"name": "冷静"}),
            )

            brief = compile_literary_brief(
                task, context, _envelope("prose", "generation-agent-task"), evidence,
                {"outputs": [{"path": "draft.md"}]},
            )
            payload = brief.as_dict()

            self.assertEqual(payload["kind"], "scene-writing")
            self.assertEqual(payload["objective"], "迫使林作出选择")
            self.assertEqual(payload["word_count"]["target_chinese_chars"], 3000)
            self.assertEqual(payload["canon_evidence_ids"], ("E003",))
            self.assertEqual(payload["provenance"]["composition_contract"], ("E002",))

    def test_review_state_and_asset_tasks_receive_distinct_briefs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = {"outputs": [{"path": "result.json"}]}
            candidate = _evidence("E001", "candidate", "candidate.md", {"body": "text"})
            deterministic = _evidence("E002", "deterministic_evidence", "lint.json", {"status": "pass"})
            character = _evidence("E003", "character_state", "characters/lin.yaml", {"name": "林"})

            review = compile_literary_brief(
                _task(root, route="scene-development", state="agent-review"),
                _context(), _envelope("review", "agent-review"),
                (candidate, deterministic, character), output,
            ).as_dict()
            state = compile_literary_brief(
                _task(root, route="scene-development", state="state-agent-task"),
                _context(), _envelope("review", "state-agent-task"),
                (candidate, character), output,
            ).as_dict()
            asset = compile_literary_brief(
                _task(root, route="character-and-world-assets", state="asset-creation-agent-task", asset_type="world"),
                _context(), _envelope("structured", "asset-creation-agent-task"),
                (character,), output,
            ).as_dict()
            asset_review = compile_literary_brief(
                _task(root, route="character-and-world-assets", state="asset-review-agent-task", asset_type="world"),
                _context(), _envelope("review", "asset-review-agent-task"),
                (candidate, character), output,
            ).as_dict()

            self.assertEqual(review["kind"], "review")
            self.assertEqual(review["candidate_evidence_ids"], ("E001",))
            self.assertEqual(state["kind"], "state-evolution")
            self.assertEqual(state["character_evidence_ids"], ("E003",))
            self.assertEqual(asset["kind"], "asset")
            self.assertEqual(asset["asset_type"], "world")
            self.assertEqual(asset_review["kind"], "review")

    def test_prompt_compiler_uses_evidence_port_and_hashes_brief(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(root, route="scene-development", state="generation-agent-task")
            evidence = (
                _evidence("E001", "scene", "missing-scene.yaml", {
                    "scene_id": "scene_0001", "scene_goal": "完成选择",
                }),
            )
            provider = _StubEvidenceProvider(evidence)
            program = compile_prompt_program(
                task,
                workspace=root,
                task_context=_context(),
                execution_context=_envelope("prose", "generation-agent-task"),
                user_direction="",
                audience="tool-worker",
                evidence_provider=provider,
            )

            self.assertEqual(provider.calls, 1)
            self.assertEqual(program.literary_brief["objective"], "完成选择")
            self.assertEqual(program.safe_projection()["literary_brief"]["kind"], "scene-writing")
            self.assertEqual(len(program.digest), 64)
            cache = program.compile_metrics["cache_contract"]
            self.assertEqual(cache["dynamic_suffix_digest"], program.digest)
            self.assertEqual(len(cache["stable_prefix_digest"]), 64)


def _task(root: Path, *, route: str, state: str, asset_type: str = "") -> TaskPackage:
    payload = {
        "task_id": f"test-{state}",
        "route": route,
        "current_state": state,
        "task_type": "platform-agent",
        "scene_id": "scene_0001",
        "asset_type": asset_type,
        "source_paths": [],
        "agent_source_paths": [],
        "expected_outputs": ["result.json"],
        "core_managed_outputs": [],
        "hard_constraints": ["不得改变 Canon"],
        "style_constraints": ["保持冷静"],
        "validation_gates": ["语义审查"],
        "forbidden_shortcuts": [],
        "prompt_asset": {
            "body": "完成当前文学任务。",
            "hard_constraints": [],
            "style_constraints": [],
            "review_requirements": ["检查人物因果"],
            "output_contract": ["输出正式产物"],
            "forbidden_shortcuts": [],
        },
    }
    return TaskPackage(root, root / "task.json", root / "task.md", payload)


def _context() -> dict[str, object]:
    return {
        "word_count": {"target": 2800, "minimum": 2500, "maximum": 3200},
        "hard_constraints": ["不得改变 Canon"],
        "style_constraints": ["保持冷静"],
        "validation_gates": ["语义审查"],
        "forbidden_shortcuts": [],
        "output_contracts": [{"path": "result.json", "kind": "semantic-artifact"}],
        "semantic_output_contract": {},
        "core_managed_outputs": [],
        "system_owned_fields": {},
        "prompt_asset": {
            "body": "完成当前文学任务。",
            "hard_constraints": [],
            "review_requirements": ["检查人物因果"],
        },
    }


def _envelope(kind: str, state: str) -> ExecutionContextEnvelope:
    return ExecutionContextEnvelope(
        task_id=f"test-{state}", route="scene-development", current_state=state,
        scene_id="scene_0001", task_kind=kind, agent_role="main-agent",
        prompt_asset_id="asset", prompt_asset_version="1", must_inline=(),
        exact_on_demand=(), summary_references=(), excluded=(),
        expected_outputs=("result.json",), hard_constraints=(), context_digest="a" * 64,
        character_budget=10_000, first_turn_visible_characters=0, budget_mode="enforced",
        prepared_context_sha256="", user_direction_sha256="b" * 64,
    )


def _evidence(
    evidence_id: str, role: str, source_ref: str, body: object
) -> PromptEvidence:
    return PromptEvidence(
        evidence_id=evidence_id, source_ref=source_ref, source_sha256="c" * 64,
        projection_sha256="d" * 64, role=role, tier="must_inline",
        fidelity="structured", body=json.dumps(body, ensure_ascii=False),
    )


if __name__ == "__main__":
    unittest.main()
