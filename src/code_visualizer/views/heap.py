from __future__ import annotations

from html import escape as html_escape
from typing import Any

from ..models import EdgeKind, NodeKind, VisualEdge, VisualNode
from ..renderers import build_tree
from ..view_types import ViewKind
from ..view_utils import (
    _format_container_stub,
    _format_scalar_html,
    _is_scalar_value,
    _stable_svg_id,
)
from .common import (
    merge_visual_graph,
    new_node_id,
    render_nested_preview,
    safe_dot_token,
)


def _heap_tree_payload(heap: list[Any], item_limit: int) -> Any | None:
    if not heap:
        return None
    limit = min(len(heap), item_limit)

    def build(idx: int) -> Any | None:
        if idx >= limit or idx >= len(heap):
            return None
        node: dict[str, Any] = {"label": str(heap[idx])}
        children: list[Any] = []
        left = build(2 * idx + 1)
        right = build(2 * idx + 2)
        if left is not None:
            children.append(left)
        if right is not None:
            children.append(right)
        node["children"] = children
        return node

    return build(0)


def _build_heap_array_node_strip(runtime: dict[str, Any], value: list[Any], name: str, depth: int) -> str:
    logical_name = name.split(" [step ", 1)[0]
    graph = runtime["graph"]
    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0
    limit = min(len(value), item_limit)

    strip_root_id = new_node_id(runtime, "heap_arr")
    graph.add_node(
        VisualNode(
            strip_root_id,
            NodeKind.OBJECT,
            "",
            {"kind": "heap_array_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}},
        )
    )

    occurrence_counts: dict[str, int] = {}
    prev_id: str | None = None
    for idx in range(limit):
        item = value[idx]
        slot_name = f"{name}[{idx}]"
        if _is_scalar_value(item):
            scalar_key = str(item)
            occurrence = occurrence_counts.get(scalar_key, 0)
            occurrence_counts[scalar_key] = occurrence + 1
            node_id = safe_dot_token("heap_item", logical_name or "heap", scalar_key, occurrence)
            svg_id = _stable_svg_id(logical_name or "heap", "heap", "item", scalar_key, occurrence)
            content_html = _format_scalar_html(item)
        else:
            node_id = safe_dot_token("heap_cell", logical_name or "heap", idx)
            svg_id = _stable_svg_id(logical_name or "heap", "heap", "cell", idx)
            content_html = render_nested_preview(item, cell_depth, item_limit, slot_name)
            if not content_html:
                content_html = _format_container_stub(item)

        node_label = (
            "<table border='1' cellborder='1' cellspacing='0' cellpadding='0'>"
            f"<tr><td align='center' bgcolor='#f8fafc' cellpadding='2'>{content_html}</td></tr>"
            f"<tr><td align='center' bgcolor='#ffffff' cellpadding='1'><font color='#94a3b8' point-size='10'>{idx}</font></td></tr>"
            "</table>"
        )
        graph.add_node(
            VisualNode(
                node_id,
                NodeKind.OBJECT,
                node_label,
                {
                    "kind": "heap_array_cell",
                    "html_label": True,
                    "rank": "heap_array_items",
                    "node_attrs": {
                        "shape": "plain",
                        "color": "#cbd5e1",
                        "penwidth": "1.0",
                        "id": svg_id,
                    },
                },
            )
        )
        if prev_id is None:
            graph.add_edge(VisualEdge(strip_root_id, node_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "12"}}))
        else:
            graph.add_edge(VisualEdge(prev_id, node_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "12"}}))
        prev_id = node_id

    if len(value) > item_limit and prev_id is not None:
        more_id = safe_dot_token("heap_more", logical_name or "heap")
        more_label = (
            "<table border='1' cellborder='1' cellspacing='0' cellpadding='4'>"
            "<tr><td align='center' bgcolor='#f8fafc'><font color='#64748b'>…</font></td></tr>"
            "<tr><td align='center' bgcolor='#ffffff' cellpadding='2'><font color='#94a3b8' point-size='10'>…</font></td></tr>"
            "</table>"
        )
        graph.add_node(
            VisualNode(
                more_id,
                NodeKind.ELLIPSIS,
                more_label,
                {"html_label": True, "rank": "heap_array_items", "node_attrs": {"shape": "plain", "color": "#cbd5e1", "penwidth": "1.0"}},
            )
        )
        graph.add_edge(VisualEdge(prev_id, more_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "12"}}))

    return strip_root_id


def build_heap_dual_view_node(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    if not isinstance(value, list):
        raise TypeError("heap_dual_node view expects list input")

    graph = runtime["graph"]
    graph.graph_attrs.setdefault("rankdir", "TB")
    graph.graph_attrs.setdefault("nodesep", "0.04")
    graph.graph_attrs.setdefault("ranksep", "0.16")
    graph.graph_attrs.setdefault("fontname", "Helvetica")
    graph.graph_attrs.setdefault("fontsize", "16")
    graph.graph_attrs.setdefault("fontcolor", "#0f172a")
    if runtime.get("show_titles", True):
        graph.graph_attrs["label"] = f"<<font point-size='16' color='#0f172a'><b>{html_escape(name)}</b></font>>"
    graph.graph_attrs.setdefault("labelloc", "t")
    graph.graph_attrs.setdefault("labeljust", "c")

    root_id = new_node_id(runtime, "heap_exp")
    graph.add_node(VisualNode(root_id, NodeKind.OBJECT, "", {"kind": "heap_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}}))

    array_root_id = _build_heap_array_node_strip(runtime, value, f"{name}[array]", depth)
    graph.add_edge(VisualEdge(root_id, array_root_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "24"}}))

    tree_payload = _heap_tree_payload(value, runtime["item_limit"])
    if tree_payload is not None:
        tree_root_hint, tree_graph = build_tree(
            tree_payload,
            name="",
            max_nodes=runtime["item_limit"],
            nested_depth=depth,
            max_items=runtime["item_limit"],
        )
        for node in tree_graph.nodes.values():
            if node.meta.get("cutoff"):
                continue
            node_attrs = dict(node.meta.get("node_attrs", {}))
            node_attrs.setdefault("shape", "circle")
            node_attrs.setdefault("style", "solid")
            node_attrs.setdefault("width", "0.6")
            node_attrs.setdefault("height", "0.6")
            node_attrs.setdefault("fixedsize", "false")
            node_attrs.setdefault("color", "#1f2933")
            node.meta["node_attrs"] = node_attrs
            node.meta.pop("html_label", None)
        tree_id = merge_visual_graph(runtime, tree_graph, new_node_id(runtime, ViewKind.TREE), root_hint=tree_root_hint)
    else:
        tree_id = new_node_id(runtime, "heap_empty")
        empty_html = "<table border='1' cellborder='1' cellspacing='0'><tr><td align='center'>∅</td></tr></table>"
        graph.add_node(VisualNode(tree_id, NodeKind.OBJECT, empty_html, {"html_label": True, "node_attrs": {"shape": "plain"}}))

    graph.add_edge(VisualEdge(array_root_id, tree_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "24"}}))
    return root_id
