from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.platform_agent_tasks import write_platform_style_prompt_eval_task
import literary_engineering_studio_engine.task_registry as task_registry
from literary_engineering_studio_engine.workflow_state import _style_engineering_state


def _quality_prompt() -> str:
    blocks = [
        "使用身份与适用边界",
        "核心风格机制",
        "叙述距离与视角",
        "句法与节奏",
        "标点节奏",
        "意象与感官调度",
        "心理呈现与行为因果",
        "对白与语气",
        "AI腔控制",
        "禁止倾向",
        "输出自检",
    ]
    rule = "叙述应先交代可观察动作，再让心理从选择和代价中显露。句号与逗号按语义层级分配，不使用机械对照和破折号变体。"
    return "\n\n".join(f"## {block}\n\n{rule}" for block in blocks) + "\n"


def _profile(root: Path, *, quality: bool = True) -> Path:
    profile = root / "style" / "author" / "default"
    (profile / "corpus").mkdir(parents=True)
    (profile / "style-profile.md").write_text("# 风格档案\n", encoding="utf-8")
    (profile / "style_metrics.json").write_text("{}\n", encoding="utf-8")
    (profile / "corpus_manifest.yaml").write_text("sources: 1\n", encoding="utf-8")
    (profile / "corpus" / "reference.txt").write_text("潮声在旧城墙下停了一夜。第二天，人们才发现门锁上全是盐。\n" * 20, encoding="utf-8")
    prompt_task = profile / "style_prompt.agent_tasks.md"
    prompt_task.write_text("# style prompt\n", encoding="utf-8")
    (profile / "style_prompt.md").write_text(_quality_prompt() if quality else "## 使用身份\n写得好看。\n", encoding="utf-8")
    (profile / "style_prompt.agent.json").write_text("{}\n", encoding="utf-8")
    write_agent_completion_marker(prompt_task, root=root, handled_by="main-agent")
    return profile


def _write_current_score(profile: Path, score: float) -> None:
    eval_dir = profile / "evaluation_results" / "formal"
    candidate = eval_dir / "platform_agent_candidate.md"
    payload = {
        "schema": "literary-engineering-workbench/style-eval/v0.1",
        "overall_score": score,
        "risk_level": "acceptable" if score >= 45 else "low_similarity",
        "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
    }
    (eval_dir / "style_eval_current.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (eval_dir / "style_eval_current.md").write_text(f"# Score\n\n{score}\n", encoding="utf-8")


class StyleEvaluationLoopTests(unittest.TestCase):
    def test_low_quality_initial_prompt_can_finish_then_route_to_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            profile = _profile(root, quality=False)

            errors, _notes = task_registry._style_engineering_state_gate_validation(
                root,
                {"current_state": "style-prompt-agent-task", "profile_dir": profile.relative_to(root).as_posix()},
            )
            self.assertEqual(errors, [])
            self.assertEqual(_style_engineering_state(root, profile)["current_step"], "style-prompt-quality")

    def test_formal_evaluation_has_concrete_prepare_agent_score_and_revision_states(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_yaml = root / "project.yaml"
            project_yaml.write_text("title: 潮线\npremise: 一个守门人发现城市边界正在后退。\n", encoding="utf-8")
            profile = _profile(root)
            reference = profile / "corpus" / "reference.txt"

            state = _style_engineering_state(root, profile)
            self.assertEqual(state["current_step"], "style-eval-task-file")
            prepare = task_registry._build_style_engineering_task_payload(root, "style-engineering", state)
            self.assertNotIn("<reference>", prepare["command"])
            self.assertIn("--mode blind-review", prepare["command"])

            eval_dir = profile / "evaluation_results" / "formal"
            write_platform_style_prompt_eval_task(
                profile,
                reference=reference,
                task_input=project_yaml,
                mode="blind-review",
                output_dir=eval_dir,
            )
            self.assertEqual(_style_engineering_state(root, profile)["current_step"], "style-eval-agent-task")

            candidate = eval_dir / "platform_agent_candidate.md"
            candidate.write_text("守门人清晨换班时，发现城门外那根界桩向里挪了三步。没有人承认昨夜来过。\n" * 12, encoding="utf-8")
            (eval_dir / "platform_agent_candidate.prompt.json").write_text(
                json.dumps(
                    {
                        "mode": "blind-review",
                        "style_prompt": "style_prompt.md",
                        "reference": "corpus/reference.txt",
                        "input": "project.yaml",
                        "candidate": "platform_agent_candidate.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            write_agent_completion_marker(candidate.with_suffix(".agent_tasks.md"), root=root, handled_by="main-agent")
            self.assertEqual(_style_engineering_state(root, profile)["current_step"], "style-eval-score-file")

            _write_current_score(profile, 30)
            failed = _style_engineering_state(root, profile)
            self.assertEqual(failed["current_step"], "style-eval-revision")
            revision = task_registry._build_style_engineering_task_payload(root, "style-engineering", failed)
            self.assertIn(profile.relative_to(root).as_posix() + "/style_prompt.md", revision["repair_targets"])
            self.assertIn(candidate.relative_to(root).as_posix(), revision["repair_targets"])

            _write_current_score(profile, 80)
            self.assertEqual(_style_engineering_state(root, profile)["status"], "ready")


if __name__ == "__main__":
    unittest.main()
