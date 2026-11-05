"""Command line interface of the dependency graph visualizer."""

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

EPILOG = """examples:
  ./run.sh -p A -r examples/simple.txt -m test -o out/a.svg --ascii tree
  ./run.sh -p serde_json -r https://crates.io -m cargo -o out/serde_json.svg
  ./run.sh -p A -r examples/cycles.txt -m test -o out/a.svg \\
      --filter B --load-order
"""


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    """Add package, repository and mode options."""
    parser.add_argument(
        "-p", "--package", required=True, metavar="NAME",
        help="name of the analyzed package",
    )
    parser.add_argument(
        "-r", "--repository", required=True, metavar="URL|PATH",
        help="Cargo sparse index URL or test repository file",
    )
    parser.add_argument(
        "-m", "--mode", choices=MODES, default="cargo",
        help="repository mode (default: cargo)",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Add output, ASCII tree and filter options."""
    parser.add_argument(
        "-o", "--output", default="dependencies.svg", metavar="FILE.svg",
        help="output SVG file (default: dependencies.svg)",
    )
    parser.add_argument(
        "-a", "--ascii", dest="ascii_mode", choices=ASCII_MODES,
        default="off", help="print an ASCII dependency tree",
    )
    parser.add_argument(
        "-f", "--filter", dest="filter_text", default="",
        metavar="SUBSTRING",
        help="skip dependency names containing SUBSTRING",
    )


def _add_advanced_arguments(parser: argparse.ArgumentParser) -> None:
    """Add load order, version, dependency kind and depth options."""
    parser.add_argument(
        "--load-order", action="store_true",
        help="print a dependencies-first load order",
    )
    parser.add_argument(
        "--package-version", default=None, metavar="X.Y.Z",
        help="use an explicit root version (cargo mode only)",
    )
    parser.add_argument(
        "--include-dev", action="store_true",
        help="include dev-dependencies",
    )
    parser.add_argument(
        "--include-optional", action="store_true",
        help="include optional dependencies",
    )
    parser.add_argument(
        "--max-depth", type=int, default=0, metavar="N",
        help="limit traversal depth; 0 means unlimited",
    )
    parser.add_argument(
        "--no-config", action="store_true",
        help="do not print the configuration block",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 1.0.0",
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="cargo-deps",
        description=(
            "Build and visualize the dependency graph of a Cargo package "
            "without invoking Cargo."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_source_arguments(parser)
    _add_output_arguments(parser)
    _add_advanced_arguments(parser)
    return parser


def _write_dot(path: Path, content: str) -> None:
    """Write the DOT source next to the image."""
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RenderError(f"cannot write DOT file {path}: {exc}") from exc


def _print_warnings(graph: DependencyGraph) -> None:
    """Print collected warnings to standard error."""
    for warning in graph.warnings:
        print(f"warning: {warning}", file=sys.stderr)


def _print_load_order(graph: DependencyGraph) -> None:
    """Print a dependencies-first loading sequence."""
    print(f"\nLoad order for {graph.root} (dependencies first):")
    for position, name in enumerate(load_order(graph), start=1):
        root_marker = " (root)" if name == graph.root else ""
        print(f"  {position:2d}. {name}{root_marker}")
    if graph.cycles:
        print("  note: cycle edges were ignored to produce this order")


def _print_summary(
    graph: DependencyGraph, config: Config, engine: str
) -> None:
    """Print the final package and output summary."""
    print(
        f"\nGraph: {graph.package_count} packages, "
        f"{graph.edge_count} edges, {len(graph.cycles)} cycle edges"
    )
    print(f"Image: {config.output} (renderer: {engine})")
    print(f"DOT: {config.dot_output}")


def _execute(config: Config) -> int:
    """Build the graph, render outputs and print the report."""
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
    """Parse arguments, execute the tool and return an exit code."""
    parser = build_parser()
    namespace = parser.parse_args(argv)
    try:
        config = config_from_namespace(namespace)
    except CargoDepsError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return exc.exit_code
    if not config.no_config:
        print(format_config(config))
    try:
        return _execute(config)
    except CargoDepsError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return exc.exit_code


def main(argv: list[str] | None = None) -> int:
    """Entry point used by the console script and ``python -m``."""
    return run(argv)
