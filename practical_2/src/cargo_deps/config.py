"""Проверка параметров и неизменяемая конфигурация командной строки."""

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import ConfigError
from .graph import MAX_DEPTH, UNLIMITED_DEPTH
from .semver import SemverError, parse_version

MODES = ("cargo", "test")
ASCII_MODES = ("off", "tree")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
TEST_PACKAGE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
MAX_NAME_LENGTH = 100
MAX_FILTER_LENGTH = 80
CONTROL_LIMIT = 32
SVG_SUFFIX = ".svg"
NONE_TEXT = "<не задано>"
LATEST_TEXT = "<последняя>"
UNLIMITED_TEXT = "без ограничения"


@dataclass(frozen=True)
class Config:
    """Проверенные настройки одного запуска программы."""

    package: str
    repository: str
    mode: str
    output: Path
    ascii_mode: str
    filter_text: str
    load_order: bool
    package_version: str | None
    include_dev: bool
    include_optional: bool
    max_depth: int
    no_config: bool

    @property
    def dot_output(self) -> Path:
        """Возвращает путь к DOT-файлу рядом с SVG-изображением."""
        return self.output.with_suffix(".dot")

    def as_pairs(self) -> list[tuple[str, str]]:
        """Возвращает все настраиваемые значения в виде пар ключ-значение."""
        depth = (
            UNLIMITED_TEXT
            if self.max_depth == UNLIMITED_DEPTH
            else str(self.max_depth)
        )
        return [
            ("package", self.package),
            ("repository", self.repository),
            ("mode", self.mode),
            ("output", str(self.output)),
            ("ascii", self.ascii_mode),
            ("filter", self.filter_text or NONE_TEXT),
            ("load_order", _bool_text(self.load_order)),
            ("package_version", self.package_version or LATEST_TEXT),
            ("include_dev", _bool_text(self.include_dev)),
            ("include_optional", _bool_text(self.include_optional)),
            ("max_depth", depth),
        ]


def _bool_text(value: bool) -> str:
    """Возвращает булево значение в текстовом виде."""
    return "да" if value else "нет"


def _ensure_text(value: str, option: str) -> str:
    """Запрещает управляющие символы в пользовательском значении."""
    if any(ord(character) < CONTROL_LIMIT for character in value):
        raise ConfigError(
            f"{option}: управляющие символы недопустимы"
        )
    return value


def _validate_mode(value: str) -> str:
    """Проверяет режим работы с репозиторием."""
    if value not in MODES:
        choices = ", ".join(MODES)
        raise ConfigError(f"--mode должен быть одним из: {choices}")
    return value


def _validate_package(package: str, mode: str) -> str:
    """Проверяет имя пакета для выбранного режима."""
    value = _ensure_text(package, "--package").strip()
    if not value:
        raise ConfigError("--package не должен быть пустым")
    if len(value) > MAX_NAME_LENGTH:
        raise ConfigError(
            f"--package должен содержать не более {MAX_NAME_LENGTH} "
            "символов"
        )
    pattern = TEST_PACKAGE_RE if mode == "test" else PACKAGE_RE
    if pattern.match(value) is None:
        if mode == "test":
            raise ConfigError(
                "--package в тестовом режиме должен состоять из заглавных "
                "латинских букв, цифр и символа подчёркивания"
            )
        raise ConfigError(
            "--package должен начинаться с буквы или цифры и содержать "
            "только буквы, цифры, '-' и '_'"
        )
    return value


def _validate_test_repository(value: str) -> str:
    """Проверяет путь к тестовому репозиторию."""
    path = Path(value).expanduser()
    if not path.exists():
        raise ConfigError(f"тестовый репозиторий не найден: {path}")
    if not path.is_file():
        raise ConfigError(f"тестовый репозиторий не является файлом: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ConfigError(
            f"не удалось получить размер {path}: {exc}"
        ) from exc
    if size == 0:
        raise ConfigError(f"тестовый репозиторий пуст: {path}")
    if not os.access(path, os.R_OK):
        raise ConfigError(f"тестовый репозиторий недоступен для чтения: {path}")
    return str(path)


def _validate_cargo_repository(value: str) -> str:
    """Проверяет URL реестра Cargo."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(
            "--repository в режиме cargo должен быть HTTP(S)-адресом "
            "реестра"
        )
    if parsed.path.endswith(".git"):
        raise ConfigError(
            "--repository должен быть URL sparse-индекса Cargo, "
            "а не git-репозитория"
        )
    return value


def _validate_repository(repository: str, mode: str) -> str:
    """Проверяет аргумент с расположением репозитория."""
    value = _ensure_text(repository, "--repository").strip()
    if not value:
        raise ConfigError("--repository не должен быть пустым")
    if mode == "test":
        return _validate_test_repository(value)
    return _validate_cargo_repository(value)


def _validate_output(output: str) -> Path:
    """Проверяет путь к SVG-файлу и его каталог."""
    value = _ensure_text(output, "--output").strip()
    if not value:
        raise ConfigError("--output не должен быть пустым")
    path = Path(value).expanduser()
    if path.suffix.lower() != SVG_SUFFIX:
        raise ConfigError("--output должен иметь расширение .svg")
    if path.exists() and path.is_dir():
        raise ConfigError(f"--output указывает на каталог: {path}")
    parent = path.parent
    if not parent.exists():
        raise ConfigError(f"каталог вывода не существует: {parent}")
    if not parent.is_dir():
        raise ConfigError(f"родительский путь вывода не каталог: {parent}")
    if not os.access(parent, os.W_OK):
        raise ConfigError(f"каталог вывода недоступен для записи: {parent}")
    return path


def _validate_ascii(value: str) -> str:
    """Проверяет режим вывода ASCII-дерева."""
    if value not in ASCII_MODES:
        choices = ", ".join(ASCII_MODES)
        raise ConfigError(f"--ascii должен быть одним из: {choices}")
    return value


def _validate_filter(value: str) -> str:
    """Проверяет подстроку фильтрации зависимостей."""
    _ensure_text(value, "--filter")
    if len(value) > MAX_FILTER_LENGTH:
        raise ConfigError(
            f"--filter должен содержать не более {MAX_FILTER_LENGTH} "
            "символов"
        )
    return value


def _validate_version(value: str | None) -> str | None:
    """Проверяет необязательную явную версию пакета."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise ConfigError("--package-version не должен быть пустым")
    try:
        parse_version(cleaned)
    except SemverError as exc:
        raise ConfigError(
            f"--package-version имеет неверный формат: {exc}"
        ) from exc
    return cleaned


def _validate_depth(value: int) -> int:
    """Проверяет ограничение глубины обхода."""
    if value < UNLIMITED_DEPTH or value > MAX_DEPTH:
        raise ConfigError(
            f"--max-depth должен быть от {UNLIMITED_DEPTH} до {MAX_DEPTH}"
        )
    return value


def config_from_namespace(namespace: argparse.Namespace) -> Config:
    """Проверяет аргументы и создаёт конфигурацию."""
    mode = _validate_mode(namespace.mode)
    package = _validate_package(namespace.package, mode)
    repository = _validate_repository(namespace.repository, mode)
    output = _validate_output(namespace.output)
    ascii_mode = _validate_ascii(namespace.ascii_mode)
    filter_text = _validate_filter(namespace.filter_text)
    package_version = _validate_version(namespace.package_version)
    max_depth = _validate_depth(namespace.max_depth)
    if mode == "test" and package_version is not None:
        raise ConfigError(
            "--package-version поддерживается только в режиме cargo"
        )
    return Config(
        package=package,
        repository=repository,
        mode=mode,
        output=output,
        ascii_mode=ascii_mode,
        filter_text=filter_text,
        load_order=bool(namespace.load_order),
        package_version=package_version,
        include_dev=bool(namespace.include_dev),
        include_optional=bool(namespace.include_optional),
        max_depth=max_depth,
        no_config=bool(namespace.no_config),
    )


def format_config(config: Config) -> str:
    """Возвращает блок параметров запуска в формате ключ-значение."""
    lines = ["Параметры запуска:"]
    lines.extend(f"  {key} = {value}" for key, value in config.as_pairs())
    return "\n".join(lines)
