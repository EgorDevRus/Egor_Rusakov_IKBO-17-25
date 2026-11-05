"""Graphviz DOT serialization of a dependency graph."""

from ..graph import cycle_packages
from ..models import BUILD, DEV, DependencyGraph, GraphEdge, GraphNode

ROOT_FILL = "#ffe8a3"
CYCLE_FILL = "#f8d7da"
NODE_FILL = "#dce9f7"
NODE_STROKE = "#33475b"
CYCLE_COLOR = "#c0392b"


def _escape(text: str) -> str:
    """Escape a DOT string body."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _quote(text: str) -> str:
    """Quote and escape one DOT identifier."""
    return f'"{_escape(text)}"'


def _node_label(node: GraphNode) -> str:
    """Build a DOT label for a node."""
    parts = [node.package.name]
    if node.package.version:
        parts.append(node.package.version)
    escaped = "\\n".join(_escape(part) for part in parts)
    return f'"{escaped}"'


def _node_attributes(node: GraphNode, in_cycle: bool) -> str:
    """Build DOT attributes for a node."""
    if node.is_root:
        fill = ROOT_FILL
    elif in_cycle:
        fill = CYCLE_FILL
    else:
        fill = NODE_FILL
    return (
        f"label={_node_label(node)}, fillcolor={_quote(fill)}, "
        f"color={_quote(NODE_STROKE)}"
    )


def _edge_attributes(edge: GraphEdge, in_cycle: bool) -> str:
    """Build DOT attributes for an edge."""
    attributes = ['color="#5b6b7c"']
    if edge.kind == BUILD:
        attributes.append('label="build"')
        attributes.append('style="dashed"')
    elif edge.kind == DEV:
        attributes.append('label="dev"')
        attributes.append('style="dotted"')
    elif edge.optional:
        attributes.append('style="dashed"')
    if in_cycle:
        attributes = [
            f"color={_quote(CYCLE_COLOR)}",
            'penwidth="2"',
            'style="bold"',
            'label="cycle"',
        ]
    return ", ".join(attributes)


def render_dot(graph: DependencyGraph) -> str:
    """Return a Graphviz DOT document for ``graph``."""
    cycles = cycle_packages(graph)
    lines = [
        "digraph dependencies {",
        "  rankdir=LR;",
        '  bgcolor="white";',
        '  node [shape="box", style="rounded,filled", fontname="Helvetica"];',
        '  edge [fontname="Helvetica", fontsize="10"];',
    ]
    for name, node in graph.nodes.items():
        attributes = _node_attributes(node, name in cycles)
        lines.append(f"  {_quote(name)} [{attributes}];")
    for edge in graph.edges:
        attributes = _edge_attributes(
            edge, (edge.parent, edge.child) in graph.cycles
        )
        lines.append(
            f"  {_quote(edge.parent)} -> {_quote(edge.child)} [{attributes}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"
