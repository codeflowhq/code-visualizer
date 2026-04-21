from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..models import EdgeKind, NodeKind, VisualEdge, VisualNode
from ..utils.value_formatting import estimate_visual_height, estimate_visual_width
from ..view_utils import (
    _format_container_stub,
    _format_nested_value,
    _format_scalar_html,
    _is_scalar_value,
    _stable_svg_id,
)
from .common import flatten_nested_preview_frame, new_node_id, safe_dot_token


def build_array_view_node_cells(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from .nested import experimental_array_nested_resolver, make_nested_renderer

    logical_name = name.split(" [step ", 1)[0]
    if isinstance(value, (set, frozenset)):
        array = sorted(value, key=lambda x: str(x))
    elif isinstance(value, Mapping) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("array_cells_node view expects a list-like input")
    elif hasattr(value, "__iter__") and hasattr(value, "__len__"):
        array = list(value)
    else:
        raise TypeError("array_cells_node view expects a list-like input")

    graph = runtime["graph"]
    graph.graph_attrs.setdefault("rankdir", "TB")
    graph.graph_attrs.setdefault("nodesep", "0.006")
    graph.graph_attrs.setdefault("ranksep", "0.06")
    graph.graph_attrs.setdefault("fontname", "Helvetica")
    graph.graph_attrs.setdefault("fontsize", "16")
    graph.graph_attrs.setdefault("fontcolor", "#0f172a")
    if runtime.get("show_titles", True):
        graph.graph_attrs["label"] = f"<<font point-size='16' color='#0f172a'><b>{logical_name}</b></font>>"
    graph.graph_attrs.setdefault("labelloc", "t")
    graph.graph_attrs.setdefault("labeljust", "c")

    root_id = new_node_id(runtime, "arr_exp")
    graph.add_node(
        VisualNode(
            root_id,
            NodeKind.OBJECT,
            "",
            {"kind": "array_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}},
        )
    )

    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0
    original_resolver = runtime["resolver"]
    runtime["resolver"] = experimental_array_nested_resolver(runtime, original_resolver)
    try:
        limit = min(len(array), item_limit)
        visible_items = array[:limit]
        value_cell_height = max(
            30,
            min(420, max((estimate_visual_height(item, item_limit) for item in visible_items), default=30)),
        )
        value_cell_width = max(
            54,
            min(920, max((estimate_visual_width(item, item_limit) for item in visible_items), default=54)),
        )
        occurrence_counts: dict[str, int] = {}
        prev_id: str | None = None
        for idx in range(limit):
            item = array[idx]
            slot_name = f"{name}[{idx}]"
            if _is_scalar_value(item):
                scalar_key = str(item)
                occurrence = occurrence_counts.get(scalar_key, 0)
                occurrence_counts[scalar_key] = occurrence + 1
                node_id = safe_dot_token("arr_item", logical_name or "array", scalar_key, occurrence)
                svg_id = _stable_svg_id(logical_name or "array", "array", "item", scalar_key, occurrence)
                content_html = _format_scalar_html(item)
            else:
                node_id = safe_dot_token("arr_cell", logical_name or "array", idx)
                svg_id = _stable_svg_id(logical_name or "array", "array", "cell", idx)
                if isinstance(item, (list, tuple, set, frozenset)):
                    content_html = _format_nested_value(item, cell_depth, item_limit, None, slot_name)
                else:
                    nested_renderer = make_nested_renderer(runtime, node_id, f"{node_id}_value", slot_name)
                    content_html = flatten_nested_preview_frame(
                        nested_renderer(item, slot_name, cell_depth) or _format_container_stub(item)
                    )
            node_label = (
                "<table border='1' cellborder='1' cellspacing='0' cellpadding='0'>"
                f"<tr><td port='{node_id}_value' width='{value_cell_width}' height='{value_cell_height}' fixedsize='true' align='center' bgcolor='#ffffff' cellpadding='2'>{content_html}</td></tr>"
                f"<tr><td align='center' bgcolor='#ffffff' cellpadding='1'><font color='#94a3b8' point-size='10'>{idx}</font></td></tr>"
                "</table>"
            )
            graph.add_node(
                VisualNode(
                    node_id,
                    NodeKind.OBJECT,
                    node_label,
                    {
                        "kind": "array_cell",
                        "html_label": True,
                        "rank": "array_items",
                        "node_attrs": {"shape": "plain", "color": "#cbd5e1", "penwidth": "1.1", "id": svg_id},
                    },
                )
            )
            if prev_id is None:
                graph.add_edge(VisualEdge(root_id, node_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}}))
            else:
                graph.add_edge(VisualEdge(prev_id, node_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}}))
            prev_id = node_id
    finally:
        runtime["resolver"] = original_resolver

    return root_id
