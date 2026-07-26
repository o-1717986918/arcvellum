from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.runtime.prompt_context import (
    build_prepared_prompt_context,
)


class PreparedPromptContextTests(unittest.TestCase):
    def test_includes_only_complete_authorized_text_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "small.md").write_text("complete evidence", encoding="utf-8")
            (root / "large.md").write_text("x" * 200, encoding="utf-8")
            (root / "binary.bin").write_bytes(b"a\x00b")

            bundle = build_prepared_prompt_context(
                root,
                ("small.md", "large.md", "binary.bin", "missing.md"),
                max_characters=200,
            )

            self.assertEqual(bundle.included_paths, ("small.md",))
            self.assertEqual(
                bundle.omitted_paths,
                ("large.md", "binary.bin", "missing.md"),
            )
            self.assertIn("complete evidence", bundle.rendered)
            self.assertNotIn("x" * 20, bundle.rendered)
            self.assertEqual(bundle.character_count, len(bundle.rendered))
            self.assertEqual(len(bundle.sha256), 64)

    def test_deduplicates_normalized_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.md").write_text("evidence", encoding="utf-8")

            bundle = build_prepared_prompt_context(
                root,
                ("source.md", "source.md"),
            )

            self.assertEqual(bundle.included_paths, ("source.md",))


if __name__ == "__main__":
    unittest.main()
