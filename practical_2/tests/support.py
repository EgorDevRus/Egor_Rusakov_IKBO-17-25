"""Общие вспомогательные функции для модульных и интеграционных тестов."""

import shutil
import tempfile
from pathlib import Path

from cargo_deps.errors import SourceError
from cargo_deps.models import Dependency, ResolvedPackage


class StaticSource:
    """Источник зависимостей в памяти для тестов графа."""

    def __init__(self, mapping: dict[str, list[Dependency]]) -> None:
        """Сохраняет изменяемую копию отображения смежности."""
        self.mapping = {
            name: list(dependencies)
            for name, dependencies in mapping.items()
        }

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Возвращает запрошенный пакет, если он существует."""
        if name not in self.mapping:
            raise SourceError(f"неизвестный пакет: {name}")
        return ResolvedPackage(name, version)

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Разрешает зависимость по точному имени из отображения."""
        if dep.name in self.mapping:
            return ResolvedPackage(dep.name)
        return None

    def dependencies(self, package: ResolvedPackage) -> list[Dependency]:
        """Возвращает настроенный список зависимостей."""
        return list(self.mapping.get(package.name, []))


def snake_case_setup(test_class):
    """Регистрирует ``set_up`` как стандартный хук ``setUp`` unittest."""
    test_class.setUp = test_class.set_up
    return test_class


def write_temp_repo(test_case, text: str) -> Path:
    """Записывает ``text`` во временный файл и удаляет его после теста."""
    directory = Path(tempfile.mkdtemp())
    test_case.addCleanup(shutil.rmtree, directory, ignore_errors=True)
    path = directory / "repository.txt"
    path.write_text(text, encoding="utf-8")
    return path
