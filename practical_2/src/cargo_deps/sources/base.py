"""Интерфейсы источников данных о зависимостях."""

from typing import Protocol

from ..models import Dependency, ResolvedPackage


class DependencySource(Protocol):
    """Источник релизов пакетов и их прямых зависимостей."""

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Выбирает корневой релиз пакета ``name``."""
        ...

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Выбирает релиз под требование ``dep`` или возвращает ``None``."""
        ...

    def dependencies(self, package: ResolvedPackage) -> list[Dependency]:
        """Возвращает прямые зависимости выбранного пакета."""
        ...
