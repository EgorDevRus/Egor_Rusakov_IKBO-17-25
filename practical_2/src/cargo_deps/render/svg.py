"""Отрисовка SVG через Graphviz и встроенный резервный рендерер.

Graphviz даёт более красивую картинку, но инструмент должен работать и
без него. Резервный рендерер раскладывает узлы по уровням BFS и строит
корректный SVG-документ, используя только стандартную библиотеку.
"""

import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from ..errors import RenderError
from ..graph import cycle_packages
from ..models import DependencyGraph, GraphNode
from .dot import render_dot

DOT_TIMEOUT = 30
NODE_WIDTH = 180
NODE_HEIGHT = 48
H_GAP = 40
V_GAP = 80
MARGIN = 40
TITLE_HEIGHT = 40
LABEL_LIMIT = 24
ROOT_FILL = "#ffe8a3"
CYCLE_FILL = "#f8d7da"
NODE_FILL = "#dce9f7"
STROKE = "#33475b"
CYCLE_COLOR = "#c0392b"
FONT = "Helvetica, Arial, sans-serif"


def _truncate(text: str) -> str:
    """Сокращает подпись узла для рамки SVG."""
    if len(text) <= LABEL_LIMIT:
        return text
    return text[: LABEL_LIMIT - 1] + "…"


def _layout(
    graph: DependencyGraph,
) -> tuple[int, int, dict[str, tuple[float, float]]]:
    """Вычисляет размер холста и позиции всех узлов."""
    levels: dict[int, list[str]] = {}
    for name, node in graph.nodes.items():
        levels.setdefault(node.depth, []).append(name)
    ordered = sorted(levels.items())
    max_count = max(len(names) for _, names in ordered)
    width = (
        2 * MARGIN + max_count * NODE_WIDTH + (max_count - 1) * H_GAP
    )
    height = (
        2 * MARGIN
        + TITLE_HEIGHT
        + len(ordered) * NODE_HEIGHT
        + (len(ordered) - 1) * V_GAP
    )
    positions: dict[str, tuple[float, float]] = {}
    for depth, names in ordered:
        names = sorted(names)
        row_width = len(names) * NODE_WIDTH + (len(names) - 1) * H_GAP
        start_x = (width - row_width) / 2
        y = MARGIN + TITLE_HEIGHT + depth * (NODE_HEIGHT + V_GAP)
        for index, name in enumerate(names):
            x = start_x + index * (NODE_WIDTH + H_GAP)
            positions[name] = (x, float(y))
    return int(width), int(height), positions


def _header(width: int, height: int, root: str) -> list[str]:
    """Собирает заголовок и описание SVG-документа."""
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        "<desc>Граф зависимостей, построенный cargo-deps-graph</desc>",
        (
            f'<text x="{MARGIN}" y="26" font-family="{FONT}" '
            f'font-size="16" font-weight="bold" fill="{STROKE}">'
            f"Граф зависимостей: {escape(root)}</text>"
        ),
    ]


def _defs() -> list[str]:
    """Собирает определения маркеров-стрелок."""
    return [
        "<defs>",
        (
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="#5b6b7c"/></marker>'
        ),
        (
            '<marker id="arrow-cycle" viewBox="0 0 10 10" refX="9" '
            'refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{CYCLE_COLOR}"/></marker>'
        ),
        "</defs>",
    ]


def _text_line(
    x: float, y: float, text: str, size: int, color: str
) -> str:
    """Собирает один центрированный текстовый элемент SVG."""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="{size}" fill="{color}">'
        f"{escape(text)}</text>"
    )


def _node_text(
    node: GraphNode, center_x: float, y: float
) -> list[str]:
    """Собирает текст с именем и необязательной версией узла."""
    label = _truncate(node.package.name)
    if not node.package.version:
        return [_text_line(center_x, y + 29, label, 12, "#1f2d3d")]
    return [
        _text_line(center_x, y + 20, label, 12, "#1f2d3d"),
        _text_line(
            center_x, y + 36, node.package.version, 10, "#5b6b7c"
        ),
    ]


def _node_markup(
    name: str,
    node: GraphNode,
    position: tuple[float, float],
    in_cycle: bool,
) -> list[str]:
    """Собирает SVG-разметку одного узла."""
    x, y = position
    if node.is_root:
        fill = ROOT_FILL
    elif in_cycle:
        fill = CYCLE_FILL
    else:
        fill = NODE_FILL
    stroke_width = 2 if node.is_root else 1
    markup = [
        (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{NODE_WIDTH}" '
            f'height="{NODE_HEIGHT}" rx="8" fill="{fill}" '
            f'stroke="{STROKE}" stroke-width="{stroke_width}"/>'
        ),
        f"<title>{escape(name)}</title>",
    ]
    markup.extend(_node_text(node, x + NODE_WIDTH / 2, y))
    return markup


def _edge_path(
    parent: str, child: str, positions: dict[str, tuple[float, float]]
) -> tuple[str, bool]:
    """Собирает SVG-путь между двумя узлами."""
    if parent == child:
        x, y = positions[parent]
        start_x = x + NODE_WIDTH
        center_y = y + NODE_HEIGHT / 2
        path = (
            f"M {start_x:.1f},{center_y - 10:.1f} "
            f"C {start_x + 70:.1f},{center_y - 50:.1f} "
            f"{start_x + 70:.1f},{center_y + 50:.1f} "
            f"{start_x:.1f},{center_y + 10:.1f}"
        )
        return path, True
    parent_x, parent_y = positions[parent]
    child_x, child_y = positions[child]
    start_x = parent_x + NODE_WIDTH / 2
    start_y = parent_y + NODE_HEIGHT
    end_x = child_x + NODE_WIDTH / 2
    end_y = child_y
    bend = 60 if end_y < start_y else 0
    control_x = start_x + bend
    path = (
        f"M {start_x:.1f},{start_y:.1f} "
        f"C {control_x:.1f},{start_y + 30:.1f} "
        f"{control_x:.1f},{end_y - 30:.1f} "
        f"{end_x:.1f},{end_y:.1f}"
    )
    return path, end_y < start_y


def _edge_markup(
    parent: str,
    child: str,
    positions: dict[str, tuple[float, float]],
    is_cycle: bool,
) -> str:
    """Собирает SVG-разметку одного ребра зависимости."""
    path, points_up = _edge_path(parent, child, positions)
    cycle = is_cycle or points_up
    color = CYCLE_COLOR if cycle else "#5b6b7c"
    marker = "arrow-cycle" if cycle else "arrow"
    dash = ' stroke-dasharray="6 4"' if cycle else ""
    return (
        f'<path d="{path}" fill="none" stroke="{color}" '
        f'stroke-width="1.5"{dash} marker-end="url(#{marker})"/>'
    )


def render_fallback_svg(graph: DependencyGraph) -> str:
    """Строит простой многоуровневый SVG без внешних инструментов."""
    width, height, positions = _layout(graph)
    cycles = cycle_packages(graph)
    lines = _header(width, height, graph.root)
    lines.extend(_defs())
    for edge in graph.edges:
        is_cycle = (edge.parent, edge.child) in graph.cycles
        lines.append(
            _edge_markup(edge.parent, edge.child, positions, is_cycle)
        )
    for name, node in graph.nodes.items():
        lines.extend(_node_markup(name, node, positions[name], name in cycles))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _write(path: Path, content: str) -> None:
    """Записывает текст в файл с понятным сообщением об ошибке."""
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RenderError(
            f"не удалось записать изображение {path}: {exc}"
        ) from exc


def write_svg(
    dot_source: str, graph: DependencyGraph, output: Path
) -> str:
    """Записывает SVG и возвращает имя использованного рендерера."""
    dot = shutil.which("dot")
    if dot:
        try:
            completed = subprocess.run(
                [dot, "-Tsvg"],
                input=dot_source,
                text=True,
                capture_output=True,
                timeout=DOT_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            graph.warnings.append(f"ошибка Graphviz: {exc}")
        else:
            if completed.returncode == 0 and "<svg" in completed.stdout:
                _write(output, completed.stdout)
                return "graphviz"
            graph.warnings.append(
                "Graphviz не вернул SVG; используется встроенный рендерер"
            )
    _write(output, render_fallback_svg(graph))
    return "встроенный"
