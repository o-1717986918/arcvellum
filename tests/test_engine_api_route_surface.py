import unittest

from literary_engineering_studio_engine.api_server import create_app


class EngineApiRouteSurfaceTests(unittest.TestCase):
    def test_legacy_endpoint_families_survive_router_extraction(self):
        paths = set(create_app().openapi()["paths"])
        required = {
            "/",
            "/health",
            "/config",
            "/style-lab/library",
            "/project/library",
            "/workflow/run",
            "/workflow/dashboard",
            "/workflow/human-choice",
            "/canon/apply",
            "/agent/run",
            "/director/chat",
            "/asset/create",
            "/workflow/approve",
        }
        self.assertTrue(required.issubset(paths))
