"""Dependency source implementations."""

from pathlib import Path

from ..errors import ConfigError
from .base import DependencySource
from .cargo_index import CargoIndexSource
from .test_repo import TestRepositorySource


def create_source(mode: str, repository: str) -> DependencySource:
    """Create the dependency source selected by ``mode``."""
    if mode == "test":
        return TestRepositorySource(Path(repository))
    if mode == "cargo":
        return CargoIndexSource(repository)
    raise ConfigError(f"unsupported source mode: {mode}")
