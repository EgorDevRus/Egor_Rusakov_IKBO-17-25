"""Интерфейс командной строки визуализатора зависимостей."""

import argparse
import sys
from pathlib import Path

from .config import (
    ASCII_MODES,
    MODES,
    Config,
    config_from_namespace,
    format_config,
)
from .errors import CargoDepsError, RenderError
from .graph import GraphBuilder, load_order
from .models import DependencyGraph
from .render import render_ascii, render_dot, write_svg
from .sources import create_source

EPILOG = """примеры:
  ./run.sh -p A -r examples/simple.txt -m test -o out/a.svg --ascii tree
  ./run.sh -p serde_json -r https://crates.io -m cargo -o out/serde_json.svg
  ./run.sh -p A -r examples/cycles.txt -m test -o out/a.svg \\
      --filter B --load-order
"""

_ERROR_REPLACEMENTS = (
    ("the following arguments are required:",
     "обязательные аргументы:"),
    ("invalid choice:", "недопустимое значение:"),
    ("(choose from ", "(допустимо: "),
    ("unrecognized arguments:", "нераспознанные аргументы:"),
    ("invalid int value:", "неверное целое значение:"),
    ("expected one argument", "требуется одно значение"),
    ("argument ", "аргумент "),
)


class RussianArgumentParser(argparse.ArgumentParser):
    """Парсер аргументов с русскими сообщениями и справкой."""

    def format_usage(self) -> str:
        """Возвращает строку использования на русском языке."""
        return super().format_usage().replace(
            "usage:", "использование:", 1
        )

    def format_help(self) -> str:
        """Возвращает справку с русскими заголовками разделов."""
        text = super().format_help()
        return (
            text.replace("usage:", "использование:", 1)
            .replace("positional arguments:", "позиционные аргументы:")
            .replace("options:", "параметры:")
        )

    def error(self, message: str) -> None:
        """Выводит сообщение об ошибке на русском языке."""
        for source, target in _ERROR_REPLACEMENTS:
            message = message.replace(source, target)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: ошибка: {message}\n")


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    """Добавляет параметры пакета, репозитория и режима."""
    parser.add_argument(
        "-p", "--package", required=True, metavar="ИМЯ",
        help="имя анализируемого пакета",
    )
    parser.add_argument(
        "-r", "--repository", required=True, metavar="URL|ПУТЬ",
        help="URL sparse-индекса Cargo или файл тестового репозитория",
    )
    parser.add_argument(
        "-m", "--mode", choices=MODES, default="cargo",
        help="режим работы с репозиторием (по умолчанию: cargo)",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Добавляет параметры вывода, ASCII-дерева и фильтра."""
    parser.add_argument(
        "-o", "--output", default="dependencies.svg", metavar="ФАЙЛ.svg",
        help="файл SVG для сохранения графа "
        "(по умолчанию: dependencies.svg)",
    )
    parser.add_argument(
        "-a", "--ascii", dest="ascii_mode", choices=ASCII_MODES,
        default="off", help="вывести ASCII-дерево зависимостей",
    )
    parser.add_argument(
        "-f", "--filter", dest="filter_text", default="",
        metavar="ПОДСТРОКА",
        help="пропускать зависимости, содержащие подстроку",
    )


def _add_advanced_arguments(parser: argparse.ArgumentParser) -> None:
    """Добавляет параметры порядка загрузки, версии и глубины."""
    parser.add_argument(
        "--load-order", action="store_true",
        help="вывести порядок загрузки, начиная с зависимостей",
    )
    parser.add_argument(
        "--package-version", default=None, metavar="X.Y.Z",
        help="явная версия корневого пакета (только для cargo)",
    )
    parser.add_argument(
        "--include-dev", action="store_true",
        help="учитывать dev-зависимости",
    )
    parser.add_argument(
        "--include-optional", action="store_true",
        help="учитывать необязательные зависимости",
    )
    parser.add_argument(
        "--max-depth", type=int, default=0, metavar="N",
        help="ограничить глубину обхода; 0 — без ограничения",
    )
    parser.add_argument(
        "--no-config", action="store_true",
        help="не печатать блок параметров запуска",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 1.0.0",
        help="показать версию программы и выйти",
    )


def build_parser() -> argparse.ArgumentParser:
    """Создаёт парсер аргументов командной строки."""
    parser = RussianArgumentParser(
        prog="cargo-deps",
        description=(
            "Построение и визуализация графа зависимостей пакета Cargo "
            "без вызова Cargo."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="help",
        help="показать эту справку и выйти",
    )
    _add_source_arguments(parser)
    _add_output_arguments(parser)
    _add_advanced_arguments(parser)
    return parser


def _write_dot(path: Path, content: str) -> None:
    """Записывает DOT-описание рядом с изображением."""
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RenderError(
            f"не удалось записать DOT-файл {path}: {exc}"
        ) from exc


def _print_warnings(graph: DependencyGraph) -> None:
    """Выводит собранные предупреждения в поток ошибок."""
    for warning in graph.warnings:
        print(f"предупреждение: {warning}", file=sys.stderr)


def _print_load_order(graph: DependencyGraph) -> None:
    """Выводит порядок загрузки, начиная с зависимостей."""
    print(f"\nПорядок загрузки для {graph.root} (сначала зависимости):")
    for position, name in enumerate(load_order(graph), start=1):
        root_marker = " (корень)" if name == graph.root else ""
        print(f"  {position:2d}. {name}{root_marker}")
    if graph.cycles:
        print(
            "  примечание: рёбра циклов пропущены, "
            "чтобы построить порядок"
        )


def _print_summary(
    graph: DependencyGraph, config: Config, engine: str
) -> None:
    """Выводит итоговую сводку по пакетам и файлам."""
    print(
        f"\nГраф: пакетов — {graph.package_count}, "
        f"рёбер — {graph.edge_count}, "
        f"циклических рёбер — {len(graph.cycles)}"
    )
    print(f"Изображение: {config.output} (рендерер: {engine})")
    print(f"DOT-файл: {config.dot_output}")


def _execute(config: Config) -> int:
    """Строит граф, сохраняет изображение и печатает отчёт."""
    source = create_source(config.mode, config.repository)
    builder = GraphBuilder(
        source,
        filter_text=config.filter_text,
        include_dev=config.include_dev,
        include_optional=config.include_optional,
        max_depth=config.max_depth,
    )
    graph = builder.build(config.package, config.package_version)
    dot_source = render_dot(graph)
    _write_dot(config.dot_output, dot_source)
    engine = write_svg(dot_source, graph, config.output)
    _print_warnings(graph)
    if config.ascii_mode == "tree":
        print(render_ascii(graph))
    if config.load_order:
        _print_load_order(graph)
    _print_summary(graph, config, engine)
    return 0


def run(argv: list[str] | None = None) -> int:
    """Разбирает аргументы, выполняет программу и возвращает код."""
    parser = build_parser()
    namespace = parser.parse_args(argv)
    try:
        config = config_from_namespace(namespace)
    except CargoDepsError as exc:
        print(f"ошибка: {exc.message}", file=sys.stderr)
        return exc.exit_code
    if not config.no_config:
        print(format_config(config))
    try:
        return _execute(config)
    except CargoDepsError as exc:
        print(f"ошибка: {exc.message}", file=sys.stderr)
        return exc.exit_code


def main(argv: list[str] | None = None) -> int:
    """Точка входа для консольной команды и ``python -m``."""
    return run(argv)
