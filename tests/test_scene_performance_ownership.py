from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_performance_ownership import unlicensed_scene_dialogue
from literary_engineering_studio_engine.public.literary import CreativeResult, SceneDelta
from tests.test_lean_kernel_v2_pi_runtime import _brief


def _materials() -> str:
    return "一级角色素材\n" + json.dumps({"actor_entries": [
        {"speaker": "character/protagonist", "spoken": "信……我拿的。你拿去看。"},
        {"speaker": "character/sister", "spoken": "门我没关。信呢？"},
    ]}, ensure_ascii=False)


class ScenePerformanceOwnershipTests(unittest.TestCase):
    def test_quote_check_allows_actor_fragments_but_not_new_dialogue(self) -> None:
        self.assertEqual(unlicensed_scene_dialogue("他说：“信……我拿的。”她问：“信呢？”", _materials()), [])
        self.assertEqual(unlicensed_scene_dialogue("他说：“饭在锅里。”", _materials()), ["饭在锅里。"])
        self.assertEqual(unlicensed_scene_dialogue("她闻到潮气，想起去年。", _materials()), [])
        self.assertEqual(unlicensed_scene_dialogue("她想起那句“原谅”，心里仍不肯信。", _materials()), [])
        self.assertEqual(unlicensed_scene_dialogue("她想着“信里有没有我”，没有问出口。", _materials()), [])

    def test_repairs_use_original_material_and_reject_persistent_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = PiSceneTransactionRuntime({}, project_root=root, data_root=root / ".studio")
            candidate = CreativeResult("她说：“饭在锅里。”", "初稿", SceneDelta())
            good = json.dumps({"prose": "他说：“信……我拿的。”", "decision_summary": "修订", "scene_delta": {}}, ensure_ascii=False)
            bad = json.dumps({"prose": "她又说：“去吃饭。”", "decision_summary": "修订", "scene_delta": {}}, ensure_ascii=False)
            with patch.object(runtime, "_run", return_value=good) as run:
                result = runtime._repair_actor_dialogue("tx", _brief(), candidate, _materials(), "", "")
                self.assertEqual(unlicensed_scene_dialogue(result.prose, _materials()), [])
                self.assertIn("饭在锅里", run.call_args.args[0])
                self.assertIn("一级角色素材", run.call_args.args[0])
            with patch.object(runtime, "_run", return_value=bad) as run, self.assertRaisesRegex(RuntimeError, "after two repairs"):
                runtime._repair_actor_dialogue("tx", _brief(), candidate, _materials(), "", "")
            self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
