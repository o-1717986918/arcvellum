import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.init_project import InitOptions, init_work_project
from literary_engineering_studio_engine.project_library import build_project_library


class ProjectLibraryLiteraryProjectionTests(unittest.TestCase):
    def test_library_projects_architecture_ledgers_decisions_and_context_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "library-projection"
            init_work_project(InitOptions(target=root, title="投影测试", work_type="novel", target_length=12000, premise="测试正式投影。"))

            self._write_json(
                root / "plot" / "story_architecture.candidate.json",
                {
                    "schema": "literary-engineering-workbench/story-architecture/v1",
                    "status": "complete",
                    "premise": "一位抄写员追查消失的航海图。",
                    "central_dramatic_question": "真相是否值得牺牲安稳？",
                    "change_vector": "从回避责任到承担代价。",
                    "midpoint_irreversibility": "航海图被公开。",
                    "endgame_choice": "公开自己伪造过的记录。",
                    "volume_obligations": ["第一卷建立谜团"],
                    "non_negotiable_payoffs": ["解释航海图来源"],
                },
            )
            self._write_json(
                root / "reviews" / "longform" / "story_architecture_review.json",
                {"verdict": "pass"},
            )
            self._write_json(
                root / "plot" / "reader_questions" / "ledger.json",
                {
                    "reader_questions": [
                        {"id": "question-map", "content": "航海图为何被涂改？", "status": "open", "last_advanced_at": "scene_0001"}
                    ]
                },
            )
            self._write_json(
                root / "plot" / "promises" / "ledger.json",
                {
                    "promises": [
                        {"id": "promise-key", "content": "钥匙会在第三章兑现。", "status": "pending", "due_window": "chapter_0003"}
                    ]
                },
            )
            self._write_json(
                root / "workflow" / "human_choices" / "state-choice.json",
                {
                    "choice_id": "state-choice",
                    "decision_type": "state_patch_confirmation",
                    "selected": "批准人物状态写回",
                    "route": "scene-development",
                    "target": {"scene_id": "scene_0001"},
                    "consumed": True,
                    "status": "submitted",
                },
            )
            self._write_json(
                root / "memory" / "context_packets" / "scene_0001.trace.json",
                {"schema": "literary-engineering-workbench/context-trace/v1", "scene_id": "scene_0001"},
            )

            library = build_project_library(root)
            sections = library["sections"]
            self.assertEqual(sections["story_architecture"][0]["facts"][4]["value"], "pass")
            self.assertEqual({item["title"] for item in sections["continuity"]}, {"航海图为何被涂改？", "钥匙会在第三章兑现。"})
            self.assertEqual(sections["decisions"][0]["title"], "批准人物状态写回")
            self.assertEqual(sections["context_health"][0]["status"], "stale")
            self.assertGreaterEqual(library["counts"]["continuity"], 2)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
