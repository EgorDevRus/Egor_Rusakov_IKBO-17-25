"""Тесты рендереров DOT, ASCII и SVG."""

import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path
from unittest.mock import patch

from cargo_deps.errors import RenderError
from cargo_deps.graph import GraphBuilder
from cargo_deps.models import (
    Dependency,
    DependencyGraph,
    GraphEdge,
    GraphNode,
    ResolvedPackage,
)
from cargo_deps.render import render_ascii, render_dot, write_svg
from tests.support import StaticSource, snake_case_setup


def simple_graph() -> DependencyGraph:
    """Строит простой граф для тестов."""
    source = StaticSource({
        "A": [Dependency("B"), Dependency("C")],
        "B": [Dependency("D")],
        "C": [Dependency("D")],
        "D": [],
    })
    return GraphBuilder(source).build("A")


def cycle_graph() -> DependencyGraph:
    """Строит граф с циклом для тестов."""
    source = StaticSource({
        "A": [Dependency("B")],
        "B": [Dependency("A")],
    })
    return GraphBuilder(source).build("A")


class DotRendererTest(unittest.TestCase):
    """Проверяет сериализацию в Graphviz."""

    def test_contains_nodes_and_edges(self):
        """Проверяет наличие узлов и рёбер."""
        dot = render_dot(simple_graph())
        self.assertIn("digraph dependencies", dot)
        self.assertIn('"A" -> "B"', dot)
        self.assertIn('"C" -> "D"', dot)

    def test_marks_cycles(self):
        """Проверяет пометку циклов."""
        dot = render_dot(cycle_graph())
        self.assertIn('label="цикл"', dot)
        self.assertIn("#c0392b", dot)

    def test_escapes_quotes_and_versions(self):
        """Проверяет экранирование кавычек и версий."""
        graph = DependencyGraph(root="A")
        graph.add_node(GraphNode(ResolvedPackage("A", "1.2.3"), 0, True))
        graph.add_node(GraphNode(ResolvedPackage('B"x', "2.0.0"), 1))
        graph.add_edge(GraphEdge("A", 'B"x'))
        dot = render_dot(graph)
        self.assertIn('label="A\\n1.2.3"', dot)
        self.assertIn('B\\"x', dot)


class AsciiRendererTest(unittest.TestCase):
    """Проверяет текстовое дерево."""

    def test_repeated_node_is_marked(self):
        """Проверяет пометку повторно встреченного узла."""
        text = render_ascii(simple_graph())
        self.assertEqual(
            text,
            "A\n"
            "├── B\n"
            "│   └── D\n"
            "└── C\n"
            "    └── D [уже показан]",
        )

    def test_cycle_is_marked(self):
        """Проверяет пометку цикла."""
        text = render_ascii(cycle_graph())
        self.assertIn("A [цикл]", text)
        self.assertEqual(text.count("A"), 2)

    def test_version_is_shown(self):
        """Проверяет вывод версии."""
        graph = DependencyGraph(root="A")
        graph.add_node(GraphNode(ResolvedPackage("A", "1.2.3"), 0, True))
        self.assertEqual(render_ascii(graph), "A 1.2.3")


@snake_case_setup
class SvgRendererTest(unittest.TestCase):
    """Проверяет создание SVG и резервный рендерер."""

    def set_up(self):
        """Готовит тестовую среду."""
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: self._cleanup())
        self.output = self.directory / "graph.svg"

    def _cleanup(self):
        """Удаляет временные файлы после теста."""
        for path in self.directory.iterdir():
            path.unlink()
        self.directory.rmdir()

    def test_fallback_is_valid_xml(self):
        """Проверяет, что резервный SVG является корректным XML."""
        graph = simple_graph()
        with patch("cargo_deps.render.svg.shutil.which", return_value=None):
            engine = write_svg("ignored", graph, self.output)
        self.assertEqual(engine, "встроенный")
        element_tree.parse(self.output)
        self.assertIn("Граф зависимостей: A", self.output.read_text())

    def test_fallback_escapes_xml(self):
        """Проверяет экранирование XML в резервном рендерере."""
        graph = DependencyGraph(root="A&B")
        graph.add_node(GraphNode(ResolvedPackage("A&B"), 0, True))
        with patch("cargo_deps.render.svg.shutil.which", return_value=None):
            write_svg("ignored", graph, self.output)
        element_tree.parse(self.output)

    def test_graphviz_is_preferred(self):
        """Проверяет, что Graphviz используется при наличии."""
        completed = subprocess.CompletedProcess(
            args=["dot"], returncode=0,
            stdout='<?xml version="1.0"?><svg/>',
        )
        graph = simple_graph()
        with patch("cargo_deps.render.svg.shutil.which",
                   return_value="/usr/bin/dot"):
            with patch("cargo_deps.render.svg.subprocess.run",
                       return_value=completed):
                engine = write_svg("dot", graph, self.output)
        self.assertEqual(engine, "graphviz")
        self.assertIn("<svg", self.output.read_text())

    def test_graphviz_failure_falls_back(self):
        """Проверяет переход на резервный рендерер при ошибке Graphviz."""
        completed = subprocess.CompletedProcess(
            args=["dot"], returncode=1, stdout="", stderr="boom",
        )
        graph = simple_graph()
        with patch("cargo_deps.render.svg.shutil.which",
                   return_value="/usr/bin/dot"):
            with patch("cargo_deps.render.svg.subprocess.run",
                       return_value=completed):
                engine = write_svg("dot", graph, self.output)
        self.assertEqual(engine, "встроенный")
        self.assertTrue(any("Graphviz" in item
                            for item in graph.warnings))

    def test_write_error_is_reported(self):
        """Проверяет сообщение об ошибке записи."""
        graph = simple_graph()
        with patch("cargo_deps.render.svg.shutil.which", return_value=None):
            with patch.object(Path, "write_text", side_effect=OSError("x")):
                with self.assertRaises(RenderError):
                    write_svg("dot", graph, self.output)
