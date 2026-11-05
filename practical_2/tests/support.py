"""Shared helpers for the unit and integration tests."""

import shutil
import tempfile
from pathlib import Path

from cargo_deps.errors import SourceError
from cargo_deps.models import Dependency, ResolvedPackage


class StaticSource:
    """In-memory dependency source used by graph tests."""

    def __init__(self, mapping: dict[str, list[Dependency]]) -> None:
        """Keep a mutable copy of the adjacency mapping."""
        self.mapping = {
            name: list(dependencies)
            for name, dependencies in mapping.items()
        }

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Return the requested package when it exists."""
        if name not in self.mapping:
            raise SourceError(f"unknown package: {name}")
        return ResolvedPackage(name, version)

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Resolve by exact name from the static mapping."""
        if dep.name in self.mapping:
            return ResolvedPackage(dep.name)
        return None

    def dependencies(self, package: ResolvedPackage) -> list[Dependency]:
        """Return the configured dependency list."""
        return list(self.mapping.get(package.name, []))


def write_temp_repo(test_case, text: str) -> Path:
    """Write ``text`` to a temporary file and clean it after the test."""
    directory = Path(tempfile.mkdtemp())
    test_case.addCleanup(shutil.rmtree, directory, ignore_errors=True)
    path = directory / "repository.txt"
    path.write_text(text, encoding="utf-8")
    return path
