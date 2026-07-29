from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.observability.throughput_metrics import (
    build_throughput_projection,
)
from literary_engineering_studio.runtime.context_access import (
    CONTEXT_ACCESS_SCHEMA,
    summarize_context_access,
)


class ContextAccessTests(unittest.TestCase):
    def test_summarizes_reads_without_retaining_paths_or_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "exact.md").write_text("按需证据", encoding="utf-8")
            (root / "inline.md").write_text("首轮证据", encoding="utf-8")
            (root / "other.md").write_text("其他资料", encoding="utf-8")
            (root / "reviews" / "agent").mkdir(parents=True)
            (root / "reviews" / "agent" / "review.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (root / "agent").mkdir()
            (root / "TASK_CONTEXT.json").write_text(
                json.dumps(
                    {
                        "source_paths": ["other.md"],
                        "reference_paths": [],
                        "core_managed_outputs": [],
                        "expected_outputs": [
                            "reviews/agent/review.json"
                        ],
                        "execution_context": {
                            "must_inline": ["inline.md"],
                            "exact_on_demand": ["exact.md"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            messages = [
                {
                    "parts": [
                        _tool("read", {"filePath": "exact.md"}),
                        _tool(
                            "read",
                            {"filePath": str(root / "exact.md")},
                        ),
                        _tool("read", {"path": "inline.md"}),
                        _tool("read", {"file_path": "other.md"}),
                        _tool("read", {"filePath": str(root)}),
                        _tool("read", {"filePath": str(root / "agent")}),
                        _tool("read", {"filePath": "reviews"}),
                        _tool(
                            "read",
                            {"filePath": "reviews/agent"},
                        ),
                        _tool(
                            "read",
                            {"filePath": "reviews/agent/review.json"},
                        ),
                        _tool("read", {"path": "../outside.md"}),
                        _tool(
                            "read",
                            {"path": "ignored.md"},
                            status="error",
                        ),
                        _tool("grep", {"path": "."}),
                    ]
                }
            ]

            summary = summarize_context_access(messages, root)

            self.assertEqual(summary["schema"], CONTEXT_ACCESS_SCHEMA)
            self.assertEqual(summary["read_tool_calls"], 10)
            self.assertEqual(summary["unique_read_targets"], 8)
            self.assertEqual(summary["exact_on_demand_read_calls"], 2)
            self.assertEqual(summary["exact_on_demand_unique_files"], 1)
            self.assertEqual(
                summary["exact_on_demand_read_characters"],
                len("按需证据"),
            )
            self.assertEqual(summary["must_inline_reread_calls"], 1)
            self.assertEqual(summary["expected_output_read_calls"], 3)
            self.assertEqual(summary["infrastructure_read_calls"], 2)
            self.assertEqual(summary["other_authorized_read_calls"], 1)
            self.assertEqual(summary["unmapped_read_calls"], 1)
            self.assertEqual(summary["redundant_read_calls"], 1)
            serialized = json.dumps(summary, ensure_ascii=False)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("按需证据", serialized)
            self.assertNotIn("exact.md", serialized)

    def test_projects_context_access_as_typed_throughput_fact(self):
        events = [
            {
                "sequence": 1,
                "event": "worker.task.opened",
                "data": {"task_id": "task-one"},
            },
            {
                "sequence": 2,
                "event": "worker.context.access.summary",
                "data": {
                    "task_id": "task-one",
                    "read_tool_calls": 2,
                    "exact_on_demand_read_calls": 1,
                    "exact_on_demand_unique_files": 1,
                    "exact_on_demand_read_characters": 420,
                },
            },
        ]

        projection = build_throughput_projection(events)

        self.assertEqual(projection["context_access"]["read_tool_calls"], 2)
        self.assertEqual(
            projection["tasks"][0]["context_access"][
                "exact_on_demand_read_characters"
            ],
            420,
        )
        self.assertTrue(projection["coverage"]["context_access"])


def _tool(
    name: str,
    payload: dict[str, str],
    *,
    status: str = "completed",
) -> dict[str, object]:
    return {
        "type": "tool",
        "tool": name,
        "state": {"status": status, "input": payload},
    }


if __name__ == "__main__":
    unittest.main()
