from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from literary_engineering_studio.observability.scene_rehearsals import scene_rehearsal_detail, scene_rehearsal_index


def _transaction(transaction_id: str, scene_id: str = "scene_0001"):
    return SimpleNamespace(
        transaction_id=transaction_id, scene_id=scene_id,
        status=SimpleNamespace(value="committed"), brief=SimpleNamespace(objective="取回旧信"),
    )


class SceneRehearsalReadTests(unittest.TestCase):
    def test_history_exposes_public_turns_without_private_impulses(self):
        with tempfile.TemporaryDirectory() as directory:
            data_root = Path(directory)
            cache = data_root / "scene-transactions" / "tx-one"
            cache.mkdir(parents=True)
            (cache / "performance-interaction-session-test.json").write_text(json.dumps({
                "scene_id": "scene_0001",
                "directions": [{"turn": 1, "next_speaker": "许遥", "beat_id": "b1", "entry_ids": ["t1:1"]}],
                "actor_entries": [{"entry_id": "t1:1", "spoken": "信呢？", "first_person_action": "我把手伸出去。",
                                   "private_impulse": "我怕他骗我。"}],
                "environment": {"passages": [{"beat_id": "b1", "description": "雨落在窗沿。"}]},
                "initializations": {"许遥": "PRIVATE_PROMPT"},
            }, ensure_ascii=False), encoding="utf-8")
            own = _transaction("tx-one")
            self.assertEqual(scene_rehearsal_index(data_root, [own])[0]["turn_count"], 1)
            detail = scene_rehearsal_detail(data_root, [own], "tx-one")
            encoded = json.dumps(detail, ensure_ascii=False)
            self.assertIn("信呢？", encoded)
            self.assertIn("雨落在窗沿", encoded)
            self.assertNotIn("我怕他骗我", encoded)
            self.assertNotIn("PRIVATE_PROMPT", encoded)
            with self.assertRaisesRegex(ValueError, "does not belong"):
                scene_rehearsal_detail(data_root, [_transaction("tx-other")], "tx-one")


if __name__ == "__main__":
    unittest.main()
