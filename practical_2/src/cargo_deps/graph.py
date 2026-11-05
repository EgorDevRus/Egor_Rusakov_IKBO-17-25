"""Breadth-first dependency collection and graph algorithms.

The collector walks the graph level by level and recurses into the next
level.  Nodes are visited at most once, which both keeps the traversal
finite for cyclic graphs and produces the BFS layering used by the
renderers.
"""

from .errors import SourceError
from .models import (
    DEV,
    Dependency,
    DependencyGraph,
    GraphEdge,
    GraphNode,
    ResolvedPackage,
)
from .sources.base import DependencySource

MAX_DEPTH = 100
UNLIMITED_DEPTH = 0
WHITE = 0
GRAY = 1
BLACK = 2
DONE = BLACK
ALWAYS_FALSE_TARGETS = frozenset({"cfg(any())", "cfg(false)", "cfg(FALSE)"})


class GraphBuilder:
    """Collect a transitive dependency graph with a recursive BFS."""

    def __init__(
        self,
        source: DependencySource,
        filter_text: str = "",
        include_dev: bool = False,
        include_optional: bool = False,
        max_depth: int = UNLIMITED_DEPTH,
    ) -> None:
        """Configure traversal filters and the depth limit."""
        self._source = source
        self._filter = filter_text
        self._include_dev = include_dev
        self._include_optional = include_optional
        self._limit = max_depth if max_depth > UNLIMITED_DEPTH else MAX_DEPTH
        self._depth_warned = False

    def build(
        self, root_name: str, root_version: str | None = None
    ) -> DependencyGraph:
        """Resolve the root and return its transitive dependency graph."""
        root = self._source.resolve_root(root_name, root_version)
        graph = DependencyGraph(root=root.name)
        graph.add_node(GraphNode(root, depth=0, is_root=True))
        if self._filter and self._filter in root.name:
            graph.warnings.append(
                f"root package {root.name!r} matches the filter and is kept"
            )
        self._walk([root], {root.name}, graph, 1)
        graph.cycles = detect_cycles(graph)
        return graph

    def _skip(self, dependency: Dependency) -> bool:
        """Return true when a dependency must not be traversed."""
        if self._filter and self._filter in dependency.name:
            return True
        if dependency.target in ALWAYS_FALSE_TARGETS:
            return True
        if dependency.kind == DEV and not self._include_dev:
            return True
        if dependency.optional and not self._include_optional:
            return True
        return False

    def _walk(
        self,
        frontier: list[ResolvedPackage],
        visited: set[str],
        graph: DependencyGraph,
        depth: int,
    ) -> None:
        """Process one BFS layer and recurse into the next one."""
        if not frontier:
            return
        if depth > self._limit:
            if not self._depth_warned:
                graph.warnings.append(
                    f"traversal stopped at max depth {self._limit}"
                )
                self._depth_warned = True
            return
        next_frontier: list[ResolvedPackage] = []
        for package in frontier:
            self._expand(package, depth, visited, next_frontier, graph)
        self._walk(next_frontier, visited, graph, depth + 1)

    def _expand(
        self,
        package: ResolvedPackage,
        depth: int,
        visited: set[str],
        next_frontier: list[ResolvedPackage],
        graph: DependencyGraph,
    ) -> None:
        """Add all direct dependencies of one package."""
        try:
            dependencies = self._source.dependencies(package)
        except SourceError as exc:
            raise SourceError(
                f"cannot read dependencies of {package.name}: {exc}"
            ) from exc
        for dependency in dependencies:
            if self._skip(dependency):
                continue
            child = self._source.resolve_dependency(dependency)
            if child is None:
                graph.warnings.append(
                    f"cannot resolve {dependency.name!r} "
                    f"{dependency.requirement or ''}".rstrip()
                )
                continue
            if child.name not in graph.nodes:
                graph.add_node(GraphNode(child, depth=depth))
            if child.name not in visited:
                visited.add(child.name)
                next_frontier.append(child)
            graph.add_edge(
                GraphEdge(
                    parent=package.name,
                    child=child.name,
                    kind=dependency.kind,
                    optional=dependency.optional,
                    target=dependency.target,
                )
            )


def detect_cycles(graph: DependencyGraph) -> set[tuple[str, str]]:
    """Return back edges that close cycles, using a recursive DFS."""
    colors: dict[str, int] = {}
    cycles: set[tuple[str, str]] = set()

    def visit(name: str) -> None:
        """Depth-first traversal that records back edges."""
        colors[name] = GRAY
        for edge in graph.children(name):
            color = colors.get(edge.child, WHITE)
            if color == GRAY:
                cycles.add((edge.parent, edge.child))
            elif color == WHITE:
                visit(edge.child)
        colors[name] = BLACK

    visit(graph.root)
    return cycles


def load_order(graph: DependencyGraph) -> list[str]:
    """Return a dependencies-first order, breaking cycles defensively."""
    state: dict[str, int] = {}
    order: list[str] = []

    def visit(name: str) -> None:
        """Append a node after all of its dependencies."""
        current = state.get(name, WHITE)
        if current in {DONE, GRAY}:
            return
        state[name] = GRAY
        for edge in sorted(graph.children(name), key=lambda item: item.child):
            visit(edge.child)
        state[name] = DONE
        order.append(name)

    visit(graph.root)
    return order


def cycle_packages(graph: DependencyGraph) -> set[str]:
    """Return all packages that participate in a detected cycle."""
    return {name for pair in graph.cycles for name in pair}
