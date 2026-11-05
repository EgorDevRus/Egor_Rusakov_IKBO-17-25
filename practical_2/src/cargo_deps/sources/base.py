"""Interfaces implemented by dependency data sources."""

from typing import Protocol

from ..models import Dependency, ResolvedPackage


class DependencySource(Protocol):
    """Source of package releases and their direct dependencies."""

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Select the root release of ``name``."""
        ...

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Select a release satisfying ``dep`` or return ``None``."""
        ...

    def dependencies(self, package: ResolvedPackage) -> list[Dependency]:
        """Return direct dependencies of a resolved package."""
        ...
