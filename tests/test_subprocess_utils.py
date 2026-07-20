import os
import sys
import unittest
from unittest.mock import patch

from literary_engineering_studio.subprocess_utils import hidden_process_options, run_hidden


class HiddenSubprocessTests(unittest.TestCase):
    def test_hidden_process_executes_and_captures_utf8(self):
        completed = run_hidden(
            [sys.executable, "-c", "print('可用')"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "可用")

    def test_windows_options_hide_console_window(self):
        with patch("literary_engineering_studio.subprocess_utils.os.name", "nt"):
            options = hidden_process_options()
        self.assertIn("creationflags", options)
        self.assertIn("startupinfo", options)

    def test_non_windows_options_are_empty(self):
        with patch("literary_engineering_studio.subprocess_utils.os.name", "posix"):
            self.assertEqual(hidden_process_options(), {})


if __name__ == "__main__":
    unittest.main()
