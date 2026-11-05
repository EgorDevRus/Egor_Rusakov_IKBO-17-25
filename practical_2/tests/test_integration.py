"""Integration tests against the bundled example repositories."""

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
import xml.etree.ElementTree as ET
from pathlib import Path

from cargo_deps.cli import run

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = PROJECT_ROOT / "examples"


class ExampleRepositoryTest(unittest.TestCase):
    """Render every bundled example and inspect its output."""

    def setUp(self):
        """Prepare the test fixture."""
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)

    def render(self, repository: str, *extra):
        """Check render."""
        output = self.directory / f"{repository}.svg"
        arguments = [
            "-p", "A",
            "-r", str(EXAMPLES / f"{repository}.txt"),
            "-m", "test",
            "-o", str(output),
            "--no-config",
            *extra,
        ]
        with redirect_stdout(io.StringIO()):
            with redirect_stderr(io.StringIO()):
                code = run(arguments)
        self.assertEqual(code, 0)
        ET.parse(output)
        return output

    def test_simple_example(self):
        """Check simple example."""
        self.render("simple", "--ascii", "tree")

    def test_cyclic_example(self):
        """Check cyclic example."""
        self.render("cycles", "--load-order")

    def test_filter_example(self):
        """Check filter example."""
        self.render("filter", "--filter", "X")

    def test_complex_example(self):
        """Check complex example."""
        self.render("complex", "--ascii", "tree")

    def test_all_examples_are_readable(self):
        """Check all examples are readable."""
        for path in EXAMPLES.glob("*.txt"):
            self.assertGreater(path.stat().st_size, 0)
