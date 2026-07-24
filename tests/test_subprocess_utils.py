import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

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
        startupinfo = MagicMock()
        startupinfo.dwFlags = 0
        with (
            patch("literary_engineering_studio.subprocess_utils.os.name", "nt"),
            patch.object(subprocess, "STARTUPINFO", return_value=startupinfo, create=True),
            patch.object(subprocess, "STARTF_USESHOWWINDOW", 1, create=True),
            patch.object(subprocess, "SW_HIDE", 0, create=True),
            patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True),
        ):
            options = hidden_process_options()
        self.assertIn("creationflags", options)
        self.assertIn("startupinfo", options)
        self.assertEqual(options["creationflags"], 0x08000000)
        self.assertEqual(startupinfo.dwFlags, 1)
        self.assertEqual(startupinfo.wShowWindow, 0)

    def test_non_windows_options_are_empty(self):
        with patch("literary_engineering_studio.subprocess_utils.os.name", "posix"):
            self.assertEqual(hidden_process_options(), {})


if __name__ == "__main__":
    unittest.main()
