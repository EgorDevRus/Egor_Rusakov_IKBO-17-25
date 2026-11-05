"""Рендерер дерева зависимостей в виде обычного текста."""

from ..models import BUILD, DEV, DependencyGraph, GraphEdge

CYCLE_MARK = "[цикл]"
SEEN_MARK = "[уже показан]"
BRANCH = "├── "
LAST_BRANCH = "└── "
PIPE = "│   "
SPACE = "    "


def _label(name: str, graph: DependencyGraph) -> str:
    """Возвращает имя пакета с версией, если она известна."""
    version = graph.nodes[name].package.version
    return f"{name} {version}" if version else name


def _suffix(edge: GraphEdge, is_cycle: bool, is_seen: bool) -> str:
    """Собирает пометку, выводимую после узла дерева."""
    markers: list[str] = []
    if is_cycle:
        markers.append(CYCLE_MARK)
    elif is_seen:
        markers.append(SEEN_MARK)
    if edge.kind == BUILD:
        markers.append("[сборка]")
    elif edge.kind == DEV:
        markers.append("[разработка]")
    if edge.optional:
        markers.append("[необязательная]")
    return f" {' '.join(markers)}" if markers else ""


def _render_children(
    graph: DependencyGraph,
    name: str,
    prefix: str,
    ancestors: frozenset[str],
    seen: set[str],
    lines: list[str],
) -> None:
    """Добавляет дочерние узлы одного узла в дерево."""
    edges = sorted(graph.children(name), key=lambda item: item.child)
    for index, edge in enumerate(edges):
        is_last = index == len(edges) - 1
        connector = LAST_BRANCH if is_last else BRANCH
        child = edge.child
        is_cycle = child in ancestors
        suffix = _suffix(edge, is_cycle, child in seen)
        lines.append(f"{prefix}{connector}{_label(child, graph)}{suffix}")
        if is_cycle or child in seen:
            continue
        seen.add(child)
        extension = SPACE if is_last else PIPE
        _render_children(
            graph,
            child,
            prefix + extension,
            ancestors | {child},
            seen,
            lines,
        )


def render_ascii(graph: DependencyGraph) -> str:
    """Возвращает дерево зависимостей в виде текстового блока."""
    lines = [_label(graph.root, graph)]
    seen = {graph.root}
    _render_children(
        graph,
        graph.root,
        "",
        frozenset({graph.root}),
        seen,
        lines,
    )
    return "\n".join(lines)
