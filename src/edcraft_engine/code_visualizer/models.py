from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

NodeType = Literal[
    "scalar", "list", "tuple", "dict", "set", "object", "entry", "ellipsis"
]

EdgeType = Literal[
    "contains", "index", "key", "value", "attr", "ref", "link"
]

ArtifactKind = Literal["graphviz", "mermaid", "markdown", "html", "text"]

@dataclass(frozen=True)
class VisualNode:
    id: str
    type: NodeType
    label: str
    meta: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class VisualEdge:
    src: str
    dst: str
    type: EdgeType = "link"
    label: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Anchor:
    """Named handles into the graph; graph may have 0 anchors."""
    name: str
    node_id: str
    kind: Literal["var", "focus", "selection"] = "var"
    meta: dict[str, Any] = field(default_factory=dict)

@dataclass
class VisualGraph:
    nodes: dict[str, VisualNode] = field(default_factory=dict)
    edges: list[VisualEdge] = field(default_factory=list)
    anchors: list[Anchor] = field(default_factory=list)  # replaces roots

    def add_node(self, node: VisualNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: VisualEdge) -> None:
        self.edges.append(edge)

@dataclass(frozen=True)
class Frame:
    step: int
    value: Any
    note: str = ""

@dataclass(frozen=True)
class Trace:
    name: str
    frames: list[Frame]

@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    content: str
    title: str | None = None
