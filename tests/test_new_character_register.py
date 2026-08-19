from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from literary_engineering_studio_engine.new_character_register import (
    new_character_register_issues,
)


class NewCharacterRegisterTests(unittest.TestCase):
    def test_review_accepts_natural_aliases_for_a_formal_character(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            character = root / "characters" / "lin-huan.yaml"
            character.parent.mkdir(parents=True)
            character.write_text(
                "character_id: lin-huan\nname: 林桓\nrole: 主角——轨道维修员\n",
                encoding="utf-8",
            )
            payload = {
                "new_character_register": {
                    "status": "ephemeral_only",
                    "introduced": [
                        {
                            "character": "林桓",
                            "type": "existing_major_participant",
                        }
                    ],
                    "ephemeral_waivers": [
                        {
                            "character": "林曦",
                            "type": "referenced_only",
                            "waiver": "仅在记忆中被提及。",
                        }
                    ],
                    "blocking_issues": [],
                }
            }

            self.assertEqual(
                new_character_register_issues(payload, root, mode="review"), []
            )

    def test_unresolved_alias_does_not_become_formal_by_declaration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = {
                "new_character_register": {
                    "status": "ephemeral_only",
                    "introduced": [
                        {
                            "character": "陌生人",
                            "type": "existing_major_participant",
                        }
                    ],
                    "ephemeral_waivers": [],
                    "blocking_issues": [],
                }
            }

            issues = new_character_register_issues(payload, root, mode="review")

            self.assertTrue(any("waiver_reason" in item for item in issues))


if __name__ == "__main__":
    unittest.main()
