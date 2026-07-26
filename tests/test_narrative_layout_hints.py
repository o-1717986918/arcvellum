from __future__ import annotations

import unittest

from literary_engineering_studio.projections.narrative.layout_hints import (
    LAYOUT_HINT_SCHEMA,
    build_layout_hints,
)


class NarrativeLayoutHintTests(unittest.TestCase):
    def test_default_contract_is_read_only_disabled_and_empty(self) -> None:
        payload = build_layout_hints("spine", "book", [{"node_id": "scene:1"}])
        self.assertEqual(payload["schema"], LAYOUT_HINT_SCHEMA)
        self.assertTrue(payload["policy"]["read_only"])
        self.assertFalse(payload["agent_layout_intent"]["enabled"])
        self.assertEqual(payload["agent_layout_intent"]["status"], "disabled")
        self.assertEqual(payload["node_offsets"], [])


if __name__ == "__main__":
    unittest.main()
