"""Текстовый источник зависимостей для детерминированного тестового режима.

Формат построчный. Пустые строки и всё после ``#`` игнорируются.
Объявление имеет вид ``ИМЯ: ЗАВИСИМОСТЬ1 ЗАВИСИМОСТЬ2`` (вместо ``:``
допускается ``->``), а имена состоят из заглавных латинских букв, цифр
и символа подчёркивания::

    # Простой ациклический граф
    A: B C
    B: D
    C: D E
    D:
    E:

Каждый упомянутый пакет должен быть объявлен — так тестовые файлы
остаются явными, а опечатки сразу видны.
"""

import re
from pathlib import Path

from ..errors import SourceError
from ..models import Dependency, ResolvedPackage

_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SEPARATORS = (":", "->")
MAX_FILE_SIZE = 1024 * 1024


def _validate_name(name: str, line_number: int) -> None:
    """Проверяет имя тестового пакета."""
    if _NAME_RE.match(name) is None:
        raise SourceError(
            f"строка {line_number}: неверное имя пакета {name!r}; "
            "используйте заглавные латинские буквы, цифры и '_'"
        )


def _split_declaration(line: str, line_number: int) -> tuple[str, str]:
    """Делит объявление на имя пакета и текст зависимостей."""
    for separator in _SEPARATORS:
        if separator in line:
            name, _, body = line.partition(separator)
            name = name.strip()
            if not name:
                raise SourceError(
                    f"строка {line_number}: пустое имя пакета"
                )
            return name, body
    raise SourceError(
        f"строка {line_number}: ожидалось 'ИМЯ: ЗАВИСИМОСТИ', "
        f"получено {line!r}"
    )


def _parse_dependencies(body: str, line_number: int) -> list[str]:
    """Разбирает список зависимостей одного объявления."""
    names = body.replace(",", " ").split()
    for name in names:
        _validate_name(name, line_number)
    if len(set(names)) != len(names):
        raise SourceError(
            f"строка {line_number}: повторяющееся имя зависимости"
        )
    return names


def _check_references(packages: dict[str, list[str]]) -> None:
    """Проверяет, что все упомянутые пакеты объявлены."""
    for owner, dependencies in packages.items():
        for dependency in dependencies:
            if dependency not in packages:
                raise SourceError(
                    f"пакет {owner!r} ссылается на необъявленный пакет "
                    f"{dependency!r}"
                )


def load_test_repository(path: Path) -> dict[str, tuple[str, ...]]:
    """Разбирает тестовый репозиторий в отображение смежности."""
    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            raise SourceError(f"тестовый репозиторий слишком велик: {path}")
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SourceError(
            f"не удалось прочитать тестовый репозиторий {path}: {exc}"
        ) from exc
    packages: dict[str, list[str]] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name, body = _split_declaration(line, line_number)
        _validate_name(name, line_number)
        if name in packages:
            raise SourceError(
                f"строка {line_number}: пакет {name!r} объявлен дважды"
            )
        packages[name] = _parse_dependencies(body, line_number)
    if not packages:
        raise SourceError(
            f"тестовый репозиторий {path} не содержит пакетов"
        )
    _check_references(packages)
    return {
        name: tuple(dependencies) for name, dependencies in packages.items()
    }


class TestRepositorySource:
    """Источник зависимостей из файла описания тестового графа."""

    def __init__(self, path: Path) -> None:
        """Сразу загружает и проверяет файл ``path``."""
        self._path = path
        self._packages = load_test_repository(path)

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Возвращает релиз без версии для объявленного тестового пакета."""
        if version is not None:
            raise SourceError(
                "явные версии не поддерживаются в тестовом режиме"
            )
        if name not in self._packages:
            raise SourceError(
                f"пакет {name!r} отсутствует в {self._path}"
            )
        return ResolvedPackage(name)

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Разрешает зависимость по точному имени пакета."""
        if dep.name in self._packages:
            return ResolvedPackage(dep.name)
        return None

    def dependencies(self, package: ResolvedPackage) -> list[Dependency]:
        """Возвращает объявленные прямые зависимости пакета."""
        if package.name not in self._packages:
            raise SourceError(
                f"неизвестный тестовый пакет {package.name!r}"
            )
        return [
            Dependency(name=child) for child in self._packages[package.name]
        ]
