from __future__ import annotations

import unittest

from literary_engineering_studio.runtime.context_cache import (
    ContextCacheKey,
    cache_key_violations,
    context_cache_key_fingerprint,
    partition_reusable,
)


def _key(**overrides):
    base = dict(
        project_revision="rev-1",
        scope_kind="scene",
        scope_id="scene_0001",
        canon_digest="canon-1",
        character_state_digest="state-1",
        style_mount_hash="style-1",
        word_budget_revision="budget-1",
        rhythm_bridge_hash="rhythm-1",
        task_role="writer",
        task_kind="formal_scene_prose",
    )
    base.update(overrides)
    return ContextCacheKey(**base)




class ContextCacheKeyTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_sensitive_to_identity_fields(self):
        first = context_cache_key_fingerprint(_key())
        second = context_cache_key_fingerprint(_key())
        changed = context_cache_key_fingerprint(_key(canon_digest="canon-2"))

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_missing_fields_are_reported(self):
        violations = cache_key_violations(_key(project_revision="", scope_id=""))

        self.assertEqual(len(violations), 2)
        self.assertEqual({item.code for item in violations}, {"missing-field"})

    def test_invalid_scope_kind_is_reported(self):
        violations = cache_key_violations(_key(scope_kind="book"))

        self.assertEqual({item.code for item in violations}, {"invalid-scope-kind"})

    def test_partition_reuse_requires_exact_identity(self):
        self.assertTrue(partition_reusable(_key(), _key()))
        self.assertFalse(
            partition_reusable(_key(), _key(style_mount_hash="style-2"))
        )
        self.assertFalse(
            partition_reusable(_key(), _key(task_role="reviewer"))
        )




if __name__ == "__main__":
    unittest.main()
