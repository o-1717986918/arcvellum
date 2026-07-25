from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config


class ApiRouteSurfaceTests(unittest.TestCase):
    def test_public_route_families_remain_available_after_api_module_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = default_config()
            config["application"]["data_root"] = str(root)
            config["application"]["database_path"] = str(root / "studio.sqlite3")
            config["application"]["projects_root"] = str(root / "projects")
            config["worker"]["runs_root"] = str(root / "runs")
            config["agent_runners"]["opencode"]["data_root"] = str(root)
            app = create_app(config)
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
            ("GET", "/archive/tree"),
            ("GET", "/archive/assets/{asset_id}"),
            ("POST", "/archive/assets/{asset_id}/commit"),
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
