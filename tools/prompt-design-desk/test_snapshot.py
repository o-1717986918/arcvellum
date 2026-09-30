"""Snapshot fidelity and safe embedding of arbitrary source text."""

from hashlib import sha256
import json
import re
import unittest

from build_snapshot import read_library, render_html


class SnapshotTests(unittest.TestCase):
    def test_all_references_have_full_text_and_traceable_versions(self):
        library = read_library()
        self.assertEqual(len(library["slots"]), 26)
        for source in library["sources"].values():
            self.assertTrue(source["text"])
            self.assertEqual(source["sha256"], sha256(source["text"].encode("utf-8")).hexdigest())
        html = render_html(library)
        embedded = re.search(r'<script id="promptLibrary" type="application/json">(.*?)</script>', html, re.S)[1]
        self.assertEqual(json.loads(embedded), library)

    def test_source_markup_cannot_close_the_json_script(self):
        library = read_library()
        hostile = '</script><img src=x onerror="alert(1)"><script>__DESK_FILES__'
        library["sources"]["scene.v2.creator.identity"]["text"] = hostile
        html = render_html(library)
        self.assertNotIn(hostile, html)
        self.assertEqual(html.count("</script>"), 4)
        embedded = re.search(r'<script id="promptLibrary" type="application/json">(.*?)</script>', html, re.S)[1]
        self.assertEqual(json.loads(embedded)["sources"]["scene.v2.creator.identity"]["text"], hostile)


if __name__ == "__main__":
    unittest.main()
