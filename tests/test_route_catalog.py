from pathlib import Path
import unittest

from literary_engineering_studio_engine.route_catalog import RouteCatalogCallbacks, route_definition


class RouteCatalogTests(unittest.TestCase):
    def test_catalog_wires_route_operations_without_route_blueprint_imports(self):
        def select(root: Path, payload: dict[str, object], scene: Path | str | None):
            return {"scene_id": "scene_0001"}

        def build(root: Path, route: str, state: dict[str, object]):
            return {"route": route, "state": state}

        def validate(root: Path, task: dict[str, object]):
            return [], []

        routes = [
            "scene-development",
            "longform-planning",
            "source-ingest",
            "style-engineering",
            "character-and-world-assets",
            "review-and-audit",
            "export-and-release",
        ]
        callbacks = RouteCatalogCallbacks(
            scene_selector=select,
            builders={route: build for route in routes},
            validators={route: validate for route in routes},
        )
        definition = route_definition(
            "scene_development",
            callbacks=callbacks,
            selectors={route: select for route in routes if route != "scene-development"},
        )
        self.assertEqual(definition.route, "scene-development")
        self.assertEqual(definition.select_work_item(Path("."), {}, None)["scene_id"], "scene_0001")
        with self.assertRaisesRegex(ValueError, "unsupported route"):
            route_definition("unknown", callbacks=callbacks, selectors={})


if __name__ == "__main__":
    unittest.main()
