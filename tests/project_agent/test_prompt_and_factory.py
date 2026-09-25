from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.integrations.pi_worker.installation import PiWorkerInstallation
from literary_engineering_studio.project_agent.factory import build_project_agent_runtime
from literary_engineering_studio.project_agent.prompt_policy import (
    delegated_goal_followup_prompt,
    system_prompt,
)


class ProjectAgentPromptAndFactoryTests(unittest.TestCase):
    def test_followup_keeps_evidence_without_fixed_status_template(self):
        prompt = delegated_goal_followup_prompt(
            "写完这一章", "已经启动", {"status": "complete", "run_id": "run-1"}
        )

        self.assertIn("主要人物处境、未决线索、连续性风险和下一步只选与本次成果有关", prompt)
        self.assertNotIn("不按固定清单写回执", prompt)
        self.assertIn("project_overview", prompt)
        self.assertIn("形式门禁通过也不能代替整书阅读判断", prompt)
        self.assertNotIn("先概括已经发生的故事变化、主要人物处境", prompt)

    def test_persona_does_not_force_editorial_review_on_every_answer(self):
        prompt = system_prompt({"name": "严谨总编", "prompt": "优先检查结构。"}, write_enabled=True)

        self.assertIn("根据用户是在提问、讨论创作、要求行动还是查看里程碑", prompt)
        self.assertNotIn("不强制每次进行编辑审稿", prompt)
        self.assertIn("优先检查结构。", prompt)
        self.assertIn("记录方向时区分三层", prompt)
        self.assertIn("用户要求高自由度时", prompt)
        self.assertIn("不主动把这些口味写进高优先级创作方向", prompt)
        self.assertIn("不能写成长篇高优先级方向替主创定稿", prompt)
        self.assertIn("当前作品会话优先使用 catalog 的 current_work_id", prompt)
        self.assertIn("三到五个能共同塑造此人说话和互动的核心项", prompt)

    def test_project_agent_thinking_is_independent_of_worker_thinking(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = root / "main.js"
            entrypoint.touch()
            installation = PiWorkerInstallation("node", entrypoint, "test")
            settings = {"model": "deepseek/deepseek-v4-flash", "thinking": "low"}
            with patch(
                "literary_engineering_studio.project_agent.factory.locate_pi_worker",
                return_value=installation,
            ):
                runtime = build_project_agent_runtime({"agent_runners": {"pi-worker": settings}}, root)
                self.assertEqual(runtime.command[runtime.command.index("--thinking") + 1], "xhigh")

                settings["project_agent_thinking"] = "high"
                runtime = build_project_agent_runtime({"agent_runners": {"pi-worker": settings}}, root)
                self.assertEqual(runtime.command[runtime.command.index("--thinking") + 1], "high")
