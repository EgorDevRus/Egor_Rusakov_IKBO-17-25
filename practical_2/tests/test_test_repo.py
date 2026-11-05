"""Tests for the text test-repository source."""

import unittest
from pathlib import Path

from cargo_deps.errors import SourceError
from cargo_deps.sources.test_repo import (
    TestRepositorySource,
    load_test_repository,
)
from tests.support import write_temp_repo


class TestRepositoryParsingTest(unittest.TestCase):
    """Check the test repository file format."""

    def test_parses_comments_commas_and_arrows(self):
        """Check parses comments commas and arrows."""
        path = write_temp_repo(
            self,
            "# comment\nA -> B, C\nB: D\nC:\nD:\n",
        )
        packages = load_test_repository(path)
        self.assertEqual(packages["A"], ("B", "C"))
        self.assertEqual(packages["C"], ())

    def test_rejects_lowercase_names(self):
        """Check rejects lowercase names."""
        path = write_temp_repo(self, "a: B\nB:\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_duplicate_declaration(self):
        """Check rejects duplicate declaration."""
        path = write_temp_repo(self, "A: B\nB:\nA: B\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_undeclared_dependency(self):
        """Check rejects undeclared dependency."""
        path = write_temp_repo(self, "A: B\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_empty_file(self):
        """Check rejects empty file."""
        path = write_temp_repo(self, "# only a comment\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_bad_syntax(self):
        """Check rejects bad syntax."""
        path = write_temp_repo(self, "A B\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)

    def test_rejects_duplicate_dependency(self):
        """Check rejects duplicate dependency."""
        path = write_temp_repo(self, "A: B B\nB:\n")
        with self.assertRaises(SourceError):
            load_test_repository(path)


class TestRepositorySourceTest(unittest.TestCase):
    """Check the source adapter around the parser."""

    def setUp(self):
        """Prepare the test fixture."""
        self.path = write_temp_repo(self, "A: B\nB:\n")

    def test_root_and_dependencies(self):
        """Check root and dependencies."""
        source = TestRepositorySource(self.path)
        root = source.resolve_root("A")
        self.assertEqual(root.name, "A")
        self.assertIsNone(root.version)
        self.assertEqual(
            [dep.name for dep in source.dependencies(root)], ["B"]
        )

    def test_unknown_root(self):
        """Check unknown root."""
        source = TestRepositorySource(self.path)
        with self.assertRaises(SourceError):
            source.resolve_root("Z")

    def test_explicit_version_is_rejected(self):
        """Check explicit version is rejected."""
        source = TestRepositorySource(self.path)
        with self.assertRaises(SourceError):
            source.resolve_root("A", "1.0.0")

    def test_dependency_resolution(self):
        """Check dependency resolution."""
        source = TestRepositorySource(self.path)
        from cargo_deps.models import Dependency

        self.assertIsNotNone(source.resolve_dependency(Dependency("B")))
        self.assertIsNone(source.resolve_dependency(Dependency("Z")))

    def test_missing_file(self):
        """Check missing file."""
        with self.assertRaises(SourceError):
            TestRepositorySource(Path("/nonexistent/repository.txt"))
