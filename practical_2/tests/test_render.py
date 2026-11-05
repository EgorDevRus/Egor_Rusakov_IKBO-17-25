"""Tests for DOT, ASCII and SVG renderers."""

import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
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
from tests.support import StaticSource


def simple_graph() -> DependencyGraph:
    """Check simple graph."""
    source = StaticSource({
        "A": [Dependency("B"), Dependency("C")],
        "B": [Dependency("D")],
        "C": [Dependency("D")],
        "D": [],
    })
    return GraphBuilder(source).build("A")


def cycle_graph() -> DependencyGraph:
    """Check cycle graph."""
    source = StaticSource({
        "A": [Dependency("B")],
        "B": [Dependency("A")],
    })
    return GraphBuilder(source).build("A")


class DotRendererTest(unittest.TestCase):
    """Check Graphviz serialization."""

    def test_contains_nodes_and_edges(self):
        """Check contains nodes and edges."""
        dot = render_dot(simple_graph())
        self.assertIn("digraph dependencies", dot)
        self.assertIn('"A" -> "B"', dot)
        self.assertIn('"C" -> "D"', dot)

    def test_marks_cycles(self):
        """Check marks cycles."""
        dot = render_dot(cycle_graph())
        self.assertIn('label="cycle"', dot)
        self.assertIn("#c0392b", dot)

    def test_escapes_quotes_and_versions(self):
        """Check escapes quotes and versions."""
        graph = DependencyGraph(root="A")
        graph.add_node(GraphNode(ResolvedPackage("A", "1.2.3"), 0, True))
        graph.add_node(GraphNode(ResolvedPackage('B"x', "2.0.0"), 1))
        graph.add_edge(GraphEdge("A", 'B"x'))
        dot = render_dot(graph)
        self.assertIn('label="A\\n1.2.3"', dot)
        self.assertIn('B\\"x', dot)


class AsciiRendererTest(unittest.TestCase):
    """Check the plain-text tree."""

    def test_repeated_node_is_marked(self):
        """Check repeated node is marked."""
        text = render_ascii(simple_graph())
        self.assertEqual(
            text,
            "A\n"
            "├── B\n"
            "│   └── D\n"
            "└── C\n"
            "    └── D [already shown]",
        )

    def test_cycle_is_marked(self):
        """Check cycle is marked."""
        text = render_ascii(cycle_graph())
        self.assertIn("A [cycle]", text)
        self.assertEqual(text.count("A"), 2)

    def test_version_is_shown(self):
        """Check version is shown."""
        graph = DependencyGraph(root="A")
        graph.add_node(GraphNode(ResolvedPackage("A", "1.2.3"), 0, True))
        self.assertEqual(render_ascii(graph), "A 1.2.3")


class SvgRendererTest(unittest.TestCase):
    """Check SVG generation and the Graphviz fallback."""

    def setUp(self):
        """Prepare the test fixture."""
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: self._cleanup())
        self.output = self.directory / "graph.svg"

    def _cleanup(self):
        """Handle cleanup."""
        for path in self.directory.iterdir():
            path.unlink()
        self.directory.rmdir()

    def test_fallback_is_valid_xml(self):
        """Check fallback is valid xml."""
        graph = simple_graph()
        with patch("cargo_deps.render.svg.shutil.which", return_value=None):
            engine = write_svg("ignored", graph, self.output)
        self.assertEqual(engine, "fallback")
        ET.parse(self.output)
        self.assertIn("Dependency graph: A", self.output.read_text())

    def test_fallback_escapes_xml(self):
        """Check fallback escapes xml."""
        graph = DependencyGraph(root="A&B")
        graph.add_node(GraphNode(ResolvedPackage("A&B"), 0, True))
        with patch("cargo_deps.render.svg.shutil.which", return_value=None):
            write_svg("ignored", graph, self.output)
        ET.parse(self.output)

    def test_graphviz_is_preferred(self):
        """Check graphviz is preferred."""
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
        """Check graphviz failure falls back."""
        completed = subprocess.CompletedProcess(
            args=["dot"], returncode=1, stdout="", stderr="boom",
        )
        graph = simple_graph()
        with patch("cargo_deps.render.svg.shutil.which",
                   return_value="/usr/bin/dot"):
            with patch("cargo_deps.render.svg.subprocess.run",
                       return_value=completed):
                engine = write_svg("dot", graph, self.output)
        self.assertEqual(engine, "fallback")
        self.assertTrue(any("Graphviz" in item
                            for item in graph.warnings))

    def test_write_error_is_reported(self):
        """Check write error is reported."""
        graph = simple_graph()
        with patch("cargo_deps.render.svg.shutil.which", return_value=None):
            with patch.object(Path, "write_text", side_effect=OSError("x")):
                with self.assertRaises(RenderError):
                    write_svg("dot", graph, self.output)
