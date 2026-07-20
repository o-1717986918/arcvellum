import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from literary_engineering_studio.api_server import create_app


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ApiServerTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_health_exposes_agent_runtimes_without_model_provider(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["core_ready"])
        self.assertEqual(payload["model_provider"], "disabled-by-architecture")
        self.assertEqual({item["runtime"] for item in payload["runtimes"]}, {"host-agent", "claude-code", "codex-cli"})

    def test_frontend_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Agent Studio", response.text)


if __name__ == "__main__":
    unittest.main()
