"""Domain models shared by sources, graph builder and renderers."""

from dataclasses import dataclass, field

NORMAL = "normal"
BUILD = "build"
DEV = "dev"
EDGE_KINDS = frozenset({NORMAL, BUILD, DEV})


@dataclass(frozen=True)
class ResolvedPackage:
    """A concrete package release selected by a dependency source."""

    name: str
    version: str | None = None
    yanked: bool = False


@dataclass(frozen=True)
class Dependency:
    """A dependency declaration of one package.

    ``name`` is the package that will be loaded.  ``requirement`` is the
    Cargo version requirement, and ``registry`` is set for dependencies
    hosted outside the analyzed registry.
    """

    name: str
    requirement: str | None = None
    kind: str = NORMAL
    optional: bool = False
    target: str | None = None
    registry: str | None = None


@dataclass(frozen=True)
class GraphNode:
    """A node of the dependency graph."""

    package: ResolvedPackage
    depth: int
    is_root: bool = False


@dataclass(frozen=True)
class GraphEdge:
    """A directed dependency edge from ``parent`` to ``child``."""

    parent: str
    child: str
    kind: str = NORMAL
    optional: bool = False
    target: str | None = None


@dataclass
class DependencyGraph:
    """Dependency graph produced by the BFS collector."""

    root: str
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    cycles: set[tuple[str, str]] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        """Add a node unless a package with the same name is present."""
        self.nodes.setdefault(node.package.name, node)

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge, ignoring exact duplicates of parent and child."""
        pair = (edge.parent, edge.child)
        if any(item.parent == pair[0] and item.child == pair[1]
               for item in self.edges):
            return
        self.edges.append(edge)

    def children(self, name: str) -> list[GraphEdge]:
        """Return all outgoing edges of ``name``."""
        return [edge for edge in self.edges if edge.parent == name]

    @property
    def package_count(self) -> int:
        """Return the number of packages in the graph."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of unique dependency edges."""
        return len(self.edges)
