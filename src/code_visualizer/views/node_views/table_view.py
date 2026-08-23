from __future__ import annotations

import re
from typing import Any

from ...renderers.html.labels import (
    html_bold_text,
    html_cell,
    html_font,
    html_row,
    html_table,
)
from ...renderers.html.tables import _format_nested_value
from ...renderers.shared.theme import (
    BG_FOCUS,
    BG_FOCUS_SOFT,
    BG_HEADER,
    BG_PANEL,
    BG_SURFACE,
    BORDER_DEFAULT,
    BORDER_FOCUS,
    TEXT_PRIMARY,
    blend_hex_colors,
    normalize_hex_color,
)
from ...shared.models import EdgeKind, NodeKind, VisualEdge, VisualNode
from ...utils.value_formatting import estimate_table_column_widths
from ...utils.value_formatting import format_container_stub as _format_container_stub
from ...utils.value_formatting import format_scalar_html as _format_scalar_html
from ...utils.value_formatting import stable_svg_id as _stable_svg_id
from ...utils.value_formatting import table_cell_text as _table_cell_text
from ...utils.value_shapes import _is_scalar_value
from ..context import ViewBuildContext
from ..graph_layout import init_graph_attrs, new_node_id, safe_dot_token


def _extract_table_focus_key(focus_path: str | None, logical_name: str) -> str | None:
    if not focus_path or not focus_path.startswith(logical_name):
        return None
    suffix = focus_path[len(logical_name) :]
    if not suffix:
        return None
    match = re.match(r"""\[(?:"([^"]+)"|'([^']+)')\]""", suffix)
    if match:
        return match.group(1) or match.group(2)
    if suffix.startswith("."):
        parts = suffix[1:].split(".", 1)
        return parts[0] if parts and parts[0] else None
    return None


def _table_column_widths(
    items: list[tuple[Any, Any]], item_limit: int
) -> tuple[int, int, int]:
    key_width, value_width = estimate_table_column_widths(items, item_limit)
    key_width = min(220, max(92, key_width))
    value_width = min(920, max(92, value_width))
    total_width = key_width + value_width
    return key_width, value_width, total_width


def _node_frame(inner_html: str, total_width: int) -> str:
    return html_table(
        html_row(
            html_cell(
                inner_html,
                width=total_width,
                FIXEDSIZE="TRUE",
                CELLPADDING="0",
            )
        ),
        BORDER="1",
        CELLBORDER="1",
        CELLSPACING="0",
        CELLPADDING="0",
    )


def _inject_table_width(opening_tag: str, width: int) -> str:
    if re.search(r"\b(?:WIDTH|width)=", opening_tag):
        return opening_tag
    return opening_tag[:-1] + f" WIDTH='{width}'>"


def _stretch_sequence_preview_html(stripped: str, value_width: int) -> str | None:
    sequence_wrapper_match = re.search(
        r"<table\b([^>]*)\bid='([^']*-wrapper)'([^>]*)>", stripped
    )
    if not sequence_wrapper_match:
        return None

    stretched = stripped
    wrapper_open = sequence_wrapper_match.group(0)
    stretched = stretched.replace(
        wrapper_open,
        _inject_table_width(wrapper_open, value_width),
        1,
    )

    value_table_match = re.search(
        r"<table\b([^>]*)\bid='([^']*-value-table)'([^>]*)>", stretched
    )
    if value_table_match:
        value_table_open = value_table_match.group(0)
        stretched = stretched.replace(
            value_table_open,
            _inject_table_width(value_table_open, value_width),
            1,
        )

    nested_item_cells = re.findall(
        r"<td align='center' bgcolor='#ffffff' cellpadding='4'><table",
        stretched,
    )
    scalar_item_cells = re.findall(
        r"<td align='center' bgcolor='#ffffff' cellpadding='4'>",
        stretched,
    )
    item_count = len(nested_item_cells) or len(scalar_item_cells)
    if item_count == 0:
        return stretched

    cell_width = max(34, value_width // item_count)
    if nested_item_cells:
        stretched = stretched.replace(
            "<td align='center' bgcolor='#ffffff' cellpadding='4'><table",
            (
                f"<td width='{cell_width}' align='center'"
                " bgcolor='#ffffff' cellpadding='4'><table"
            ),
        )
    else:
        stretched = stretched.replace(
            "<td align='center' bgcolor='#ffffff' cellpadding='4'>",
            (
                f"<td width='{cell_width}' align='center'"
                " bgcolor='#ffffff' cellpadding='4'>"
            ),
        )
    return stretched.replace(
        "<td align='center'><font color='#dc2626' point-size='12'>",
        (
            f"<td width='{cell_width}' align='center'>"
            "<font color='#dc2626' point-size='12'>"
        ),
    )


def _stretch_nested_dict_preview_html(
    stripped: str,
    value_width: int,
) -> str | None:
    header_match = re.search(
        r"^<table\b[^>]*><tr><td width='(\d+)'[^>]*><b>Key</b></td><td width='(\d+)'[^>]*><b>Value</b></td>",
        stripped,
    )
    if not header_match:
        return None

    open_match = re.match(r"^<table\b([^>]*)>", stripped)
    if not open_match:
        return None

    attrs = open_match.group(1) or ""
    stretched = stripped
    if not re.search(r"\b(?:WIDTH|width)=", attrs):
        stretched_open = f"<table{attrs} WIDTH='{value_width}'>"
        stretched = stretched_open + stripped[open_match.end() :]

    inner_match = re.search(r"<table\b([^>]*)\bid='[^']*-value-table'([^>]*)>", stretched)
    if inner_match:
        inner_open = inner_match.group(0)
        stretched = stretched.replace(
            inner_open,
            _inject_table_width(inner_open, value_width),
            1,
        )

    nested_key_width = int(header_match.group(1))
    nested_value_width = int(header_match.group(2))
    target_nested_value_width = max(
        nested_value_width,
        value_width - nested_key_width,
    )
    if target_nested_value_width == nested_value_width:
        return stretched

    row_pattern = re.compile(
        rf"(<tr><td width='{nested_key_width}'[^>]*>.*?</td><td width=')"
        rf"{nested_value_width}"
        rf"('[^>]*>)",
        flags=re.DOTALL,
    )
    return row_pattern.sub(
        rf"\g<1>{target_nested_value_width}\g<2>",
        stretched,
    )


def _stretch_nested_value_html(value_html: str, value_width: int) -> str:
    stripped = value_html.strip()
    if not stripped.startswith("<table"):
        return value_html

    sequence_stretched = _stretch_sequence_preview_html(stripped, value_width)
    if sequence_stretched is not None:
        return sequence_stretched

    dict_stretched = _stretch_nested_dict_preview_html(stripped, value_width)
    if dict_stretched is not None:
        return dict_stretched

    return value_html


def _two_column_row(
    key_html: str,
    value_html: str,
    *,
    key_width: int,
    value_width: int,
    key_fill: str,
    value_fill: str,
    value_port: str | None = None,
    value_align: str = "CENTER",
    value_cellpadding: str = "6",
) -> str:
    key_cell = html_cell(
        key_html,
        WIDTH=key_width,
        FIXEDSIZE="TRUE",
        ALIGN="CENTER",
        BGCOLOR=key_fill,
        CELLPADDING="6",
    )
    value_attrs: dict[str, object] = {
        "WIDTH": value_width,
        "FIXEDSIZE": "TRUE",
        "ALIGN": value_align,
        "BGCOLOR": value_fill,
        "CELLPADDING": value_cellpadding,
    }
    if value_port is not None:
        value_attrs["PORT"] = value_port
    value_cell = html_cell(value_html, value_attrs)
    return html_table(
        html_row(key_cell, value_cell),
        BORDER="0",
        CELLBORDER="1",
        CELLSPACING="0",
        CELLPADDING="0",
    )


def build_table_view_node_rows(
    runtime: ViewBuildContext, value: Any, name: str, depth: int
) -> str:
    logical_name = name.split(" [step ", 1)[0]
    if not isinstance(value, dict):
        raise TypeError("table_node view expects dict input")

    items = list(value.items())
    item_limit = runtime.item_limit
    limit = min(len(items), item_limit)
    depth_budget = max(0, depth)
    inner_depth = depth_budget - 1 if depth_budget > 0 else 0
    focused_key = _extract_table_focus_key(runtime.focus_path, logical_name)
    visible_items = items[:limit]
    key_width, value_width, total_width = _table_column_widths(
        visible_items, item_limit
    )

    graph = runtime.graph
    accent_color = normalize_hex_color(runtime.accent_color)
    header_fill = blend_hex_colors(accent_color, BG_HEADER, 0.22) if accent_color else BG_HEADER
    header_border = blend_hex_colors(accent_color, BORDER_DEFAULT, 0.62) if accent_color else BORDER_DEFAULT
    init_graph_attrs(
        graph,
        rankdir="TB",
        nodesep="0.01",
        ranksep="0.035",
        title=name,
        show_title=runtime.show_titles,
    )

    root_id = new_node_id(runtime, "table_exp")
    graph.add_node(
        VisualNode(
            root_id,
            NodeKind.OBJECT,
            "",
            {
                "kind": "table_root",
                "node_attrs": {
                    "shape": "point",
                    "style": "invis",
                    "width": "0.01",
                    "height": "0.01",
                },
            },
        )
    )
    node_width_inches = f"{max(0.01, total_width / 72):.2f}"

    header_id = safe_dot_token("table_header", logical_name)
    header_inner = _two_column_row(
        html_font(html_bold_text("Key"), color=TEXT_PRIMARY),
        html_font(html_bold_text("Value"), color=TEXT_PRIMARY),
        key_width=key_width,
        value_width=value_width,
        key_fill=header_fill,
        value_fill=header_fill,
    )
    header_label = _node_frame(header_inner, total_width)
    graph.add_node(
        VisualNode(
            header_id,
            NodeKind.OBJECT,
            header_label,
            {
                "html_label": True,
                "rank": "table_header",
                "node_attrs": {
                    "shape": "plain",
                    "color": header_border,
                    "penwidth": "1.0",
                    "width": node_width_inches,
                },
            },
        )
    )

    prev_node_id = header_id
    for idx in range(limit):
        key, val = items[idx]
        key_text = _table_cell_text(key)
        row_id = safe_dot_token("table_row", logical_name, key_text)
        value_port = f"{row_id}_value"
        if _is_scalar_value(val):
            value_html = _format_scalar_html(val)
            value_align = "CENTER"
            value_cellpadding = "6"
        else:
            value_html = _format_nested_value(
                val, inner_depth, item_limit, None, f"{name}.{key}"
            )
            if not value_html:
                value_html = _format_container_stub(val)
            value_html = _stretch_nested_value_html(value_html, value_width)
            value_html = html_table(
                html_row(
                    html_cell(
                        value_html,
                        width=value_width,
                        align="left",
                        valign="top",
                        cellpadding="0",
                    )
                ),
                border="0",
                cellborder="0",
                cellspacing="0",
                cellpadding="0",
            )
            value_align = "LEFT"
            value_cellpadding = "0"

        is_focused = focused_key is not None and str(focused_key) == str(key_text)
        if accent_color is not None:
            focused_key_fill = blend_hex_colors(accent_color, BG_PANEL, 0.22)
            focused_value_fill = blend_hex_colors(accent_color, BG_SURFACE, 0.12)
            resting_key_fill = blend_hex_colors(accent_color, BG_PANEL, 0.10)
            resting_value_fill = BG_SURFACE
            focused_border = accent_color
            resting_border = blend_hex_colors(accent_color, BORDER_DEFAULT, 0.54)
        else:
            focused_key_fill = BG_FOCUS
            focused_value_fill = BG_FOCUS_SOFT
            resting_key_fill = BG_PANEL
            resting_value_fill = BG_SURFACE
            focused_border = BORDER_FOCUS
            resting_border = BORDER_DEFAULT
        if is_focused:
            key_fill, value_fill, border_color, penwidth = (
                focused_key_fill,
                focused_value_fill,
                focused_border,
                "1.8",
            )
        else:
            key_fill, value_fill, border_color, penwidth = (
                resting_key_fill,
                resting_value_fill,
                resting_border,
                "1.0",
            )

        row_inner = _two_column_row(
            html_font(
                html_bold_text(key_text), {"color": TEXT_PRIMARY, "point-size": 11}
            ),
            value_html,
            key_width=key_width,
            value_width=value_width,
            key_fill=key_fill,
            value_fill=value_fill,
            value_port=value_port,
            value_align=value_align,
            value_cellpadding=value_cellpadding,
        )
        row_label = _node_frame(row_inner, total_width)
        graph.add_node(
            VisualNode(
                row_id,
                NodeKind.OBJECT,
                row_label,
                {
                    "kind": "table_row",
                    "html_label": True,
                    "rank": f"table_row_{idx}",
                    "node_attrs": {
                        "shape": "plain",
                        "color": border_color,
                        "penwidth": penwidth,
                        "id": _stable_svg_id(logical_name, "table", "row", key_text),
                        "width": node_width_inches,
                    },
                },
            )
        )
        graph.add_edge(
            VisualEdge(
                prev_node_id,
                row_id,
                type=EdgeKind.LAYOUT,
                meta={"edge_attrs": {"style": "invis"}},
            )
        )
        prev_node_id = row_id

    graph.add_edge(
        VisualEdge(
            root_id,
            header_id,
            type=EdgeKind.LAYOUT,
            meta={"edge_attrs": {"style": "invis"}},
        )
    )
    return root_id
