from __future__ import annotations

import hashlib
import unittest

from literary_engineering_studio.runtime.context_cache import ContextCacheKey
from literary_engineering_studio.runtime.prepared_context_cache import (
    PreparedContextCache,
)
from literary_engineering_studio.runtime.prompt_context import (
    PreparedPromptContext,
)


def _key(scope_id: str) -> ContextCacheKey:
    return ContextCacheKey(
        project_revision=f"project-{scope_id}",
        scope_kind="scene",
        scope_id=scope_id,
        canon_digest="canon-1",
        character_state_digest="state-1",
        style_mount_hash="style-1",
        word_budget_revision="budget-1",
        rhythm_bridge_hash="rhythm-1",
        task_role="main-review-agent",
        task_kind="platform-agent-review:candidate-review",
    )


def _context(text: str) -> PreparedPromptContext:
    return PreparedPromptContext(
        rendered=text,
        included_paths=("scene.md",),
        omitted_paths=(),
        character_count=len(text),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


class PreparedContextCacheTests(unittest.TestCase):
    def test_roundtrip_and_lru_eviction_are_bounded(self):
        cache = PreparedContextCache(enabled=True, max_entries=1)
        first = _key("scene_0001")
        second = _key("scene_0002")
        cache.put(first, _context("first"))
        self.assertEqual(cache.get(first), _context("first"))

        cache.put(second, _context("second"))

        self.assertIsNone(cache.get(first))
        self.assertEqual(cache.get(second), _context("second"))
        status = cache.status()
        self.assertEqual(status["entries"], 1)
        self.assertEqual(status["evictions"], 1)

    def test_disabled_cache_keeps_no_content(self):
        cache = PreparedContextCache(enabled=False, max_entries=1)
        cache.put(_key("scene_0001"), _context("private prose"))

        self.assertIsNone(cache.get(_key("scene_0001")))
        self.assertEqual(cache.status()["entries"], 0)

    def test_task_allowlist_limits_enabled_cache(self):
        cache = PreparedContextCache(
            enabled=True,
            routes=("scene-development",),
            states=("candidate-review",),
        )

        self.assertTrue(cache.allows("scene-development", "candidate-review"))
        self.assertFalse(cache.allows("scene-development", "candidate-generation-provenance"))
        self.assertFalse(cache.allows("review-and-audit", "candidate-review"))


if __name__ == "__main__":
    unittest.main()
