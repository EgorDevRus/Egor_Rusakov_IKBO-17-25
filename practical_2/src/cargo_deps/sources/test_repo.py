"""Text-file dependency source used by the deterministic test mode.

The format is line oriented.  Blank lines and everything after ``#`` are
ignored.  A declaration has the form ``NAME: DEP1 DEP2`` (``->`` is
accepted instead of ``:``) and names consist of capital Latin letters,
digits and underscores::

    # Simple acyclic graph
    A: B C
    B: D
    C: D E
    D:
    E:

Every referenced package must be declared, which keeps test files
explicit and makes typos visible.
"""

import re
from pathlib import Path

from ..errors import SourceError
from ..models import Dependency, ResolvedPackage

_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SEPARATORS = (":", "->")
MAX_FILE_SIZE = 1024 * 1024


def _validate_name(name: str, line_number: int) -> None:
    """Validate a test package name."""
    if _NAME_RE.match(name) is None:
        raise SourceError(
            f"line {line_number}: invalid package name {name!r}; "
            "use capital Latin letters, digits and underscores"
        )


def _split_declaration(line: str, line_number: int) -> tuple[str, str]:
    """Split a declaration into a package name and dependency text."""
    for separator in _SEPARATORS:
        if separator in line:
            name, _, body = line.partition(separator)
            name = name.strip()
            if not name:
                raise SourceError(f"line {line_number}: empty package name")
            return name, body
    raise SourceError(
        f"line {line_number}: expected 'NAME: DEPENDENCIES', got {line!r}"
    )


def _parse_dependencies(body: str, line_number: int) -> list[str]:
    """Parse the dependency list of one declaration."""
    names = body.replace(",", " ").split()
    for name in names:
        _validate_name(name, line_number)
    if len(set(names)) != len(names):
        raise SourceError(f"line {line_number}: duplicate dependency name")
    return names


def _check_references(packages: dict[str, list[str]]) -> None:
    """Ensure every referenced package is declared."""
    for owner, dependencies in packages.items():
        for dependency in dependencies:
            if dependency not in packages:
                raise SourceError(
                    f"package {owner!r} references undeclared package "
                    f"{dependency!r}"
                )


def load_test_repository(path: Path) -> dict[str, tuple[str, ...]]:
    """Parse a test repository file into an adjacency mapping."""
    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            raise SourceError(f"test repository is too large: {path}")
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SourceError(f"cannot read test repository {path}: {exc}") from exc
    packages: dict[str, list[str]] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name, body = _split_declaration(line, line_number)
        _validate_name(name, line_number)
        if name in packages:
            raise SourceError(
                f"line {line_number}: package {name!r} is declared twice"
            )
        packages[name] = _parse_dependencies(body, line_number)
    if not packages:
        raise SourceError(f"test repository {path} contains no packages")
    _check_references(packages)
    return {
        name: tuple(dependencies) for name, dependencies in packages.items()
    }


class TestRepositorySource:
    """Dependency source backed by a test graph description file."""

    def __init__(self, path: Path) -> None:
        """Load and validate ``path`` eagerly."""
        self._path = path
        self._packages = load_test_repository(path)

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Return a versionless release for a declared test package."""
        if version is not None:
            raise SourceError(
                "explicit versions are not supported in test mode"
            )
        if name not in self._packages:
            raise SourceError(
                f"package {name!r} is not present in {self._path}"
            )
        return ResolvedPackage(name)

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Resolve an edge by its exact package name."""
        if dep.name in self._packages:
            return ResolvedPackage(dep.name)
        return None

    def dependencies(self, package: ResolvedPackage) -> list[Dependency]:
        """Return the declared direct dependencies of ``package``."""
        if package.name not in self._packages:
            raise SourceError(f"unknown test package {package.name!r}")
        return [
            Dependency(name=child) for child in self._packages[package.name]
        ]
