import unittest

from literary_engineering_studio.cli import _is_loopback_host, _validate_serve_binding, _write_ready_file, build_parser


class CliSecurityTests(unittest.TestCase):
    def test_loopback_host_detection(self):
        self.assertTrue(_is_loopback_host("127.0.0.1"))
        self.assertTrue(_is_loopback_host("localhost"))
        self.assertTrue(_is_loopback_host("::1"))
        self.assertFalse(_is_loopback_host("0.0.0.0"))
        self.assertFalse(_is_loopback_host("192.168.1.9"))
        self.assertFalse(_is_loopback_host("studio.example.test"))

    def test_desktop_sidecar_arguments_are_accepted(self):
        args = build_parser().parse_args(
            ["serve", "--host", "127.0.0.1", "--port", "8791", "--parent-pid", "42"]
        )
        self.assertEqual(args.parent_pid, 42)

    def test_non_loopback_bind_requires_a_token(self):
        with self.assertRaisesRegex(ValueError, "without LES_API_TOKEN"):
            _validate_serve_binding("0.0.0.0", "")
        _validate_serve_binding("127.0.0.1", "")
        _validate_serve_binding("0.0.0.0", "test-token")

    def test_ready_file_is_atomic_and_declares_bound_sidecar_contract(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ready.json"
            with patch.dict(os.environ, {"LES_STARTUP_NONCE": "nonce-fixture"}):
                _write_ready_file(target, 43123)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["port"], 43123)
            self.assertEqual(payload["startup_nonce"], "nonce-fixture")
            self.assertEqual(payload["protocol_version"], "arcvellum-sidecar/v1")
