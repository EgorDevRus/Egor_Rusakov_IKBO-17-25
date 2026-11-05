"""Параметры командной строки эмулятора."""
import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Настройки запуска эмулятора."""

    vfs_path: str
    script_path: str


def build_parser() -> argparse.ArgumentParser:
    """Создаёт парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="shell-emulator",
        description="Эмулятор командной оболочки с виртуальной ФС",
    )
    parser.add_argument(
        "--vfs",
        required=True,
        help="путь к CSV-файлу виртуальной файловой системы",
    )
    parser.add_argument(
        "--script",
        required=True,
        help="путь к стартовому скрипту с командами эмулятора",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> Config:
    """Разбирает аргументы командной строки и возвращает настройки."""
    namespace = build_parser().parse_args(argv)
    return Config(
        vfs_path=namespace.vfs,
        script_path=namespace.script,
    )
