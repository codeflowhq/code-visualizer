from __future__ import annotations

from typing import Any

from ..models import EdgeKind, NodeKind, VisualEdge, VisualNode
from ..utils.structure_detection import _collect_linked_list_labels
from ..view_utils import (
    _format_container_stub,
    _format_scalar_html,
    _is_scalar_value,
    _stable_svg_id,
)
from .common import (
    attach_view_title,
    new_node_id,
    render_nested_preview,
    safe_dot_token,
)


def build_linked_list_view_nodes(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    logical_name = name.split(" [step ", 1)[0]
    seq = _collect_linked_list_labels(value, runtime["item_limit"])
    if seq is None:
        raise TypeError("linked_list_node view expects objects with .next")
    values, truncated = seq

    graph = runtime["graph"]
    graph.graph_attrs.setdefault("rankdir", "LR")
    graph.graph_attrs.setdefault("nodesep", "0.18")
    graph.graph_attrs.setdefault("ranksep", "0.30")

    root_id = new_node_id(runtime, "linked_exp")
    graph.add_node(
        VisualNode(
            root_id,
            NodeKind.OBJECT,
            "",
            {"kind": "linked_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}},
        )
    )
    attach_view_title(runtime, root_id, name, "linked_list_node")

    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0
    occurrence_counts: dict[str, int] = {}

    prev_id: str | None = None
    for idx, item in enumerate(values):
        slot_name = f"{name}[{idx}]"
        if _is_scalar_value(item):
            scalar_key = str(item)
            occurrence = occurrence_counts.get(scalar_key, 0)
            occurrence_counts[scalar_key] = occurrence + 1
            node_id = safe_dot_token("linked_item", logical_name or "linked", scalar_key, occurrence)
            svg_id = _stable_svg_id(logical_name or "linked", "linked", "item", scalar_key, occurrence)
            content_html = _format_scalar_html(item)
        else:
            node_id = safe_dot_token("linked_node", logical_name or "linked", idx)
            svg_id = _stable_svg_id(logical_name or "linked", "linked", "node", idx)
            content_html = render_nested_preview(item, cell_depth, item_limit, slot_name)
            if not content_html:
                content_html = _format_container_stub(item)

        node_label = (
            "<table border='1' cellborder='1' cellspacing='0' cellpadding='0'>"
            "<tr>"
            f"<td align='center' bgcolor='#ffffff' cellpadding='6'>{content_html}</td>"
            "<td align='center' bgcolor='#f8fafc' cellpadding='6'><font color='#94a3b8' point-size='10'>next</font></td>"
            "</tr>"
            "</table>"
        )
        graph.add_node(
            VisualNode(
                node_id,
                NodeKind.OBJECT,
                node_label,
                {
                    "kind": "linked_list_node",
                    "html_label": True,
                    "node_attrs": {
                        "shape": "plain",
                        "color": "#cbd5e1",
                        "penwidth": "1.1",
                        "id": svg_id,
                    },
                },
            )
        )
        if prev_id is None:
            graph.add_edge(VisualEdge(root_id, node_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}}))
        else:
            graph.add_edge(VisualEdge(prev_id, node_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"color": "#6b7280", "penwidth": "1.2", "arrowhead": "normal"}}))
        prev_id = node_id

    tail_id = safe_dot_token("linked_tail", logical_name or "linked")
    tail_text = "…" if truncated else "∅"
    tail_label = (
        "<table border='1' cellborder='1' cellspacing='0' cellpadding='6'>"
        f"<tr><td align='center' bgcolor='#ffffff'><font color='#9ca3af'>{tail_text}</font></td></tr>"
        "</table>"
    )
    graph.add_node(
        VisualNode(
            tail_id,
            NodeKind.OBJECT,
            tail_label,
            {"html_label": True, "node_attrs": {"shape": "plain", "color": "#cbd5e1", "penwidth": "1.0", "id": _stable_svg_id(logical_name or "linked", "linked", "tail")}},
        )
    )
    if prev_id is None:
        graph.add_edge(VisualEdge(root_id, tail_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}}))
    else:
        graph.add_edge(VisualEdge(prev_id, tail_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"color": "#9ca3af", "penwidth": "1.1", "arrowhead": "normal"}}))

    return root_id
