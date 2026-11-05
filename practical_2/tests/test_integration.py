"""Интеграционные тесты на примерах репозиториев из репозитория."""

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
import xml.etree.ElementTree as ET
from pathlib import Path

from cargo_deps.cli import run
from tests.support import snake_case_setup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = PROJECT_ROOT / "examples"


@snake_case_setup
class ExampleRepositoryTest(unittest.TestCase):
    """Строит все примеры и проверяет результаты."""

    def set_up(self):
        """Готовит тестовую среду."""
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)

    def render(self, repository: str, *extra):
        """Строит граф для примера ``repository``."""
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
        """Проверяет простой пример."""
        self.render("simple", "--ascii", "tree")

    def test_cyclic_example(self):
        """Проверяет пример с циклами."""
        self.render("cycles", "--load-order")

    def test_filter_example(self):
        """Проверяет пример с фильтрацией."""
        self.render("filter", "--filter", "X")

    def test_complex_example(self):
        """Проверяет сложный пример."""
        self.render("complex", "--ascii", "tree")

    def test_all_examples_are_readable(self):
        """Проверяет, что все примеры читаются."""
        for path in EXAMPLES.glob("*.txt"):
            self.assertGreater(path.stat().st_size, 0)
