from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.sandbox import SandboxManifest
from literary_engineering_studio.task_preflight import validate_task_outputs
from literary_engineering_studio_engine.public.literary import canon_patch_candidate_issues


SCHEMA = "literary-engineering-workbench/canon-patch-candidate/v0.1"


def _valid_payload() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "scene_id": "scene_0005",
        "canon_change": True,
        "no_canon_change_reason": "",
        "items": [
            {
                "type": "world_rule",
                "summary": "远航船只能在晨昏窗口穿过灰潮。",
                "source_evidence": ["drafts/scenes/scene_0005.md#灰潮窗口"],
                "target_files": ["canon/world_rules.yaml"],
                "risk_level": "medium",
                "requires_user_approval": True,
            }
        ],
    }


class CanonCandidateContractTests(unittest.TestCase):
    def test_accepts_change_and_no_change_contracts(self):
        self.assertEqual(canon_patch_candidate_issues(_valid_payload(), expected_scene_id="scene_0005"), ())

        no_change = {
            "schema": SCHEMA,
            "scene_id": "scene_0005",
            "canon_change": False,
            "no_canon_change_reason": "本场只兑现既有规则，没有形成新的持续事实。",
            "items": [],
        }
        self.assertEqual(canon_patch_candidate_issues(no_change, expected_scene_id="scene_0005"), ())

    def test_detects_real_nested_item_field_leak(self):
        payload = _valid_payload()
        payload["items"] = [payload["items"][0], {"type": "history/character"}]
        payload.update(
            {
                "summary": "错误地泄漏到根对象。",
                "source_evidence": "drafts/scenes/scene_0005.md#尾声",
                "target_files": ["canon/history.yaml"],
                "risk_level": "low",
                "requires_user_approval": True,
            }
        )

        paths = {issue.path for issue in canon_patch_candidate_issues(payload, expected_scene_id="scene_0005")}

        self.assertEqual(
            paths,
            {
                "items[1].summary",
                "items[1].source_evidence",
                "items[1].target_files",
                "items[1].risk_level",
                "items[1].requires_user_approval",
            },
        )

    def test_rejects_unsafe_canon_target(self):
        payload = _valid_payload()
        payload["items"][0]["target_files"] = ["../characters/protagonist.yaml"]

        paths = {issue.path for issue in canon_patch_candidate_issues(payload)}

        self.assertIn("items[0].target_files[0]", paths)


class CanonCandidatePreflightTests(unittest.TestCase):
    def test_nested_item_error_reaches_worker_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_root = Path(temporary)
            workspace = run_root / "workspace"
            (run_root / "baseline.json").write_text("{}\n", encoding="utf-8")
            relative = "canon/patches/scene_0005_canon_patch.json"
            target = workspace / relative
            target.parent.mkdir(parents=True)
            payload = _valid_payload()
            payload["items"].append({"type": "history/character"})
            target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            task = TaskPackage(
                project_root=run_root,
                task_json_path=run_root / "task.json",
                task_markdown_path=run_root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0005-canon-patch-json",
                    "route": "scene-development",
                    "scene_id": "scene_0005",
                    "current_state": "canon-patch-json",
                    "expected_outputs": [relative],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=run_root,
                workspace=workspace,
                prompt_path=run_root / "prompt.md",
                manifest_path=run_root / "manifest.json",
                baseline_path=run_root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            result = validate_task_outputs(task, sandbox)
            canon_issues = [issue for issue in result.issues if issue.code == "canon-patch-contract"]

            self.assertFalse(result.passed)
            self.assertEqual(len(canon_issues), 5)
            self.assertIn(
                f"{relative}#items[1].summary",
                {issue.path for issue in canon_issues},
            )
            self.assertTrue(all("同一个对象内" in issue.repair for issue in canon_issues))


if __name__ == "__main__":
    unittest.main()
