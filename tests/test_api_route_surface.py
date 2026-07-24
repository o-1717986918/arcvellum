import unittest

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config


class ApiRouteSurfaceTests(unittest.TestCase):
    def test_public_route_families_remain_available_after_api_module_extraction(self):
        app = create_app(default_config())
        def route_pairs(items, prefix: str = ""):
            for route in items:
                nested = getattr(route, "original_router", None)
                if nested is not None:
                    # Recent FastAPI versions retain an included APIRouter as
                    # a lazy route wrapper. Expand it so the public route
                    # contract stays meaningful as handlers move to routers.
                    nested_prefix = prefix + str(getattr(route, "prefix", "") or "")
                    yield from route_pairs(nested.routes, nested_prefix)
                    continue
                path = getattr(route, "path", None)
                for method in getattr(route, "methods", set()):
                    if path:
                        yield method, prefix + path

        routes = set(route_pairs(app.routes))
        expected = {
            ("GET", "/health"),
            ("GET", "/application/bootstrap"),
            ("GET", "/application/bootstrap/stream"),
            ("GET", "/help"),
            ("POST", "/desktop/session"),
            ("GET", "/agent-runners"),
            ("GET", "/model-connections"),
            ("PUT", "/model-connections/opencode/model"),
            ("GET", "/projects"),
            ("GET", "/projects/default-location"),
            ("POST", "/projects/open"),
            ("POST", "/projects/directions"),
            ("POST", "/projects/create"),
            ("GET", "/workflow/dashboard"),
            ("GET", "/workflow/dashboard/stream"),
            ("POST", "/workflow/human-choice"),
            ("POST", "/worker/run"),
            ("GET", "/worker/jobs/{job_id}/stream"),
            ("GET", "/agent-observability"),
            ("GET", "/project/library"),
            ("GET", "/reader/manifest"),
            ("GET", "/project/rhythm-plan"),
            ("PUT", "/project/rhythm-plan"),
            ("GET", "/narrative/projection/v3"),
            ("GET", "/narrative/stream/v3"),
            ("GET", "/project/delivery"),
        }
        self.assertTrue(expected <= routes, expected - routes)


if __name__ == "__main__":
    unittest.main()
