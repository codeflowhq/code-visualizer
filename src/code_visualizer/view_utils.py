# view_utils.py
from __future__ import annotations

from collections.abc import Callable, Mapping
from html import escape as html_escape
from typing import Any

from graphviz import Digraph

from .utils.image_sources import (
    VisualizationImageError as _VisualizationImageError,
)
from .utils.image_sources import (
    _detect_image_source as _detect_image_source_impl,
)
from .utils.image_sources import (
    _image_html as _image_html_impl,
)
from .utils.image_sources import (
    _looks_like_image_candidate as _looks_like_image_candidate_impl,
)
from .utils.image_sources import (
    _render_dot_to_image as _render_dot_to_image_impl,
)
from .utils.structure_detection import (
    _collect_linked_list_labels as _collect_linked_list_labels_impl,
)
from .utils.structure_detection import (
    _hash_bucket_entries as _hash_bucket_entries_impl,
)
from .utils.structure_detection import (
    _looks_like_graph_mapping as _looks_like_graph_mapping_impl,
)
from .utils.structure_detection import (
    _looks_like_hash_table as _looks_like_hash_table_impl,
)
from .utils.structure_detection import (
    _tree_children as _tree_children_impl,
)
from .utils.structure_detection import (
    _try_networkx_edges_nodes as _try_networkx_edges_nodes_impl,
)
from .utils.type_patterns import _is_number
from .utils.type_patterns import (
    _match_type_pattern_override as _match_type_pattern_override_impl,
)
from .utils.value_formatting import (
    format_container_stub as _format_container_stub,
)
from .utils.value_formatting import (
    format_scalar_html as _format_scalar_html,
)
from .utils.value_formatting import (
    stable_svg_id as _stable_svg_id,
)
from .utils.value_formatting import (
    table_cell_text as _table_cell_text,
)
from .view_types import ViewKind

NestedRenderer = Callable[[Any, str, int], str | None]

VisualizationImageError = _VisualizationImageError
_detect_image_source = _detect_image_source_impl
_image_html = _image_html_impl
_looks_like_image_candidate = _looks_like_image_candidate_impl
_render_dot_to_image = _render_dot_to_image_impl
_collect_linked_list_labels = _collect_linked_list_labels_impl
_hash_bucket_entries = _hash_bucket_entries_impl
_looks_like_graph_mapping = _looks_like_graph_mapping_impl
_looks_like_hash_table = _looks_like_hash_table_impl
_tree_children = _tree_children_impl
_try_networkx_edges_nodes = _try_networkx_edges_nodes_impl
_match_type_pattern_override = _match_type_pattern_override_impl

# Backward-compatible private aliases used across the package.
_collect_linked_list_labels = _collect_linked_list_labels_impl
_hash_bucket_entries = _hash_bucket_entries_impl
_looks_like_graph_mapping = _looks_like_graph_mapping_impl
_looks_like_hash_table = _looks_like_hash_table_impl
_tree_children = _tree_children_impl
_try_networkx_edges_nodes = _try_networkx_edges_nodes_impl

def _is_list_numbers(x: Any) -> bool:
    return isinstance(x, list) and all(_is_number(v) for v in x)

def _is_dict(x: Any) -> bool:
    return isinstance(x, dict)

def _is_scalar_value(x: Any) -> bool:
    return isinstance(x, (str, int, float, bool)) or x is None

def _is_matrix_value(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) > 0
        and all(isinstance(row, (list, tuple)) for row in value)
    )

def _auto_nested_depth(value: Any, cap: int) -> int:
    capped = max(0, cap)

    def helper(obj: Any, depth: int) -> int:
        if depth >= capped:
            return capped
        if isinstance(obj, dict):
            if not obj:
                return depth
            best = depth
            for v in obj.values():
                best = max(best, helper(v, depth + 1))
            return best
        if isinstance(obj, (list, tuple, set, frozenset)):
            if not obj:
                return depth
            best = depth
            for item in obj:
                best = max(best, helper(item, depth + 1))
            return best
        return depth

    return helper(value, 0)

def _graphviz_array_block(value_cells: list[str], index_cells: list[str], *, slot_name: str = "array") -> str:
    if not value_cells:
        value_row = f'<td id="{_stable_svg_id(slot_name, "value", "empty")}" align="center">&nbsp;</td>'
    else:
        value_row = "".join(value_cells)
    if not index_cells:
        index_row = f'<td id="{_stable_svg_id(slot_name, "index", "empty")}" align="center">&nbsp;</td>'
    else:
        index_row = "".join(index_cells)
    return (
        f'<table id="{_stable_svg_id(slot_name, "wrapper")}" border="0" cellborder="0" cellspacing="0">'
        f'<tr><td id="{_stable_svg_id(slot_name, "value-table-container")}">'
        f'<table id="{_stable_svg_id(slot_name, "value-table")}" border="1" cellborder="1" cellspacing="0">'
        f'<tr id="{_stable_svg_id(slot_name, "value-row")}">{value_row}</tr>'
        '</table>'
        '</td></tr>'
        f'<tr><td id="{_stable_svg_id(slot_name, "index-table-container")}">'
        f'<table id="{_stable_svg_id(slot_name, "index-table")}" border="0" cellborder="0" cellspacing="4">'
        f'<tr id="{_stable_svg_id(slot_name, "index-row")}">{index_row}</tr>'
        '</table>'
        '</td></tr>'
        '</table>'
    )

def _format_nested_value(
    value: Any,
    depth_remaining: int,
    max_items: int,
    nested_renderer: NestedRenderer | None = None,
    slot_name: str = "value",
) -> str:
    if nested_renderer is not None:
        nested_html = nested_renderer(value, slot_name, depth_remaining)
        if nested_html is not None:
            return nested_html

    img_src = _detect_image_source(value)
    if img_src is not None:
        return _image_html(img_src)

    inline_html = _format_inline_collection(
        value,
        depth_remaining,
        max_items,
        nested_renderer,
        slot_name,
    )
    if inline_html is not None:
        return inline_html

    if not _is_scalar_value(value):
        return _format_container_stub(value)

    return _format_scalar_html(value)

def _format_inline_collection(  # noqa: C901
    value: Any,
    depth_remaining: int,
    max_items: int,
    nested_renderer: NestedRenderer | None,
    slot_name: str,
) -> str | None:
    if depth_remaining <= 0:
        return None

    next_depth = depth_remaining - 1

    if _is_matrix_value(value):
        rows = [list(r) for r in value]  # type: ignore[arg-type]
        return _format_matrix_html(
            rows,
            next_depth,
            max_items,
            nested_renderer=nested_renderer,
            slot_name=slot_name,
            row_limit=max_items,
            col_limit=max_items,
        )

    seq: list[Any] | None = None
    if isinstance(value, (list, tuple)):
        seq = list(value)
    elif isinstance(value, (set, frozenset)):
        seq = sorted(value, key=lambda x: str(x))

    if seq is not None:
        n = len(seq)
        limit = min(n, max_items)
        value_cells: list[str] = []
        index_cells: list[str] = []
        for i in range(limit):
            cell_html = _format_nested_value(
                seq[i],
                next_depth,
                max_items,
                nested_renderer,
                f"{slot_name}[{i}]",
            )
            value_cells.append(f'<td align="center" bgcolor="#ffffff" cellpadding="4">{cell_html}</td>')
            index_cells.append(
                f'<td align="center"><font color="#dc2626" point-size="12">{html_escape(str(i))}</font></td>'
            )
        if n > max_items:
            value_cells.append('<td align="center" bgcolor="#ffffff">…</td>')
            index_cells.append('<td align="center"></td>')
        return _graphviz_array_block(value_cells, index_cells, slot_name=slot_name)

    if isinstance(value, dict):
        items = list(value.items())
        n = len(items)
        limit = min(n, max_items)
        rows: list[str] = []
        rows.append('<tr><td bgcolor="#e5e7eb"><b>Key</b></td><td bgcolor="#e5e7eb"><b>Value</b></td></tr>')
        if n == 0:
            rows.append('<tr><td colspan="2">∅</td></tr>')
        else:
            for idx in range(limit):
                k, v = items[idx]
                val_html = _format_nested_value(
                    v,
                    next_depth,
                    max_items,
                    nested_renderer,
                    f"{slot_name}.{_table_cell_text(k)}",
                )
                rows.append(f"<tr><td>{_table_cell_text(k)}</td><td>{val_html}</td></tr>")
            if n > max_items:
                rows.append('<tr><td colspan="2">… (+more)</td></tr>')
        return f'<table border="1" cellborder="1" cellspacing="0">{"".join(rows)}</table>'

    return None

def _bar_chart_html(values: list[float], labels: list[str], max_height_px: int = 160) -> str:
    if not values:
        return "<table border='1' cellborder='1' cellspacing='0'><tr><td>∅</td></tr></table>"

    max_abs = max(abs(v) for v in values)
    if max_abs == 0:
        max_abs = 1.0

    table: list[str] = ["<table border='0' cellborder='0' cellspacing='10'><tr>"]
    for label, val in zip(labels, values, strict=False):
        norm = abs(val) / max_abs
        height = max(24, int(max_height_px * norm))
        gap = max(0, max_height_px - height)
        color = "#bae6fd" if val >= 0 else "#fecaca"
        value_text = int(val) if float(val).is_integer() else round(val, 2)
        inner = (
            "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
            f"<tr><td height='{gap}'></td></tr>"
            f"<tr><td bgcolor='{color}' width='34' height='{height}'></td></tr>"
            f"<tr><td align='center'><font point-size='11' color='#0f172a'>{value_text}</font></td></tr>"
            f"<tr><td align='center'><font point-size='9' color='#dc2626'>{html_escape(label)}</font></td></tr>"
            "</table>"
        )
        table.append(f"<td valign='bottom'>{inner}</td>")
    table.append("</tr></table>")
    return "".join(table)

def _format_value_label(
    value: Any,
    nested_depth: int,
    max_items: int,
    nested_renderer: NestedRenderer | None = None,
    slot_name: str = "value",
) -> tuple[str, bool]:
    image_src = _detect_image_source(value)
    if image_src is not None:
        return _image_html(image_src), True

    depth = max(0, nested_depth)
    html_depth: int | None
    if depth > 0:
        html_depth = depth
    elif _is_matrix_value(value):
        html_depth = 1
    elif isinstance(value, (list, tuple, set, frozenset, dict)):
        html_depth = 1
    else:
        html_depth = None

    if html_depth is not None:
        html = _format_nested_value(value, html_depth, max_items, nested_renderer, slot_name)
        return html, True
    return str(value), False

def _format_matrix_html(  # noqa: C901
    rows: list[list[Any]],
    depth_remaining: int,
    max_items: int,
    *,
    include_headers: bool = False,
    row_limit: int | None = None,
    col_limit: int | None = None,
    nested_renderer: NestedRenderer | None = None,
    slot_name: str = "matrix",
) -> str:
    depth_remaining = max(0, depth_remaining)
    total_rows = len(rows)
    width = max((len(r) for r in rows), default=0)
    limit_rows = min(total_rows, row_limit if row_limit is not None else total_rows)
    limit_rows = min(limit_rows, max_items)
    limit_cols = min(width, col_limit if col_limit is not None else width)
    limit_cols = min(limit_cols, max_items)
    table: list[str] = []
    table.append(f'<table id="{_stable_svg_id(slot_name, "wrapper")}" border="1" cellborder="1" cellspacing="0">')

    def cell(val: Any) -> str:
        return _format_nested_value(val, depth_remaining, max_items, nested_renderer, slot_name)

    if include_headers:
        header_cells = [f'<td id="{_stable_svg_id(slot_name, "header", "corner")}" bgcolor="#f3f4f6"></td>']
        for c in range(limit_cols):
            header_cells.append(f'<td id="{_stable_svg_id(slot_name, "header", c)}" bgcolor="#f3f4f6"><font color="#dc2626">{c}</font></td>')
        if width > limit_cols:
            header_cells.append(f'<td id="{_stable_svg_id(slot_name, "header", "ellipsis")}" bgcolor="#f3f4f6">…</td>')
        table.append(f"<tr>{''.join(header_cells)}</tr>")

    for r_idx in range(limit_rows):
        row = rows[r_idx]
        cells: list[str] = []
        if include_headers:
            cells.append(f'<td id="{_stable_svg_id(slot_name, "row", r_idx, "header")}" bgcolor="#fef3c7"><font color="#b45309">{r_idx}</font></td>')
        for c_idx in range(limit_cols):
            val = row[c_idx] if c_idx < len(row) else ""
            cells.append(
                f'<td id="{_stable_svg_id(slot_name, "row", r_idx, "col", c_idx)}">{cell(val if c_idx < len(row) else "")}</td>'
            )
        if len(row) > limit_cols:
            cells.append(f'<td id="{_stable_svg_id(slot_name, "row", r_idx, "ellipsis")}">…</td>')
        table.append(f"<tr>{''.join(cells)}</tr>")

    if total_rows > limit_rows:
        colspan = limit_cols + (1 if include_headers else 0)
        if width > limit_cols:
            colspan += 1
        table.append(f'<tr><td id="{_stable_svg_id(slot_name, "rows", "ellipsis")}" colspan="{max(1, colspan)}">… (+more rows)</td></tr>')

    table.append("</table>")
    return "".join(table)

def _digraph_edge(dot: Digraph, tail: str, head: str, **attrs: str) -> None:
    if ":" not in tail and ":" not in head:
        dot.edge(tail, head, **attrs)
        return

    attr_text = ""
    if attrs:
        attr_parts = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        attr_text = f" [{attr_parts}]"
    dot.body.append(f"  {tail} -> {head}{attr_text};")

def _normalize_view_name(name: str) -> str:
    return "".join(ch for ch in name.strip() if not ch.isspace())

def _match_named_override(name: str, mapping: Mapping[str, ViewKind] | None) -> ViewKind | None:
    if not mapping:
        return None
    normalized = _normalize_view_name(name)
    for raw_key, view in mapping.items():
        if not isinstance(raw_key, str):
            continue
        if _normalize_view_name(raw_key) == normalized:
            return view
    return None

