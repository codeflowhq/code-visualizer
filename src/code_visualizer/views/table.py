from __future__ import annotations

import re
from typing import Any

from ..models import EdgeKind, NodeKind, VisualEdge, VisualNode
from ..utils.value_formatting import estimate_table_column_widths
from ..view_utils import (
    _format_container_stub,
    _format_nested_value,
    _format_scalar_html,
    _is_scalar_value,
    _stable_svg_id,
    _table_cell_text,
)
from .common import new_node_id, safe_dot_token


def _extract_table_focus_key(focus_path: str | None, logical_name: str) -> str | None:
    if not focus_path or not focus_path.startswith(logical_name):
        return None
    suffix = focus_path[len(logical_name):]
    if not suffix:
        return None
    match = re.match(r"""\[(?:"([^"]+)"|'([^']+)')\]""", suffix)
    if match:
        return match.group(1) or match.group(2)
    if suffix.startswith("."):
        parts = suffix[1:].split(".", 1)
        return parts[0] if parts and parts[0] else None
    return None


def _table_column_widths(items: list[tuple[Any, Any]], item_limit: int) -> tuple[int, int, int]:
    key_width, value_width = estimate_table_column_widths(items, item_limit)
    key_width = min(220, max(92, key_width))
    value_width = min(920, max(92, value_width))
    total_width = key_width + value_width
    return key_width, value_width, total_width


def build_table_view_node_rows(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from .nested import make_nested_renderer

    logical_name = name.split(" [step ", 1)[0]
    if not isinstance(value, dict):
        raise TypeError("table_node view expects dict input")

    items = list(value.items())
    item_limit = runtime["item_limit"]
    limit = min(len(items), item_limit)
    depth_budget = max(0, depth)
    inner_depth = depth_budget - 1 if depth_budget > 0 else 0
    focus_path = runtime.get("focus_path")
    focused_key = _extract_table_focus_key(focus_path, logical_name)
    visible_items = items[:limit]
    key_width, value_width, total_width = _table_column_widths(visible_items, item_limit)

    graph = runtime["graph"]
    graph.graph_attrs.setdefault("rankdir", "TB")
    graph.graph_attrs.setdefault("nodesep", "0.01")
    graph.graph_attrs.setdefault("ranksep", "0.035")
    graph.graph_attrs.setdefault("fontname", "Helvetica")
    graph.graph_attrs.setdefault("fontsize", "16")
    graph.graph_attrs.setdefault("fontcolor", "#0f172a")
    if runtime.get("show_titles", True):
        graph.graph_attrs["label"] = f"<<font point-size='16' color='#0f172a'><b>{name}</b></font>>"
    graph.graph_attrs.setdefault("labelloc", "t")
    graph.graph_attrs.setdefault("labeljust", "c")

    root_id = new_node_id(runtime, "table_exp")
    graph.add_node(VisualNode(root_id, NodeKind.OBJECT, "", {"kind": "table_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}}))
    node_width_inches = f"{max(0.01, total_width / 72):.2f}"

    header_id = safe_dot_token("table_header", logical_name)
    header_label = (
        "<table BORDER='1' CELLBORDER='1' CELLSPACING='0' CELLPADDING='0'>"
        f"<tr><td WIDTH='{total_width}' FIXEDSIZE='TRUE' CELLPADDING='0'>"
        "<table BORDER='0' CELLBORDER='1' CELLSPACING='0' CELLPADDING='0'>"
        "<tr>"
        f"<td WIDTH='{key_width}' FIXEDSIZE='TRUE' ALIGN='CENTER' BGCOLOR='#e5e7eb' CELLPADDING='6'><font color='#0f172a'><b>Key</b></font></td>"
        f"<td WIDTH='{value_width}' FIXEDSIZE='TRUE' ALIGN='CENTER' BGCOLOR='#e5e7eb' CELLPADDING='6'><font color='#0f172a'><b>Value</b></font></td>"
        "</tr></table>"
        "</td></tr></table>"
    )
    graph.add_node(VisualNode(header_id, NodeKind.OBJECT, header_label, {"html_label": True, "rank": "table_header", "node_attrs": {"shape": "plain", "color": "#cbd5e1", "penwidth": "1.0", "width": node_width_inches}}))

    prev_node_id = header_id
    for idx in range(limit):
        key, val = items[idx]
        key_text = _table_cell_text(key)
        row_id = safe_dot_token("table_row", logical_name, key_text)
        value_port = f"{row_id}_value"
        nested_renderer = make_nested_renderer(runtime, row_id, value_port, f"{name}.{key}")
        if _is_scalar_value(val):
            value_html = _format_scalar_html(val)
        else:
            value_html = _format_nested_value(val, inner_depth, item_limit, nested_renderer, f"{name}.{key}")
            if not value_html:
                value_html = _format_container_stub(val)
            value_html = (
                "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
                f"<tr><td width='{value_width}' align='center'>{value_html}</td></tr>"
                "</table>"
            )

        is_focused = focused_key is not None and str(focused_key) == str(key_text)
        if is_focused:
            key_fill, value_fill, border_color, penwidth = "#dbeafe", "#eff6ff", "#60a5fa", "1.8"
        else:
            key_fill, value_fill, border_color, penwidth = "#f8fafc", "#ffffff", "#cbd5e1", "1.0"

        row_label = (
            "<table BORDER='1' CELLBORDER='1' CELLSPACING='0' CELLPADDING='0'>"
            f"<tr><td WIDTH='{total_width}' FIXEDSIZE='TRUE' CELLPADDING='0'>"
            "<table BORDER='0' CELLBORDER='1' CELLSPACING='0' CELLPADDING='0'>"
            "<tr>"
            f"<td WIDTH='{key_width}' FIXEDSIZE='TRUE' ALIGN='CENTER' BGCOLOR='{key_fill}' CELLPADDING='6'><font color='#0f172a' point-size='11'><b>{key_text}</b></font></td>"
            f"<td WIDTH='{value_width}' FIXEDSIZE='TRUE' PORT='{value_port}' ALIGN='CENTER' BGCOLOR='{value_fill}' CELLPADDING='6'>{value_html}</td>"
            "</tr></table>"
            "</td></tr></table>"
        )
        graph.add_node(VisualNode(row_id, NodeKind.OBJECT, row_label, {"kind": "table_row", "html_label": True, "rank": f"table_row_{idx}", "node_attrs": {"shape": "plain", "color": border_color, "penwidth": penwidth, "id": _stable_svg_id(logical_name, "table", "row", key_text), "width": node_width_inches}}))
        graph.add_edge(VisualEdge(prev_node_id, row_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}}))
        prev_node_id = row_id

    graph.add_edge(VisualEdge(root_id, header_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}}))
    return root_id
