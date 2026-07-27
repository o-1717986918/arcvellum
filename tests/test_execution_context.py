from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.context_budget import (
    resolve_task_context_budget,
)
from literary_engineering_studio.runtime.context_selection import (
    AgentContextSelection,
)
from literary_engineering_studio.runtime.execution_context import (
    ContextVisibilityTier,
    build_execution_context_envelope,
)
from literary_engineering_studio.runtime.prompt_context import (
    PreparedPromptContext,
)


class ExecutionContextEnvelopeTests(unittest.TestCase):
    def test_compiles_four_disjoint_tiers_and_stable_content_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "inline.md").write_text("exact first turn", encoding="utf-8")
            (root / "on-demand.md").write_text("exact later", encoding="utf-8")
            source = root / "canon" / "large-source.md"
            source.parent.mkdir()
            source.write_text("canonical source", encoding="utf-8")
            source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
            task = _task(
                root,
                context_summary_references=[
                    {
                        "source_ref": "canon/large-source.md",
                        "summary": "Digest-bound short summary.",
                        "source_sha256": source_digest,
                    }
                ],
            )
            selection = AgentContextSelection(
                source_paths=("inline.md", "on-demand.md"),
                reference_paths=(),
                operational_paths=(),
                visible_paths=("inline.md", "on-demand.md"),
                excluded_paths=("private/other.md",),
                summary_reference_paths=("canon/large-source.md",),
            )
            prepared = _prepared()
            budget = resolve_task_context_budget(task)

            first = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=prepared,
                budget=budget,
            )
            second = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=prepared,
                budget=budget,
            )

            self.assertEqual(first.context_digest, second.context_digest)
            self.assertEqual(first.must_inline, ("inline.md",))
            self.assertEqual(first.exact_on_demand, ("on-demand.md",))
            self.assertEqual(first.summary_reference_paths, ("canon/large-source.md",))
            self.assertEqual(first.excluded, ("private/other.md",))
            self.assertIs(
                first.tier_for("canon/large-source.md"),
                ContextVisibilityTier.SUMMARY_REFERENCE,
            )

            (root / "on-demand.md").write_text("changed exact later", encoding="utf-8")
            changed = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=prepared,
                budget=budget,
            )
            self.assertNotEqual(first.context_digest, changed.context_digest)

    def test_declared_mandatory_context_must_be_present_in_first_turn(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "inline.md").write_text("exact first turn", encoding="utf-8")
            (root / "on-demand.md").write_text("exact later", encoding="utf-8")
            source = root / "canon" / "source.md"
            source.parent.mkdir()
            source.write_text("source", encoding="utf-8")
            task = _task(
                root,
                context_must_inline_paths=["on-demand.md"],
            )
            selection = AgentContextSelection(
                source_paths=("inline.md", "on-demand.md"),
                reference_paths=(),
                operational_paths=(),
                visible_paths=("inline.md", "on-demand.md"),
            )

            with self.assertRaisesRegex(
                ValueError,
                "mandatory paths are not present",
            ):
                build_execution_context_envelope(
                    task,
                    workspace=root,
                    selection=selection,
                    prepared_context=_prepared(),
                    budget=resolve_task_context_budget(task),
                )

    def test_summary_reference_requires_exact_source_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "inline.md").write_text("exact first turn", encoding="utf-8")
            (root / "on-demand.md").write_text("exact later", encoding="utf-8")
            task = _task(
                root,
                context_summary_references=[
                    {
                        "source_ref": "canon/source.md",
                        "summary": "summary",
                        "source_sha256": "not-a-digest",
                    }
                ],
            )
            selection = AgentContextSelection(
                source_paths=("inline.md", "on-demand.md"),
                reference_paths=(),
                operational_paths=(),
                visible_paths=("inline.md", "on-demand.md"),
                summary_reference_paths=("canon/source.md",),
            )

            with self.assertRaisesRegex(ValueError, "source_sha256"):
                build_execution_context_envelope(
                    task,
                    workspace=root,
                    selection=selection,
                    prepared_context=_prepared(),
                    budget=resolve_task_context_budget(task),
                )

    def test_user_direction_changes_context_identity_without_exposing_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "inline.md").write_text("exact first turn", encoding="utf-8")
            (root / "on-demand.md").write_text("exact later", encoding="utf-8")
            task = _task(root)
            selection = AgentContextSelection(
                source_paths=("inline.md", "on-demand.md"),
                reference_paths=(),
                operational_paths=(),
                visible_paths=("inline.md", "on-demand.md"),
            )
            budget = resolve_task_context_budget(task)
            first = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=_prepared(),
                budget=budget,
                user_direction="保留克制的叙事距离。",
            )
            changed = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=_prepared(),
                budget=budget,
                user_direction="把结尾改成静默余波。",
            )

            self.assertNotEqual(first.context_digest, changed.context_digest)
            self.assertNotEqual(
                first.user_direction_sha256,
                changed.user_direction_sha256,
            )
            safe = json.dumps(changed.safe_projection(), ensure_ascii=False)
            self.assertNotIn("把结尾改成静默余波", safe)
            self.assertNotIn(changed.user_direction_sha256, safe)
            self.assertEqual(
                changed.as_dict()["user_direction_sha256"],
                changed.user_direction_sha256,
            )


def _prepared() -> PreparedPromptContext:
    rendered = "----- exact first turn -----"
    return PreparedPromptContext(
        rendered=rendered,
        included_paths=("inline.md",),
        omitted_paths=("on-demand.md",),
        character_count=len(rendered),
        sha256=hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
    )


def _task(root: Path, **extra) -> TaskPackage:
    payload = {
        "task_id": "scene-context-envelope",
        "route": "scene-development",
        "current_state": "candidate-review",
        "task_type": "platform-agent-review",
        "execution_policy": "agent-required",
        "agent_role": "main-review-agent",
        "runtime_capabilities_required": ["read-task-sources", "write-expected-outputs"],
        "human_gate": {"required": False, "reasons": [], "source": "test"},
        "expected_outputs": ["reviews/scene.json"],
        "output_contracts": [
            {
                "path": "reviews/scene.json",
                "kind": "agent-authored",
                "writeback_policy": "preview-required",
            }
        ],
        "prompt_asset": {
            "resolved_id": "route.scene-development.agent-review.v1",
            "version": "v2",
            "hard_constraints": ["Review the exact candidate."],
        },
        **extra,
    }
    return TaskPackage(root, root / "task.json", root / "task.md", payload)


if __name__ == "__main__":
    unittest.main()
