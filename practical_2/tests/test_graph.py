"""Тесты сбора BFS, циклов и порядка загрузки."""

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
    """Проверяет построение графа и параметры обхода."""

    def build(self, mapping, **options):
        """Строит граф для отображения зависимостей."""
        return GraphBuilder(StaticSource(mapping), **options).build("A")

    def test_breadth_first_layers(self):
        """Проверяет уровни обхода в ширину."""
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
        """Проверяет, что цикл не приводит к бесконечному обходу."""
        graph = self.build({
            "A": [Dependency("B")],
            "B": [Dependency("C")],
            "C": [Dependency("A")],
        })
        self.assertEqual(graph.package_count, 3)
        self.assertEqual(graph.cycles, {("C", "A")})
        self.assertEqual(cycle_packages(graph), {"A", "C"})

    def test_self_cycle(self):
        """Проверяет петлю пакета на самого себя."""
        graph = self.build({"A": [Dependency("A")]})
        self.assertEqual(graph.cycles, {("A", "A")})
        self.assertEqual(cycle_packages(graph), {"A"})

    def test_filter_skips_packages_and_subtrees(self):
        """Проверяет, что фильтр пропускает пакеты и поддеревья."""
        graph = self.build({
            "A": [Dependency("B"), Dependency("X1")],
            "B": [],
            "X1": [Dependency("X2")],
            "X2": [],
        }, filter_text="X")
        self.assertEqual(set(graph.nodes), {"A", "B"})
        self.assertEqual(graph.edge_count, 1)

    def test_root_survives_matching_filter(self):
        """Проверяет, что корень сохраняется при совпадении с фильтром."""
        graph = self.build({"A": [Dependency("B")], "B": []},
                           filter_text="A")
        self.assertIn("A", graph.nodes)
        self.assertTrue(any("совпадает с фильтром" in item
                            for item in graph.warnings))

    def test_dev_and_optional_are_skipped_by_default(self):
        """Проверяет, что dev- и необязательные зависимости пропускаются."""
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
        """Проверяет, что dev- и необязательные зависимости включаются."""
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
        """Проверяет, что недостижимая цель пропускается."""
        graph = self.build({
            "A": [Dependency("B", target="cfg(any())")],
            "B": [],
        })
        self.assertEqual(set(graph.nodes), {"A"})

    def test_max_depth_limits_traversal(self):
        """Проверяет ограничение глубины обхода."""
        graph = self.build({
            "A": [Dependency("B")],
            "B": [Dependency("C")],
            "C": [],
        }, max_depth=1)
        self.assertEqual(set(graph.nodes), {"A", "B"})
        self.assertTrue(graph.warnings)

    def test_unresolved_dependency_produces_warning(self):
        """Проверяет предупреждение о неразрешённой зависимости."""
        source = StaticSource({"A": [Dependency("B")]})
        graph = GraphBuilder(source).build("A")
        self.assertNotIn("B", graph.nodes)
        self.assertTrue(any("не удалось разрешить" in item
                            for item in graph.warnings))


class CycleDetectionTest(unittest.TestCase):
    """Проверяет поиск циклов на вручную построенном графе."""

    def test_detects_back_edges(self):
        """Проверяет обнаружение обратных рёбер."""
        source = StaticSource({
            "A": [Dependency("B")],
            "B": [Dependency("A")],
        })
        graph = GraphBuilder(source).build("A")
        self.assertEqual(detect_cycles(graph), {("B", "A")})


class LoadOrderTest(unittest.TestCase):
    """Проверяет порядок, в котором зависимости идут первыми."""

    def test_dependencies_are_loaded_before_dependents(self):
        """Проверяет, что зависимости загружаются раньше зависимых."""
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
        """Проверяет разрыв цикла при построении порядка."""
        source = StaticSource({
            "A": [Dependency("B")],
            "B": [Dependency("A")],
        })
        graph = GraphBuilder(source).build("A")
        order = load_order(graph)
        self.assertEqual(order, ["B", "A"])
