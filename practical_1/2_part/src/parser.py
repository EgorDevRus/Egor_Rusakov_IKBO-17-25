"""Разбор строки ввода на имя команды и аргументы."""
import shlex
from dataclasses import dataclass
from typing import List, Optional

MIN_PARTS = 1


class ParseError(ValueError):
    """Ошибка разбора строки ввода."""


@dataclass(frozen=True)
class Command:
    """Результат разбора одной строки ввода."""

    name: str
    args: List[str]


def parse_input(line: str) -> Optional[Command]:
    """Разбирает строку ввода с корректной обработкой кавычек.

    Пустая строка или строка из пробелов даёт None.
    """
    try:
        parts = shlex.split(line, posix=True)
    except ValueError as error:
        raise ParseError(f"незакрытая кавычка: {error}") from error
    if len(parts) < MIN_PARTS:
        return None
    return Command(name=parts[0], args=parts[1:])
