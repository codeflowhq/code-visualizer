from __future__ import annotations

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
    matrix_focus_coords,
    new_node_id,
    render_nested_preview,
    safe_dot_token,
)


def _matrix_cell_dimensions(rows: list[list[Any]], row_limit: int, col_limit: int) -> tuple[int, int, int]:
    row_header_width = 54
    cell_width = 54
    cell_height = 30
    for r_idx in range(row_limit):
        row_header_width = max(row_header_width, 24 + len(str(r_idx)) * 10)
        row = rows[r_idx]
        for c_idx in range(min(col_limit, len(row))):
            text = str(row[c_idx])
            cell_width = max(cell_width, min(120, 26 + len(text) * 11))
    for c_idx in range(col_limit):
        cell_width = max(cell_width, 24 + len(str(c_idx)) * 10)
    return row_header_width, cell_width, cell_height


def build_matrix_view_node_cells(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:  # noqa: C901
    logical_name = name.split(" [step ", 1)[0]
    if not isinstance(value, (list, tuple)):
        raise TypeError("matrix_node view expects a list of lists/tuples")

    rows: list[list[Any]] = []
    for row in value:
        if not isinstance(row, (list, tuple)):
            raise TypeError("matrix_node view expects uniform sublists")
        rows.append(list(row))

    graph = runtime["graph"]
    graph.graph_attrs.setdefault("rankdir", "TB")
    graph.graph_attrs.setdefault("nodesep", "0.01")
    graph.graph_attrs.setdefault("ranksep", "0.055")
    if runtime.get("show_titles", True):
        graph.graph_attrs["label"] = f"<<font point-size='16' color='#0f172a'><b>{name}</b></font>>"
    graph.graph_attrs.setdefault("labelloc", "t")
    graph.graph_attrs.setdefault("labeljust", "c")
    graph.graph_attrs.setdefault("fontname", "Helvetica")
    graph.graph_attrs.setdefault("fontsize", "16")
    graph.graph_attrs.setdefault("fontcolor", "#0f172a")

    root_id = new_node_id(runtime, "matrix_exp")
    graph.add_node(VisualNode(root_id, NodeKind.OBJECT, "", {"kind": "matrix_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}}))

    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0
    row_count = len(rows)
    row_limit = min(row_count, min(item_limit, 25))
    width = max((len(r) for r in rows), default=0)
    col_limit = min(width, min(item_limit, 25))
    focus_coords = matrix_focus_coords(runtime.get("focus_path"))
    row_header_width, cell_width, cell_height = _matrix_cell_dimensions(rows, row_limit, col_limit)

    corner_id = safe_dot_token("matrix_corner", logical_name or "matrix")
    corner_label = (
        "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
        f"<tr><td width='{row_header_width}' height='{cell_height}'></td></tr>"
        "</table>"
    )
    graph.add_node(
        VisualNode(
            corner_id,
            NodeKind.OBJECT,
            corner_label,
            {
                "html_label": True,
                "rank": "matrix_headers",
                "node_attrs": {"shape": "plain", "color": "#ffffff", "penwidth": "0.0"},
            },
        )
    )

    col_header_ids: list[str] = []
    prev_col_id = corner_id
    for c_idx in range(col_limit):
        col_id = safe_dot_token("matrix_col", logical_name, c_idx)
        col_header_ids.append(col_id)
        is_focused_col = focus_coords is not None and focus_coords[1] == c_idx
        col_fill = "#dbeafe" if is_focused_col else "#f3f4f6"
        col_border = "#60a5fa" if is_focused_col else "#e2e8f0"
        col_label = (
            "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
            f"<tr><td width='{cell_width}' height='{cell_height}' align='center' bgcolor='{col_fill}' cellpadding='0'><font color='#dc2626' point-size='11'>{c_idx}</font></td></tr>"
            "</table>"
        )
        graph.add_node(VisualNode(col_id, NodeKind.OBJECT, col_label, {"html_label": True, "rank": "matrix_headers", "node_attrs": {"shape": "plain", "color": col_border, "penwidth": "0.8"}}))
        graph.add_edge(VisualEdge(prev_col_id, col_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "14"}}))
        prev_col_id = col_id

    row_header_ids: list[str] = []
    previous_row_cells: list[str] | None = None
    first_row_cells: list[str] | None = None

    for r_idx in range(row_limit):
        row = rows[r_idx]
        row_header_id = safe_dot_token("matrix_row", logical_name, r_idx)
        row_header_ids.append(row_header_id)
        is_focused_row = focus_coords is not None and focus_coords[0] == r_idx
        row_fill = "#fde68a" if is_focused_row else "#fef3c7"
        row_border = "#f59e0b" if is_focused_row else "#f8dca3"
        row_label = (
            "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
            f"<tr><td width='{row_header_width}' height='{cell_height}' align='center' bgcolor='{row_fill}' cellpadding='0'><font color='#b45309' point-size='11'>{r_idx}</font></td></tr>"
            "</table>"
        )
        graph.add_node(VisualNode(row_header_id, NodeKind.OBJECT, row_label, {"html_label": True, "rank": f"matrix_row_{r_idx}", "node_attrs": {"shape": "plain", "color": row_border, "penwidth": "0.8"}}))

        current_row_cells: list[str] = []
        for c_idx in range(col_limit):
            val = row[c_idx] if c_idx < len(row) else ""
            slot_name = f"{name}[{r_idx}][{c_idx}]"
            cell_focus = focus_coords is not None and focus_coords == (r_idx, c_idx)
            cell_graph_id = safe_dot_token("matrix_cell", logical_name, r_idx, c_idx)
            cell_svg_id = _stable_svg_id(logical_name, "matrix", "cell", r_idx, c_idx)
            if _is_scalar_value(val):
                cell_content = _format_scalar_html(val)
            else:
                cell_content = flatten_nested_preview_frame(render_nested_preview(val, cell_depth, item_limit, slot_name))
                if not cell_content:
                    cell_content = _format_container_stub(val)

            cell_fill = "#fff7ed" if cell_focus else "#ffffff"
            cell_border = "#f59e0b" if cell_focus else "#cbd5e1"
            cell_penwidth = "1.6" if cell_focus else "1.0"
            cell_label = (
                "<table border='1' cellborder='1' cellspacing='0' cellpadding='0'>"
                f"<tr><td width='{cell_width}' height='{cell_height}' align='center' bgcolor='{cell_fill}' cellpadding='0'>{cell_content}</td></tr>"
                "</table>"
            )
            graph.add_node(VisualNode(cell_graph_id, NodeKind.OBJECT, cell_label, {"kind": "matrix_cell", "html_label": True, "rank": f"matrix_row_{r_idx}", "node_attrs": {"shape": "plain", "color": cell_border, "penwidth": cell_penwidth, "id": cell_svg_id}}))
            current_row_cells.append(cell_graph_id)

        if current_row_cells and first_row_cells is None:
            first_row_cells = list(current_row_cells)

        if current_row_cells:
            graph.add_edge(VisualEdge(row_header_id, current_row_cells[0], type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "16"}}))
            for left, right in zip(current_row_cells, current_row_cells[1:], strict=False):
                graph.add_edge(VisualEdge(left, right, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "16"}}))

        if previous_row_cells is not None:
            graph.add_edge(VisualEdge(row_header_ids[-2], row_header_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "16"}}))
            for upper, lower in zip(previous_row_cells, current_row_cells, strict=False):
                graph.add_edge(VisualEdge(upper, lower, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "16"}}))

        previous_row_cells = current_row_cells

    if col_header_ids and first_row_cells:
        for col_id, cell_id in zip(col_header_ids, first_row_cells, strict=False):
            graph.add_edge(VisualEdge(col_id, cell_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "16"}}))

    if col_header_ids:
        graph.add_edge(VisualEdge(root_id, corner_id, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "16"}}))
    if row_header_ids:
        graph.add_edge(VisualEdge(corner_id, row_header_ids[0], type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis", "weight": "16"}}))

    return root_id
