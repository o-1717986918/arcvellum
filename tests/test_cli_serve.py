"""Regression coverage for the frozen desktop sidecar entry point."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from literary_engineering_studio.cli import main


class CliServeTests(unittest.TestCase):
    def test_serve_passes_an_in_process_asgi_app_to_uvicorn(self):
        app = object()
        with patch("literary_engineering_studio.api_server.create_app", return_value=app) as create_app, patch(
            "uvicorn.run"
        ) as run:
            result = main(["serve", "--host", "127.0.0.1", "--port", "18792"])

        self.assertEqual(result, 0)
        create_app.assert_called_once_with()
        run.assert_called_once_with(app, host="127.0.0.1", port=18792)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
