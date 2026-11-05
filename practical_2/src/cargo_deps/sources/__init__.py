"""Реализации источников данных о зависимостях."""

from pathlib import Path

from ..errors import ConfigError
from .base import DependencySource
from .cargo_index import CargoIndexSource
from .test_repo import TestRepositorySource


def create_source(mode: str, repository: str) -> DependencySource:
    """Создаёт источник данных, выбранный режимом ``mode``."""
    if mode == "test":
        return TestRepositorySource(Path(repository))
    if mode == "cargo":
        return CargoIndexSource(repository)
    raise ConfigError(f"неподдерживаемый режим источника: {mode}")
