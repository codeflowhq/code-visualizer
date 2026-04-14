from __future__ import annotations

from html import escape as html_escape
from typing import Any

from ..models import EdgeKind, NodeKind, VisualEdge, VisualNode
from ..utils.structure_detection import (
    _collect_linked_list_labels,
    _hash_bucket_entries,
)
from ..view_types import ViewKind
from ..view_utils import _bar_chart_html, _format_nested_value, _graphviz_array_block
from .heap import _heap_tree_payload


def _hash_entry_label(value: Any) -> str:
    if value is None:
        return "∅"
    if isinstance(value, float):
        display = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        display = str(value).strip()
    if not display:
        display = type(value).__name__
    if len(display) > 6:
        display = display[:5] + "…"
    return display


def build_array_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from .common import add_html_node, new_node_id, wrap_label
    from .nested import make_nested_renderer

    if isinstance(value, (set, frozenset)):
        array = sorted(value, key=lambda x: str(x))
    elif isinstance(value, (list, tuple)):
        array = list(value)
    else:
        raise TypeError("array_cells view expects list-like input")

    node_id = new_node_id(runtime, "arr")
    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0

    value_cells: list[str] = []
    index_cells: list[str] = []
    limit = min(len(array), item_limit)

    for i in range(limit):
        port = f"{node_id}_item_{i}"
        nested_renderer = make_nested_renderer(runtime, node_id, port, f"{name}[{i}]")
        cell_html = _format_nested_value(array[i], cell_depth, item_limit, nested_renderer, f"{name}[{i}]")
        value_cells.append(f'<td port="{port}" align="center" bgcolor="#ffffff" cellpadding="4">{cell_html}</td>')
        index_cells.append(f"<td align='center'><font color='#dc2626' point-size='12'>{html_escape(str(i))}</font></td>")

    if len(array) > item_limit:
        value_cells.append('<td align="center" bgcolor="#ffffff">…</td>')
        index_cells.append("<td align='center'></td>")

    table_html = _graphviz_array_block(value_cells, index_cells)
    add_html_node(runtime, node_id, wrap_label(name, table_html))
    return node_id


def build_table_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from ..view_utils import _table_cell_text
    from .common import add_html_node, new_node_id, wrap_label
    from .nested import make_nested_renderer

    if not isinstance(value, dict):
        raise TypeError("table view expects dict input")

    item_limit = runtime["item_limit"]
    items = list(value.items())
    limit = min(len(items), item_limit)
    node_id = new_node_id(runtime, ViewKind.TABLE)
    depth_budget = max(0, depth)
    inner_depth = depth_budget - 1 if depth_budget > 0 else 0

    rows = ["<tr><td bgcolor='#e5e7eb'><b>Key</b></td><td bgcolor='#e5e7eb'><b>Value</b></td></tr>"]
    for idx in range(limit):
        key, val = items[idx]
        port = f"{node_id}_val_{idx}"
        nested_renderer = make_nested_renderer(runtime, node_id, port, f"{name}.{key}")
        val_html = _format_nested_value(val, inner_depth, item_limit, nested_renderer, f"{name}.{key}")
        rows.append(f"<tr><td>{_table_cell_text(key)}</td><td port='{port}'>{val_html}</td></tr>")

    if not items:
        rows.append("<tr><td colspan='2'>∅</td></tr>")
    elif len(items) > item_limit:
        rows.append("<tr><td colspan='2'>… (+more)</td></tr>")

    table_html = f"<table border='1' cellborder='1' cellspacing='0'>{''.join(rows)}</table>"
    add_html_node(runtime, node_id, wrap_label(name, table_html))
    return node_id


def build_matrix_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:  # noqa: C901
    from .common import add_html_node, new_node_id, wrap_label
    from .nested import make_nested_renderer

    if not isinstance(value, (list, tuple)):
        raise TypeError("matrix view expects a list of lists/tuples")
    rows: list[list[Any]] = []
    for row in value:
        if not isinstance(row, (list, tuple)):
            raise TypeError("matrix view expects uniform sublists")
        rows.append(list(row))

    node_id = new_node_id(runtime, ViewKind.MATRIX)
    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0
    row_count = len(rows)
    row_limit = min(row_count, min(item_limit, 25))
    width = max((len(r) for r in rows), default=0)
    col_limit = min(width, min(item_limit, 25))

    body: list[str] = ["<table border='1' cellborder='1' cellspacing='0'>"]
    if row_count == 0:
        body.append("<tr><td>∅</td></tr>")
    else:
        header_cells = ["<td bgcolor='#f3f4f6'></td>"]
        for c in range(col_limit):
            header_cells.append(f"<td bgcolor='#f3f4f6'><font color='#dc2626'>{c}</font></td>")
        if width > col_limit:
            header_cells.append("<td bgcolor='#f3f4f6'>…</td>")
        body.append(f"<tr>{''.join(header_cells)}</tr>")

        for r_idx in range(row_limit):
            row = rows[r_idx]
            cells: list[str] = [f"<td bgcolor='#fef3c7'><font color='#b45309'>{r_idx}</font></td>"]
            for c_idx in range(col_limit):
                val = row[c_idx] if c_idx < len(row) else ""
                port = f"{node_id}_r{r_idx}_c{c_idx}"
                nested_renderer = make_nested_renderer(runtime, node_id, port, f"{name}[{r_idx}][{c_idx}]")
                cell_html = _format_nested_value(val, cell_depth, item_limit, nested_renderer, f"{name}[{r_idx}][{c_idx}]")
                cells.append(f"<td port='{port}'>{cell_html}</td>")
            if len(row) > col_limit:
                cells.append("<td>…</td>")
            body.append(f"<tr>{''.join(cells)}</tr>")

        if row_count > row_limit:
            colspan = col_limit + 1
            if width > col_limit:
                colspan += 1
            body.append(f"<tr><td colspan='{colspan}'>… (+more rows)</td></tr>")

    body.append("</table>")
    add_html_node(runtime, node_id, wrap_label(name, "".join(body)))
    return node_id


def _make_hash_entry_node(runtime: dict[str, Any], value: Any, slot_name: str, depth_remaining: int) -> str:
    from ..graph_view_builder import _build_view
    from .common import add_edge, new_node_id
    from .nested import select_nested_view

    node_id = new_node_id(runtime, "hash_val")
    label = _hash_entry_label(value)
    meta = {
        "node_attrs": {
            "shape": "circle",
            "width": "0.55",
            "height": "0.55",
            "fixedsize": "true",
            "fontname": "Helvetica",
            "fontsize": "11",
            "style": "filled",
            "fillcolor": "#ffffff",
            "color": "#1f2933",
        }
    }
    runtime["graph"].add_node(VisualNode(node_id, NodeKind.OBJECT, label, meta))
    if depth_remaining >= 0:
        coerce = runtime["coerce"]
        coerced = coerce(value)
        next_view = select_nested_view(runtime, slot_name, value, coerced, depth_remaining)
        if next_view is not None:
            child_id = _build_view(runtime, coerced, slot_name, next_view, max(0, depth_remaining))
            add_edge(runtime, node_id, child_id)
    return node_id


def _make_hash_bucket_node(runtime: dict[str, Any], idx: int, rank_group: str) -> str:
    from .common import new_node_id

    bucket_id = new_node_id(runtime, "hash_bucket")
    label = (
        "<table border='0' cellborder='0' cellspacing='0'>"
        "<tr><td><table border='1' cellborder='0' cellspacing='0' cellpadding='6'>"
        "<tr><td><font point-size='12'><b>H</b></font></td></tr></table></td></tr>"
        f"<tr><td align='center'><font color='#dc2626'>{idx}</font></td></tr></table>"
    )
    meta = {"html_label": True, "node_attrs": {"shape": "plain"}, "rank": rank_group}
    runtime["graph"].add_node(VisualNode(bucket_id, NodeKind.OBJECT, label, meta))
    return bucket_id


def _populate_hash_bucket(runtime: dict[str, Any], bucket_id: str, bucket_value: Any, idx: int, name: str, depth_remaining: int) -> None:
    from .common import add_html_node, new_node_id

    item_limit = runtime["item_limit"]
    entries, clipped = _hash_bucket_entries(bucket_value, min(item_limit, 8))
    prev = bucket_id
    slot_prefix = f"{name}[{idx}]"
    for j, entry in enumerate(entries):
        entry_id = _make_hash_entry_node(runtime, entry, f"{slot_prefix}[{j}]", depth_remaining)
        runtime["graph"].add_edge(VisualEdge(prev, entry_id, type=EdgeKind.CONTAINS, meta={"edge_attrs": {"color": "#1f2933"}}))
        prev = entry_id
    if clipped:
        ellipsis_id = new_node_id(runtime, "hash_clip")
        add_html_node(runtime, ellipsis_id, "<font color='#0f172a'>…</font>")
        runtime["graph"].add_edge(
            VisualEdge(prev, ellipsis_id, type=EdgeKind.CONTAINS, meta={"edge_attrs": {"color": "#1f2933", "style": "dashed"}})
        )


def build_hash_table_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from .common import add_edge, add_html_node, new_node_id, wrap_label

    if not isinstance(value, list):
        raise TypeError("hash_table view expects list input")

    graph = runtime["graph"]
    item_limit = runtime["item_limit"]
    root_id = new_node_id(runtime, "hash_root")
    header = "<font color='#0f172a' point-size='11'><b>hash_table</b></font>"
    add_html_node(runtime, root_id, wrap_label(None, header, show_title=False))

    depth_budget = max(0, depth)
    chain_depth = depth_budget - 1 if depth_budget > 0 else 0
    limit = min(len(value), item_limit)
    bucket_ids: list[str] = []
    bucket_rank_group = f"{root_id}_row"

    for idx in range(limit):
        bucket_id = _make_hash_bucket_node(runtime, idx, bucket_rank_group)
        bucket_ids.append(bucket_id)
        graph.add_edge(VisualEdge(root_id, bucket_id, type=EdgeKind.CONTAINS, meta={"edge_attrs": {"style": "invis"}}))
        _populate_hash_bucket(runtime, bucket_id, value[idx], idx, name, chain_depth)

    if len(bucket_ids) > 1:
        for left, right in zip(bucket_ids, bucket_ids[1:], strict=False):
            graph.add_edge(VisualEdge(left, right, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}}))

    if len(value) > limit:
        more_id = new_node_id(runtime, "hash_more")
        add_html_node(runtime, more_id, "<font color='#475569'>… (+more buckets)</font>")
        add_edge(runtime, root_id, more_id)

    return root_id


def build_bar_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from .common import add_html_node, new_node_id, wrap_label

    if not isinstance(value, (list, tuple)):
        raise TypeError("bar view expects list-like numeric input")
    seq = list(value)
    item_limit = runtime["item_limit"]
    limit = min(len(seq), item_limit)

    numeric: list[float] = []
    labels: list[str] = []
    for idx in range(limit):
        item = seq[idx]
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise TypeError("bar view expects list[number]")
        numeric.append(float(item))
        labels.append(str(idx))

    if not numeric:
        chart_html = "<table border='1' cellborder='1' cellspacing='0'><tr><td>∅</td></tr></table>"
    else:
        chart_html = _bar_chart_html(numeric, labels)
        if len(seq) > limit:
            chart_html += "<div><font color='#475569'>… (+more)</font></div>"

    node_id = new_node_id(runtime, ViewKind.BAR)
    add_html_node(runtime, node_id, wrap_label(name, chart_html))
    return node_id


def build_linked_list_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from .common import add_html_node, new_node_id, wrap_label
    from .nested import make_nested_renderer

    seq = _collect_linked_list_labels(value, runtime["item_limit"])
    if seq is None:
        raise TypeError("linked_list view expects objects with .next")
    values, truncated = seq

    node_id = new_node_id(runtime, "list")
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0
    item_limit = runtime["item_limit"]

    if not values:
        html = "<table border='1' cellborder='1' cellspacing='0'><tr><td align='center'>∅</td></tr></table>"
    else:
        cells: list[str] = []
        for idx, val in enumerate(values):
            port = f"{node_id}_node_{idx}"
            nested_renderer = make_nested_renderer(runtime, node_id, port, f"{name}[{idx}]")
            cell_html = _format_nested_value(val, cell_depth, item_limit, nested_renderer, f"{name}[{idx}]")
            value_block = f"<table border='1' cellborder='1' cellspacing='0'><tr><td port='{port}' bgcolor='#ffffff' cellpadding='6'>{cell_html}</td></tr></table>"
            cells.append(f"<td border='0' cellborder='0'>{value_block}</td>")
            cells.append("<td border='0' cellborder='0' sides='' width='24' align='center'><font color='#94a3b8'>&rarr;</font></td>")
        tail_inner = "<font color='#9ca3af'>∅</font>"
        if truncated:
            tail_inner = "…"
        tail = f"<table border='1' cellborder='1' cellspacing='0'><tr><td align='center'>{tail_inner}</td></tr></table>"
        cells.append(f"<td border='0' cellborder='0'>{tail}</td>")
        html = f"<table border='0' cellborder='0' cellspacing='2'><tr>{''.join(cells)}</tr></table>"

    add_html_node(runtime, node_id, wrap_label(name, html))
    return node_id


def build_heap_dual_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    from .common import add_edge, add_html_node, new_node_id, wrap_label
    from .tree import build_tree_view

    if not isinstance(value, list):
        raise TypeError("heap_dual view expects list input")

    container_id = new_node_id(runtime, "heap")
    container_label = (
        "<table border='0' cellborder='0' cellspacing='0'>"
        f"<tr><td align='center'><font point-size='16'><b>{html_escape(name)}</b></font></td></tr>"
        "<tr><td align='center'><font color='#64748b' point-size='11'>heap_dual</font></td></tr></table>"
    )
    add_html_node(runtime, container_id, container_label)

    array_id = build_array_view(runtime, value, f"{name}[array]", depth)
    add_edge(runtime, container_id, array_id)

    tree_payload = _heap_tree_payload(value, runtime["item_limit"])
    if tree_payload is not None:
        tree_id = build_tree_view(runtime, tree_payload, f"{name}[tree]", depth)
        add_edge(runtime, container_id, tree_id)
    else:
        empty_id = new_node_id(runtime, "heap_empty")
        empty_html = "<table border='1' cellborder='1' cellspacing='0'><tr><td align='center'>∅</td></tr></table>"
        add_html_node(runtime, empty_id, wrap_label(f"{name}[tree]", empty_html))
        add_edge(runtime, container_id, empty_id)

    return container_id
