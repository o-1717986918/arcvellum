from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import admission_plan
from literary_engineering_studio.runtime.resources import ResourceClaim


def _claim(
    node_id: str,
    *,
    reads: tuple[str, ...] = (),
    writes: tuple[str, ...] = (),
    barriers: tuple[str, ...] = (),
    project_id: str = "project-test",
) -> ResourceClaim:
    return ResourceClaim(
        task_node_id=node_id,
        project_id=project_id,
        reads=reads,
        writes=writes,
        runtime_slot="agent-worker",
        model_slot="default",
        network="none",
        exclusive_barriers=barriers,
    )


class ResourceGateTests(unittest.TestCase):
    def test_read_only_claims_form_one_parallel_group(self):
        plan = admission_plan(
            (
                _claim("reader-1", reads=("canon/a.md",)),
                _claim("reader-2", reads=("canon/b.md",)),
                _claim("reader-3", reads=("canon/c.md",)),
            )
        )

        self.assertTrue(plan.passed)
        self.assertEqual(plan.serialized, ())
        self.assertEqual(len(plan.parallel_groups), 1)
        self.assertEqual(
            plan.parallel_groups[0].task_node_ids,
            ("reader-1", "reader-2", "reader-3"),
        )

    def test_parallel_limit_splits_groups(self):
        plan = admission_plan(
            (
                _claim("reader-1", reads=("a.md",)),
                _claim("reader-2", reads=("b.md",)),
                _claim("reader-3", reads=("c.md",)),
            ),
            max_parallel_read_tasks=2,
        )

        self.assertEqual(len(plan.parallel_groups), 2)
        self.assertEqual(plan.parallel_groups[0].task_node_ids, ("reader-1", "reader-2"))
        self.assertEqual(plan.parallel_groups[1].task_node_ids, ("reader-3",))

    def test_writers_are_serialized_singletons(self):
        plan = admission_plan(
            (
                _claim("reader-1", reads=("drafts/scenes/a.md",)),
                _claim("writer-1", writes=("drafts/scenes/a.md",)),
            )
        )

        self.assertTrue(plan.passed)
        self.assertEqual(plan.serialized, ("writer-1",))
        self.assertEqual(
            plan.parallel_groups[0].task_node_ids,
            ("reader-1",),
        )

    def test_exclusive_barriers_force_serialization(self):
        plan = admission_plan(
            (
                _claim("writer-1", reads=("a.md",), barriers=("canon",)),
                _claim("writer-2", reads=("b.md",), barriers=("canon",)),
            )
        )

        self.assertTrue(plan.passed)
        self.assertEqual(
            plan.serialized,
            ("writer-1", "writer-2"),
        )
        self.assertEqual(plan.parallel_groups, ())

    def test_different_projects_never_conflict(self):
        plan = admission_plan(
            (
                _claim("reader-1", reads=("a.md",), project_id="project-a"),
                _claim("reader-2", reads=("a.md",), project_id="project-b"),
            )
        )

        self.assertEqual(len(plan.parallel_groups), 1)
        self.assertEqual(
            plan.parallel_groups[0].task_node_ids,
            ("reader-1", "reader-2"),
        )

    def test_duplicate_claims_fail_closed(self):
        plan = admission_plan(
            (
                _claim("reader-1", reads=("a.md",)),
                _claim("reader-1", reads=("b.md",)),
            )
        )

        self.assertFalse(plan.passed)
        codes = {item.code for item in plan.violations}
        self.assertIn("duplicate-claim", codes)
        self.assertEqual(plan.parallel_groups, ())

    def test_invalid_parallel_limit_fails_closed(self):
        plan = admission_plan(
            (_claim("reader-1", reads=("a.md",)),),
            max_parallel_read_tasks=0,
        )

        self.assertFalse(plan.passed)
        codes = {item.code for item in plan.violations}
        self.assertIn("invalid-parallel-limit", codes)


if __name__ == "__main__":
    unittest.main()
