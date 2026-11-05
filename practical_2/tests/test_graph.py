"""Tests for BFS collection, cycles and load order."""

import unittest

from cargo_deps.graph import (
    GraphBuilder,
    cycle_packages,
    detect_cycles,
    load_order,
)
from cargo_deps.models import DEV, Dependency
from tests.support import StaticSource


class GraphBuilderTest(unittest.TestCase):
    """Check graph construction and traversal options."""

    def build(self, mapping, **options):
        """Check build."""
        return GraphBuilder(StaticSource(mapping), **options).build("A")

    def test_breadth_first_layers(self):
        """Check breadth first layers."""
        graph = self.build({
            "A": [Dependency("B"), Dependency("C")],
            "B": [Dependency("D")],
            "C": [Dependency("D")],
            "D": [],
        })
        self.assertEqual(graph.package_count, 4)
        self.assertEqual(graph.edge_count, 4)
        depths = {
            name: node.depth for name, node in graph.nodes.items()
        }
        self.assertEqual(depths, {"A": 0, "B": 1, "C": 1, "D": 2})
        self.assertTrue(graph.nodes["A"].is_root)

    def test_cycle_does_not_loop_forever(self):
        """Check cycle does not loop forever."""
        graph = self.build({
            "A": [Dependency("B")],
            "B": [Dependency("C")],
            "C": [Dependency("A")],
        })
        self.assertEqual(graph.package_count, 3)
        self.assertEqual(graph.cycles, {("C", "A")})
        self.assertEqual(cycle_packages(graph), {"A", "C"})

    def test_self_cycle(self):
        """Check self cycle."""
        graph = self.build({"A": [Dependency("A")]})
        self.assertEqual(graph.cycles, {("A", "A")})
        self.assertEqual(cycle_packages(graph), {"A"})

    def test_filter_skips_packages_and_subtrees(self):
        """Check filter skips packages and subtrees."""
        graph = self.build({
            "A": [Dependency("B"), Dependency("X1")],
            "B": [],
            "X1": [Dependency("X2")],
            "X2": [],
        }, filter_text="X")
        self.assertEqual(set(graph.nodes), {"A", "B"})
        self.assertEqual(graph.edge_count, 1)

    def test_root_survives_matching_filter(self):
        """Check root survives matching filter."""
        graph = self.build({"A": [Dependency("B")], "B": []},
                           filter_text="A")
        self.assertIn("A", graph.nodes)
        self.assertTrue(any("matches the filter" in item
                            for item in graph.warnings))

    def test_dev_and_optional_are_skipped_by_default(self):
        """Check dev and optional are skipped by default."""
        graph = self.build({
            "A": [
                Dependency("B", kind=DEV),
                Dependency("C", optional=True),
                Dependency("D"),
            ],
            "B": [], "C": [], "D": [],
        })
        self.assertEqual(set(graph.nodes), {"A", "D"})

    def test_dev_and_optional_can_be_included(self):
        """Check dev and optional can be included."""
        graph = self.build({
            "A": [
                Dependency("B", kind=DEV),
                Dependency("C", optional=True),
                Dependency("D"),
            ],
            "B": [], "C": [], "D": [],
        }, include_dev=True, include_optional=True)
        self.assertEqual(set(graph.nodes), {"A", "B", "C", "D"})

    def test_impossible_target_is_skipped(self):
        """Check impossible target is skipped."""
        graph = self.build({
            "A": [Dependency("B", target="cfg(any())")],
            "B": [],
        })
        self.assertEqual(set(graph.nodes), {"A"})

    def test_max_depth_limits_traversal(self):
        """Check max depth limits traversal."""
        graph = self.build({
            "A": [Dependency("B")],
            "B": [Dependency("C")],
            "C": [],
        }, max_depth=1)
        self.assertEqual(set(graph.nodes), {"A", "B"})
        self.assertTrue(graph.warnings)

    def test_unresolved_dependency_produces_warning(self):
        """Check unresolved dependency produces warning."""
        source = StaticSource({"A": [Dependency("B")]})
        graph = GraphBuilder(source).build("A")
        self.assertNotIn("B", graph.nodes)
        self.assertTrue(any("cannot resolve" in item
                            for item in graph.warnings))


class CycleDetectionTest(unittest.TestCase):
    """Check cycle detection on a manually built graph."""

    def test_detects_back_edges(self):
        """Check detects back edges."""
        source = StaticSource({
            "A": [Dependency("B")],
            "B": [Dependency("A")],
        })
        graph = GraphBuilder(source).build("A")
        self.assertEqual(detect_cycles(graph), {("B", "A")})


class LoadOrderTest(unittest.TestCase):
    """Check dependencies-first ordering."""

    def test_dependencies_are_loaded_before_dependents(self):
        """Check dependencies are loaded before dependents."""
        source = StaticSource({
            "A": [Dependency("B"), Dependency("C")],
            "B": [Dependency("D")],
            "C": [Dependency("D")],
            "D": [],
        })
        graph = GraphBuilder(source).build("A")
        order = load_order(graph)
        self.assertEqual(order[-1], "A")
        self.assertLess(order.index("D"), order.index("B"))
        self.assertLess(order.index("D"), order.index("C"))

    def test_cycle_is_broken(self):
        """Check cycle is broken."""
        source = StaticSource({
            "A": [Dependency("B")],
            "B": [Dependency("A")],
        })
        graph = GraphBuilder(source).build("A")
        order = load_order(graph)
        self.assertEqual(order, ["B", "A"])
