from __future__ import annotations

from dataclasses import dataclass
import unittest

from literary_engineering_studio.protocols.canonical_json import (
    canonical_json_bytes,
    canonical_json_digest,
)


class CanonicalJsonTests(unittest.TestCase):
    def test_bytes_and_digest_are_stable_across_insertion_order(self):
        left = {"b": 2, "a": "中文"}
        right = {"a": "中文", "b": 2}

        self.assertEqual(canonical_json_bytes(left), b'{"a":"\xe4\xb8\xad\xe6\x96\x87","b":2}')
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        self.assertEqual(
            canonical_json_digest(left),
            "257880e3654c372ee4dd773481c8ec19c1a0afe4d9d41078817518c4bd2aecc8",
        )

    def test_non_json_values_fail_instead_of_silently_stringifying(self):
        @dataclass(frozen=True)
        class Unsupported:
            value: str

        with self.assertRaises(TypeError):
            canonical_json_digest(Unsupported("x"))


if __name__ == "__main__":
    unittest.main()
