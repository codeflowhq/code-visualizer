from __future__ import annotations

import re
from html import escape as html_escape
from typing import Any

from ..models import EdgeKind, NodeKind, VisualEdge, VisualNode
from ..view_utils import (
    _format_container_stub,
    _format_scalar_html,
    _is_scalar_value,
    _stable_svg_id,
)
from .common import (
    flatten_nested_preview_frame,
    new_node_id,
    render_nested_preview,
    safe_dot_token,
)


def _hash_table_focus_indices(focus_path: str | None, logical_name: str) -> tuple[int | None, int | None]:
    if not focus_path:
        return None, None
    if not focus_path.startswith(logical_name):
        return None, None
    suffix = focus_path[len(logical_name):]
    matches = re.findall(r"\[(\d+)\]", suffix)
    if not matches:
        return None, None
    bucket_idx = int(matches[0])
    item_idx = int(matches[1]) if len(matches) > 1 else None
    return bucket_idx, item_idx


def _configure_hash_table_graph(graph: Any, name: str, *, show_titles: bool) -> None:
    graph.graph_attrs.setdefault("rankdir", "TB")
    graph.graph_attrs.setdefault("nodesep", "0.42")
    graph.graph_attrs.setdefault("ranksep", "0.36")
    graph.graph_attrs.setdefault("fontname", "Helvetica")
    graph.graph_attrs.setdefault("fontsize", "16")
    graph.graph_attrs.setdefault("fontcolor", "#0f172a")
    if show_titles:
        graph.graph_attrs["label"] = (
            f"<<font point-size='16' color='#0f172a'><b>{html_escape(name)}</b></font>"
            f"<br/><font point-size='10' color='#94a3b8'>hash table node</font>>"
        )
    graph.graph_attrs.setdefault("labelloc", "t")
    graph.graph_attrs.setdefault("labeljust", "c")


def _hash_bucket_head_node(logical_name: str, idx: int, *, is_focused: bool) -> VisualNode:
    head_fill = "#dbeafe" if is_focused else "#ffffff"
    head_border = "#60a5fa" if is_focused else "#4b5563"
    head_penwidth = "1.7" if is_focused else "1.2"
    idx_fill = "#dbeafe" if is_focused else "#ffffff"
    bucket_label = (
        "<table border='0' cellborder='1' cellspacing='0' cellpadding='0'>"
        f"<tr><td align='center' bgcolor='{head_fill}' cellpadding='6'><font point-size='14' color='#111827'><b>H</b></font></td></tr>"
        f"<tr><td align='center' bgcolor='{idx_fill}' cellpadding='3'><font point-size='11' color='#ef4444'>{idx}</font></td></tr>"
        "</table>"
    )
    return VisualNode(
        safe_dot_token("hash_bucket_node", logical_name, idx),
        NodeKind.OBJECT,
        bucket_label,
        {
            "kind": "hash_bucket_node",
            "html_label": True,
            "rank": "hash_heads",
            "node_attrs": {
                "shape": "plain",
                "color": head_border,
                "penwidth": head_penwidth,
                "id": _stable_svg_id(logical_name, "hash", "bucket", idx),
            },
        },
    )


def _hash_chain_node(
    logical_name: str,
    idx: int,
    item_idx: int,
    item_preview: str,
    *,
    chain_focus: bool,
) -> VisualNode:
    item_fill = "#eff6ff" if chain_focus else "#ffffff"
    item_border = "#60a5fa" if chain_focus else "#6b7280"
    item_penwidth = "1.5" if chain_focus else "1.0"
    chain_label = (
        "<table border='1' cellborder='1' cellspacing='0' cellpadding='0'>"
        "<tr>"
        f"<td align='center' bgcolor='{item_fill}' cellpadding='4'>{item_preview}</td>"
        "</tr>"
        "</table>"
    )
    return VisualNode(
        safe_dot_token("hash_chain_node", logical_name, idx, item_idx),
        NodeKind.OBJECT,
        chain_label,
        {
            "kind": "hash_chain_node",
            "html_label": True,
            "rank": f"hash_chain_{idx}_{item_idx}",
            "node_attrs": {
                "shape": "plain",
                "color": item_border,
                "penwidth": item_penwidth,
                "id": _stable_svg_id(logical_name, "hash", "chain", idx, item_idx),
            },
        },
    )


def build_hash_table_view_node_heads_chains(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    logical_name = name.split(" [step ", 1)[0]
    if not isinstance(value, list):
        raise TypeError("hash_table_node view expects list input")

    graph = runtime["graph"]
    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    preview_depth = depth_budget - 1 if depth_budget > 0 else 0
    limit = min(len(value), item_limit)
    focus_idx, focus_item_idx = _hash_table_focus_indices(runtime.get("focus_path"), logical_name)

    _configure_hash_table_graph(graph, name, show_titles=runtime.get("show_titles", True))

    root_id = new_node_id(runtime, "hash_exp")
    graph.add_node(
        VisualNode(
            root_id,
            NodeKind.OBJECT,
            "",
            {"kind": "hash_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}},
        )
    )

    head_anchor_id = new_node_id(runtime, "hash_head_row")
    graph.add_node(
        VisualNode(
            head_anchor_id,
            NodeKind.OBJECT,
            "",
            {
                "kind": "hash_head_anchor",
                "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"},
            },
        )
    )
    graph.add_edge(
        VisualEdge(
            root_id,
            head_anchor_id,
            type=EdgeKind.LAYOUT,
            meta={"edge_attrs": {"style": "invis", "constraint": "false"}},
        )
    )

    prev_head_id: str | None = None
    for idx in range(limit):
        bucket = value[idx]
        is_focused = focus_idx is not None and focus_idx == idx
        bucket_node = _hash_bucket_head_node(logical_name, idx, is_focused=is_focused)
        bucket_id = bucket_node.id
        graph.add_node(bucket_node)
        graph.add_edge(
            VisualEdge(
                head_anchor_id,
                bucket_id,
                type=EdgeKind.LAYOUT,
                meta={"edge_attrs": {"style": "invis", "constraint": "false", "weight": "12"}},
            )
        )
        if prev_head_id is not None:
            graph.add_edge(
                VisualEdge(
                    prev_head_id,
                    bucket_id,
                    type=EdgeKind.LAYOUT,
                    meta={"edge_attrs": {"style": "invis", "constraint": "false", "weight": "4"}},
                )
            )
        prev_head_id = bucket_id

        bucket_items = bucket if isinstance(bucket, list) else ([] if bucket is None else [bucket])
        if not bucket_items:
            continue

        chain_limit = min(len(bucket_items), item_limit)
        prev_chain_node_id = bucket_id
        for item_idx in range(chain_limit):
            item = bucket_items[item_idx]
            chain_focus = focus_idx is not None and focus_idx == idx and (focus_item_idx is None or focus_item_idx == item_idx)

            item_preview = render_nested_preview(item, preview_depth, item_limit, f"{name}[{idx}][{item_idx}]")
            if not item_preview:
                if _is_scalar_value(item):
                    item_preview = _format_scalar_html(item)
                else:
                    item_preview = _format_container_stub(item)
            item_preview = flatten_nested_preview_frame(item_preview)

            chain_node = _hash_chain_node(logical_name, idx, item_idx, item_preview, chain_focus=chain_focus)
            chain_node_id = chain_node.id
            graph.add_node(chain_node)
            graph.add_edge(
                VisualEdge(
                    prev_chain_node_id,
                    chain_node_id,
                    type=EdgeKind.LAYOUT,
                    meta={"edge_attrs": {"color": "#6b7280", "penwidth": "1.0", "arrowhead": "normal"}},
                )
            )
            prev_chain_node_id = chain_node_id

        if len(bucket_items) > item_limit:
            more_id = safe_dot_token("hash_more", logical_name, idx)
            more_label = (
                "<table border='1' cellborder='1' cellspacing='0' cellpadding='4'>"
                "<tr><td align='center' bgcolor='#f8fafc'><font color='#64748b'>…</font></td></tr>"
                "</table>"
            )
            graph.add_node(
                VisualNode(
                    more_id,
                    NodeKind.OBJECT,
                    more_label,
                    {
                        "html_label": True,
                        "rank": f"hash_chain_more_{idx}",
                        "node_attrs": {
                            "shape": "plain",
                            "color": "#cbd5e1",
                            "penwidth": "1.0",
                        },
                    },
                )
            )
            graph.add_edge(
                VisualEdge(
                    prev_chain_node_id,
                    more_id,
                    type=EdgeKind.LAYOUT,
                    meta={"edge_attrs": {"color": "#9ca3af", "style": "dashed", "arrowhead": "normal"}},
                )
            )

    if not value:
        empty_id = safe_dot_token("hash_empty", logical_name)
        empty_label = (
            "<table border='1' cellborder='1' cellspacing='0' cellpadding='8'>"
            "<tr><td align='center' bgcolor='#ffffff'>∅</td></tr></table>"
        )
        graph.add_node(
            VisualNode(
                empty_id,
                NodeKind.OBJECT,
                empty_label,
                {"html_label": True, "rank": "hash_empty", "node_attrs": {"shape": "plain", "color": "#cbd5e1", "penwidth": "1.0"}},
            )
        )
        graph.add_edge(
            VisualEdge(
                head_anchor_id,
                empty_id,
                type=EdgeKind.LAYOUT,
                meta={"edge_attrs": {"style": "invis", "constraint": "false"}},
            )
        )

    return root_id
