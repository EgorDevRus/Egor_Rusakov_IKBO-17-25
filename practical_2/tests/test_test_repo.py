"""Тесты текстового источника тестового репозитория."""

import unittest
from pathlib import Path

from cargo_deps.errors import SourceError
from cargo_deps.sources.test_repo import (
    TestRepositorySource,
    load_test_repository,
)
from tests.support import snake_case_setup, write_temp_repo


class TestRepositoryParsingTest(unittest.TestCase):
    """Проверяет формат файла тестового репозитория."""

    def test_parses_comments_commas_and_arrows(self):
        """Проверяет комментарии, запятые и стрелки."""
        path = write_temp_repo(
            self,
            "# комментарий\nA -> B, C\nB: D\nC:\nD:\n",
        )
        packages = load_test_repository(path)
        self.assertEqual(packages["A"], ("B", "C"))
        self.assertEqual(packages["C"], ())

    def test_rejects_lowercase_names(self):
        """Проверяет отказ при строчных именах."""
        path = write_temp_repo(self, "a: B\nB:\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_duplicate_declaration(self):
        """Проверяет отказ при повторном объявлении."""
        path = write_temp_repo(self, "A: B\nB:\nA: B\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_undeclared_dependency(self):
        """Проверяет отказ при необъявленной зависимости."""
        path = write_temp_repo(self, "A: B\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_empty_file(self):
        """Проверяет отказ при пустом файле."""
        path = write_temp_repo(self, "# только комментарий\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_bad_syntax(self):
        """Проверяет отказ при неверном синтаксисе."""
        path = write_temp_repo(self, "A B\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_duplicate_dependency(self):
        """Проверяет отказ при повторяющейся зависимости."""
        path = write_temp_repo(self, "A: B B\nB:\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)


@snake_case_setup
class TestRepositorySourceTest(unittest.TestCase):
    """Проверяет адаптер источника вокруг парсера."""

    def set_up(self):
        """Готовит тестовую среду."""
        self.path = write_temp_repo(self, "A: B\nB:\n")

    def test_root_and_dependencies(self):
        """Проверяет корневой пакет и зависимости."""
        source = TestRepositorySource(self.path)
        root = source.resolve_root("A")
        self.assertEqual(root.name, "A")
        self.assertIsNone(root.version)
        self.assertEqual(
            [dep.name for dep in source.dependencies(root)], ["B"]
        )

    def test_unknown_root(self):
        """Проверяет неизвестный корневой пакет."""
        source = TestRepositorySource(self.path)
        with self.assertRaises(SourceError):
            source.resolve_root("Z")

    def test_explicit_version_is_rejected(self):
        """Проверяет отказ от явной версии."""
        source = TestRepositorySource(self.path)
        with self.assertRaises(SourceError):
            source.resolve_root("A", "1.0.0")

    def test_dependency_resolution(self):
        """Проверяет разрешение зависимостей."""
        source = TestRepositorySource(self.path)
        from cargo_deps.models import Dependency

        self.assertIsNotNone(source.resolve_dependency(Dependency("B")))
        self.assertIsNone(source.resolve_dependency(Dependency("Z")))

    def test_missing_file(self):
        """Проверяет отсутствующий файл."""
        with self.assertRaises(SourceError):
            TestRepositorySource(Path("/nonexistent/repository.txt"))
