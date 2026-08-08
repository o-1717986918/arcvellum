from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration.graph_algorithms import (
    graph_ancestors,
    graph_descendants,
    nodes_are_ordered,
)


class GraphAlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.dependencies = {
            "context": (),
            "roleplay": ("context",),
            "branches": ("roleplay",),
            "prose": ("branches",),
            "review": ("prose",),
            "independent": (),
        }

    def test_ancestors_are_transitive(self):
        self.assertEqual(
            graph_ancestors("review", self.dependencies),
            {"context", "roleplay", "branches", "prose"},
        )

    def test_descendants_are_transitive(self):
        descendants = graph_descendants(self.dependencies)

        self.assertEqual(
            descendants["context"],
            {"roleplay", "branches", "prose", "review"},
        )
        self.assertEqual(descendants["independent"], set())

    def test_ordered_detects_either_direction(self):
        self.assertTrue(nodes_are_ordered("context", "review", self.dependencies))
        self.assertTrue(nodes_are_ordered("review", "context", self.dependencies))
        self.assertFalse(
            nodes_are_ordered("review", "independent", self.dependencies)
        )

    def test_cycles_terminate_without_including_the_origin(self):
        cyclic = {"a": ("b",), "b": ("a",)}

        self.assertEqual(graph_ancestors("a", cyclic), {"b"})


if __name__ == "__main__":
    unittest.main()
