from __future__ import annotations

from pathlib import Path
import unittest

from scripts.verify_checkout_import import checkout_report


class CheckoutVerifierTests(unittest.TestCase):
    def test_current_test_process_imports_packages_from_this_checkout(self) -> None:
        root = Path(__file__).resolve().parents[1]

        report = checkout_report(root)

        self.assertTrue(report["ok"], report["outside_checkout"])
        self.assertEqual(report["repository"], str(root))


if __name__ == "__main__":
    unittest.main()
