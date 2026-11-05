"""Модели данных, общие для источников, построителя графа и рендереров."""

from dataclasses import dataclass, field

NORMAL = "normal"
BUILD = "build"
DEV = "dev"
EDGE_KINDS = frozenset({NORMAL, BUILD, DEV})


@dataclass(frozen=True)
class ResolvedPackage:
    """Конкретный релиз пакета, выбранный источником зависимостей."""

    name: str
    version: str | None = None
    yanked: bool = False


@dataclass(frozen=True)
class Dependency:
    """Объявление зависимости одного пакета.

    ``name`` — имя пакета, который будет загружен. ``requirement`` —
    требование Cargo к версии, ``registry`` задан для зависимостей из
    другого реестра.
    """

    name: str
    requirement: str | None = None
    kind: str = NORMAL
    optional: bool = False
    target: str | None = None
    registry: str | None = None


@dataclass(frozen=True)
class GraphNode:
    """Узел графа зависимостей."""

    package: ResolvedPackage
    depth: int
    is_root: bool = False


@dataclass(frozen=True)
class GraphEdge:
    """Направленное ребро зависимости от ``parent`` к ``child``."""

    parent: str
    child: str
    kind: str = NORMAL
    optional: bool = False
    target: str | None = None


@dataclass
class DependencyGraph:
    """Граф зависимостей, построенный обходом в ширину."""

    root: str
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    cycles: set[tuple[str, str]] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        """Добавляет узел, если пакета с таким именем ещё нет."""
        self.nodes.setdefault(node.package.name, node)

    def add_edge(self, edge: GraphEdge) -> None:
        """Добавляет ребро, пропуская точные дубликаты."""
        pair = (edge.parent, edge.child)
        if any(item.parent == pair[0] and item.child == pair[1]
               for item in self.edges):
            return
        self.edges.append(edge)

    def children(self, name: str) -> list[GraphEdge]:
        """Возвращает все исходящие рёбра пакета ``name``."""
        return [edge for edge in self.edges if edge.parent == name]

    @property
    def package_count(self) -> int:
        """Возвращает число пакетов в графе."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Возвращает число уникальных рёбер зависимостей."""
        return len(self.edges)
