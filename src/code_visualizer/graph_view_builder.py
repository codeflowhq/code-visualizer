"""Graphviz view builder shared by nested visualizations."""

from __future__ import annotations

from html import escape as html_escape
from itertools import count
from typing import Any, Callable, Iterator, Mapping

from .models import EdgeKind, NodeKind, VisualEdge, VisualGraph, VisualNode
from .renderers import build_tree, render_graphviz_node_link
from .view_types import ViewKind
from .view_utils import (
    _collect_linked_list_labels,
    _bar_chart_html,
    _detect_image_source,
    _format_nested_value,
    _format_value_label,
    _graphviz_array_block,
    _hash_bucket_entries,
    _image_html,
    _is_matrix_value,
    _looks_like_graph_mapping,
    _looks_like_hash_table,
    _render_dot_to_image,
    _table_cell_text,
    _tree_children,
    _try_networkx_edges_nodes,
)


ViewResolver = Callable[[str, Any, Any], tuple[ViewKind, bool]]
BuilderRuntime = dict[str, Any]

STRUCTURED_VIEW_KINDS: set[ViewKind] = {
    ViewKind.ARRAY_CELLS,
    ViewKind.TABLE,
    ViewKind.MATRIX,
    ViewKind.HASH_TABLE,
    ViewKind.LINKED_LIST,
    ViewKind.TREE,
    ViewKind.GRAPH,
    ViewKind.HEAP_DUAL,
    ViewKind.BAR,
    ViewKind.IMAGE,
}
RECURSIVE_VIEW_KINDS: set[ViewKind] = {
    ViewKind.TREE,
    ViewKind.LINKED_LIST,
    ViewKind.GRAPH,
    ViewKind.HASH_TABLE,
    ViewKind.HEAP_DUAL,
}


def build_graph_view(
    value: Any,
    name: str,
    view: ViewKind,
    depth: int,
    *,
    item_limit: int,
    value_coercer: Callable[[Any], Any] | None = None,
    view_resolver: ViewResolver | None = None,
) -> tuple[str, VisualGraph]:
    runtime = _create_runtime(item_limit, value_coercer, view_resolver)
    coerced_value = runtime["coerce"](value)
    root_id = _build_view(runtime, coerced_value, name, view, depth)
    return root_id, runtime["graph"]


def _create_runtime(
    item_limit: int,
    value_coercer: Callable[[Any], Any] | None,
    view_resolver: ViewResolver | None,
) -> BuilderRuntime:
    return {
        "graph": VisualGraph(),
        "item_limit": item_limit,
        "coerce": value_coercer or (lambda x: x),
        "resolver": view_resolver,
        "counter": count(1),
    }


def _build_view(runtime: BuilderRuntime, value: Any, name: str, view: ViewKind, depth: int) -> str:
    builder = _VIEW_BUILDERS.get(view)
    if builder is None:
        raise ValueError(f"Unsupported nested view: {view}")
    return builder(runtime, value, name, depth)


def _new_node_id(runtime: BuilderRuntime, prefix: str) -> str:
    counter: Iterator[int] = runtime["counter"]
    return f"{prefix}_{next(counter)}"


def _wrap_label(title: str | None, inner_html: str, *, show_title: bool = True) -> str:
    rows: list[str] = []
    if show_title and title:
        safe_title = html_escape(title)
        rows.append(
            "<tr><td align='center'><font point-size='16'><b>" + safe_title + "</b></font></td></tr>"
        )
    rows.append(f"<tr><td>{inner_html}</td></tr>")
    return "<table border='0' cellborder='0' cellspacing='2'>" + "".join(rows) + "</table>"


def _add_html_node(runtime: BuilderRuntime, node_id: str, label_html: str, meta: Mapping[str, Any] | None = None) -> None:
    merged_meta = {"html_label": True, "node_attrs": {"shape": "plain"}}
    if meta:
        merged_meta.update(meta)
    runtime["graph"].add_node(VisualNode(node_id, NodeKind.OBJECT, label_html, dict(merged_meta)))


def _add_edge(
    runtime: BuilderRuntime,
    src: str,
    dst: str,
    *,
    tailport: str | None = None,
    edge_meta: Mapping[str, Any] | None = None,
) -> None:
    meta: dict[str, Any] = {}
    if tailport:
        meta["tailport"] = tailport
    if edge_meta:
        meta["edge_attrs"] = dict(edge_meta)
    runtime["graph"].add_edge(VisualEdge(src, dst, type=EdgeKind.CONTAINS, meta=meta))


def _select_nested_view(
    runtime: BuilderRuntime,
    slot_name: str,
    original_value: Any,
    coerced_value: Any,
    depth_remaining: int,
) -> ViewKind | None:
    if depth_remaining <= 0:
        return None

    resolver: ViewResolver | None = runtime["resolver"]
    if resolver is not None:
        resolved_view, configured = resolver(slot_name, original_value, coerced_value)
        if configured and resolved_view in STRUCTURED_VIEW_KINDS:
            return resolved_view
        if resolved_view in RECURSIVE_VIEW_KINDS:
            return resolved_view

    legacy_view = _legacy_nested_view(runtime, coerced_value)
    if legacy_view in RECURSIVE_VIEW_KINDS:
        return legacy_view
    return None


def _legacy_nested_view(runtime: BuilderRuntime, value: Any) -> ViewKind | None:
    if value is None:
        return None
    if _tree_children(value) is not None:
        return ViewKind.TREE
    if _collect_linked_list_labels(value, min(8, runtime["item_limit"])) is not None:
        return ViewKind.LINKED_LIST
    if isinstance(value, list) and _looks_like_hash_table(value):
        return ViewKind.HASH_TABLE
    if _try_networkx_edges_nodes(value) is not None or _looks_like_graph_mapping(value):
        return ViewKind.GRAPH
    if _is_matrix_value(value):
        return ViewKind.MATRIX
    if isinstance(value, dict):
        return ViewKind.TABLE
    if isinstance(value, (list, tuple, set, frozenset)):
        return ViewKind.ARRAY_CELLS
    return None


def _make_nested_renderer(
    runtime: BuilderRuntime,
    parent_id: str,
    port_name: str,
    slot_name: str,
) -> Callable[[Any, str, int], str | None]:
    def _renderer(child_value: Any, _: str, depth_remaining: int) -> str | None:
        coerce = runtime["coerce"]
        coerced = coerce(child_value)
        next_view = _select_nested_view(runtime, slot_name, child_value, coerced, depth_remaining)
        if next_view is None:
            return None
        inline_html = _render_inline_child_view(runtime, coerced, slot_name, next_view, max(0, depth_remaining))
        if inline_html is not None:
            return inline_html
        child_id = _build_view(runtime, coerced, slot_name, next_view, max(0, depth_remaining))
        _add_edge(runtime, parent_id, child_id, tailport=port_name)
        return ""

    return _renderer


def _render_inline_child_view(
    runtime: BuilderRuntime,
    coerced_value: Any,
    slot_name: str,
    view: ViewKind,
    depth_remaining: int,
) -> str | None:
    try:
        child_root_id, child_graph = build_graph_view(
            coerced_value,
            slot_name,
            view,
            depth_remaining,
            item_limit=runtime["item_limit"],
            value_coercer=runtime["coerce"],
            view_resolver=runtime["resolver"],
        )
    except Exception:
        return None

    root_node = child_graph.nodes.get(child_root_id)
    if (
        root_node is not None
        and not child_graph.edges
        and len(child_graph.nodes) == 1
        and root_node.meta.get("html_label")
    ):
        return root_node.label

    direction = "TD" if view in {ViewKind.TREE, ViewKind.HASH_TABLE} else "LR"
    dot_source = render_graphviz_node_link(child_graph, direction=direction)
    img_src = _render_dot_to_image(dot_source, fmt="png")
    if img_src is None:
        return None
    return _image_html(img_src)


def _build_array_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    if isinstance(value, (set, frozenset)):
        array = sorted(value, key=lambda x: str(x))
    elif isinstance(value, (list, tuple)):
        array = list(value)
    else:
        raise TypeError("array_cells view expects list-like input")

    node_id = _new_node_id(runtime, "arr")
    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0

    value_cells: list[str] = []
    index_cells: list[str] = []
    limit = min(len(array), item_limit)

    for i in range(limit):
        port = f"{node_id}_item_{i}"
        nested_renderer = _make_nested_renderer(runtime, node_id, port, f"{name}[{i}]")
        cell_html = _format_nested_value(array[i], cell_depth, item_limit, nested_renderer, f"{name}[{i}]")
        value_cells.append(
            f'<td port="{port}" align="center" bgcolor="#ffffff" cellpadding="4">{cell_html}</td>'
        )
        index_cells.append(
            f"<td align='center'><font color='#dc2626' point-size='12'>{html_escape(str(i))}</font></td>"
        )

    if len(array) > item_limit:
        value_cells.append('<td align="center" bgcolor="#ffffff">…</td>')
        index_cells.append('<td align="center"></td>')

    table_html = _graphviz_array_block(value_cells, index_cells)
    _add_html_node(runtime, node_id, _wrap_label(name, table_html))
    return node_id


def _build_table_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    if not isinstance(value, dict):
        raise TypeError("table view expects dict input")

    item_limit = runtime["item_limit"]
    items = list(value.items())
    limit = min(len(items), item_limit)
    node_id = _new_node_id(runtime, ViewKind.TABLE)
    depth_budget = max(0, depth)
    inner_depth = depth_budget - 1 if depth_budget > 0 else 0

    rows = ["<tr><td bgcolor='#e5e7eb'><b>Key</b></td><td bgcolor='#e5e7eb'><b>Value</b></td></tr>"]
    for idx in range(limit):
        key, val = items[idx]
        port = f"{node_id}_val_{idx}"
        nested_renderer = _make_nested_renderer(runtime, node_id, port, f"{name}.{key}")
        val_html = _format_nested_value(val, inner_depth, item_limit, nested_renderer, f"{name}.{key}")
        rows.append(f"<tr><td>{_table_cell_text(key)}</td><td port='{port}'>{val_html}</td></tr>")

    if not items:
        rows.append("<tr><td colspan='2'>∅</td></tr>")
    elif len(items) > item_limit:
        rows.append("<tr><td colspan='2'>… (+more)</td></tr>")

    table_html = f"<table border='1' cellborder='1' cellspacing='0'>{''.join(rows)}</table>"
    _add_html_node(runtime, node_id, _wrap_label(name, table_html))
    return node_id


def _build_matrix_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    if not isinstance(value, (list, tuple)):
        raise TypeError("matrix view expects a list of lists/tuples")
    rows: list[list[Any]] = []
    for row in value:
        if not isinstance(row, (list, tuple)):
            raise TypeError("matrix view expects uniform sublists")
        rows.append(list(row))

    node_id = _new_node_id(runtime, ViewKind.MATRIX)
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
            cells: list[str] = [
                f"<td bgcolor='#fef3c7'><font color='#b45309'>{r_idx}</font></td>"
            ]
            for c_idx in range(col_limit):
                val = row[c_idx] if c_idx < len(row) else ""
                port = f"{node_id}_r{r_idx}_c{c_idx}"
                nested_renderer = _make_nested_renderer(runtime, node_id, port, f"{name}[{r_idx}][{c_idx}]")
                cell_html = _format_nested_value(
                    val,
                    cell_depth,
                    item_limit,
                    nested_renderer,
                    f"{name}[{r_idx}][{c_idx}]",
                )
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
    _add_html_node(runtime, node_id, _wrap_label(name, ''.join(body)))
    return node_id


def _build_hash_table_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    if not isinstance(value, list):
        raise TypeError("hash_table view expects list input")

    graph = runtime["graph"]
    item_limit = runtime["item_limit"]
    root_id = _new_node_id(runtime, "hash_root")
    header = "<font color='#0f172a' point-size='11'><b>hash_table</b></font>"
    _add_html_node(runtime, root_id, _wrap_label(None, header, show_title=False))

    depth_budget = max(0, depth)
    chain_depth = depth_budget - 1 if depth_budget > 0 else 0
    limit = min(len(value), item_limit)
    bucket_ids: list[str] = []
    bucket_rank_group = f"{root_id}_row"

    for idx in range(limit):
        bucket_id = _make_hash_bucket_node(runtime, idx, bucket_rank_group)
        bucket_ids.append(bucket_id)
        graph.add_edge(
            VisualEdge(root_id, bucket_id, type=EdgeKind.CONTAINS, meta={"edge_attrs": {"style": "invis"}})
        )
        _populate_hash_bucket(runtime, bucket_id, value[idx], idx, name, chain_depth)

    if len(bucket_ids) > 1:
        for left, right in zip(bucket_ids, bucket_ids[1:]):
            graph.add_edge(
                VisualEdge(left, right, type=EdgeKind.LAYOUT, meta={"edge_attrs": {"style": "invis"}})
            )

    if len(value) > limit:
        more_id = _new_node_id(runtime, "hash_more")
        _add_html_node(runtime, more_id, "<font color='#475569'>… (+more buckets)</font>")
        _add_edge(runtime, root_id, more_id)

    return root_id


def _make_hash_bucket_node(runtime: BuilderRuntime, idx: int, rank_group: str) -> str:
    bucket_id = _new_node_id(runtime, "hash_bucket")
    label = (
        "<table border='0' cellborder='0' cellspacing='0'>"
        "<tr><td><table border='1' cellborder='0' cellspacing='0' cellpadding='6'>"
        "<tr><td><font point-size='12'><b>H</b></font></td></tr></table></td></tr>"
        f"<tr><td align='center'><font color='#dc2626'>{idx}</font></td></tr></table>"
    )
    meta = {"html_label": True, "node_attrs": {"shape": "plain"}, "rank": rank_group}
    runtime["graph"].add_node(VisualNode(bucket_id, NodeKind.OBJECT, label, meta))
    return bucket_id


def _populate_hash_bucket(
    runtime: BuilderRuntime,
    bucket_id: str,
    bucket_value: Any,
    idx: int,
    name: str,
    depth_remaining: int,
) -> None:
    item_limit = runtime["item_limit"]
    entries, clipped = _hash_bucket_entries(bucket_value, min(item_limit, 8))
    prev = bucket_id
    slot_prefix = f"{name}[{idx}]"
    for j, entry in enumerate(entries):
        entry_id = _make_hash_entry_node(runtime, entry, f"{slot_prefix}[{j}]", depth_remaining)
        runtime["graph"].add_edge(
            VisualEdge(prev, entry_id, type=EdgeKind.CONTAINS, meta={"edge_attrs": {"color": "#1f2933"}})
        )
        prev = entry_id
    if clipped:
        ellipsis_id = _new_node_id(runtime, "hash_clip")
        _add_html_node(runtime, ellipsis_id, "<font color='#0f172a'>…</font>")
        runtime["graph"].add_edge(
            VisualEdge(
                prev,
                ellipsis_id,
                type=EdgeKind.CONTAINS,
                meta={"edge_attrs": {"color": "#1f2933", "style": "dashed"}},
            )
        )


def _make_hash_entry_node(
    runtime: BuilderRuntime,
    value: Any,
    slot_name: str,
    depth_remaining: int,
) -> str:
    node_id = _new_node_id(runtime, "hash_val")
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
        next_view = _select_nested_view(runtime, slot_name, value, coerced, depth_remaining)
        if next_view is not None:
            child_id = _build_view(runtime, coerced, slot_name, next_view, max(0, depth_remaining))
            _add_edge(runtime, node_id, child_id)
    return node_id


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


def _build_bar_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
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

    node_id = _new_node_id(runtime, ViewKind.BAR)
    _add_html_node(runtime, node_id, _wrap_label(name, chart_html))
    return node_id


def _build_image_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    src = _detect_image_source(value, strict=True)
    node_id = _new_node_id(runtime, ViewKind.IMAGE)
    _add_html_node(runtime, node_id, _wrap_label(name, _image_html(src)))
    return node_id


def _build_linked_list_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    seq = _collect_linked_list_labels(value, runtime["item_limit"])
    if seq is None:
        raise TypeError("linked_list view expects objects with .next")
    values, truncated = seq

    node_id = _new_node_id(runtime, "list")
    depth_budget = max(0, depth)
    cell_depth = depth_budget - 1 if depth_budget > 0 else 0
    item_limit = runtime["item_limit"]

    if not values:
        html = "<table border='1' cellborder='1' cellspacing='0'><tr><td align='center'>∅</td></tr></table>"
    else:
        cells: list[str] = []
        for idx, val in enumerate(values):
            port = f"{node_id}_node_{idx}"
            nested_renderer = _make_nested_renderer(runtime, node_id, port, f"{name}[{idx}]")
            cell_html = _format_nested_value(val, cell_depth, item_limit, nested_renderer, f"{name}[{idx}]")
            value_block = (
                "<table border='1' cellborder='1' cellspacing='0'>"
                f"<tr><td port='{port}' bgcolor='#ffffff' cellpadding='6'>{cell_html}</td></tr></table>"
            )
            cells.append(f"<td border='0' cellborder='0'>{value_block}</td>")
            cells.append(
                "<td border='0' cellborder='0' sides='' width='24' align='center'><font color='#94a3b8'>&rarr;</font></td>"
            )
        tail_inner = "<font color='#9ca3af'>∅</font>"
        if truncated:
            tail_inner = "…"
        tail = f"<table border='1' cellborder='1' cellspacing='0'><tr><td align='center'>{tail_inner}</td></tr></table>"
        cells.append(f"<td border='0' cellborder='0'>{tail}</td>")
        html = f"<table border='0' cellborder='0' cellspacing='2'><tr>{''.join(cells)}</tr></table>"

    _add_html_node(runtime, node_id, _wrap_label(name, html))
    return node_id


def _build_heap_dual_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    if not isinstance(value, list):
        raise TypeError("heap_dual view expects list input")

    container_id = _new_node_id(runtime, "heap")
    container_label = (
        "<table border='0' cellborder='0' cellspacing='0'>"
        f"<tr><td align='center'><font point-size='16'><b>{html_escape(name)}</b></font></td></tr>"
        "<tr><td align='center'><font color='#64748b' point-size='11'>heap_dual</font></td></tr></table>"
    )
    _add_html_node(runtime, container_id, container_label)

    array_id = _build_array_view(runtime, value, f"{name}[array]", depth)
    _add_edge(runtime, container_id, array_id)

    tree_payload = _heap_tree_payload(value, runtime["item_limit"])
    if tree_payload is not None:
        tree_id = _build_tree_view(runtime, tree_payload, f"{name}[tree]", depth)
        _add_edge(runtime, container_id, tree_id)
    else:
        empty_id = _new_node_id(runtime, "heap_empty")
        empty_html = "<table border='1' cellborder='1' cellspacing='0'><tr><td align='center'>∅</td></tr></table>"
        _add_html_node(runtime, empty_id, _wrap_label(f"{name}[tree]", empty_html))
        _add_edge(runtime, container_id, empty_id)

    return container_id


def _heap_tree_payload(heap: list[Any], item_limit: int) -> Any | None:
    if not heap:
        return None
    limit = min(len(heap), item_limit)

    def build(idx: int) -> Any | None:
        if idx >= limit or idx >= len(heap):
            return None
        node: dict[str, Any] = {"label": f"[{idx}] {heap[idx]}"}
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


def _merge_visual_graph(runtime: BuilderRuntime, other: VisualGraph, prefix: str, root_hint: str | None = None) -> str:
    graph = runtime["graph"]
    mapping: dict[str, str] = {}
    for node_id, node in other.nodes.items():
        new_id = f"{prefix}__{node_id}"
        mapping[node_id] = new_id
        graph.add_node(VisualNode(new_id, node.type, node.label, dict(node.meta)))
    for edge in other.edges:
        graph.add_edge(
            VisualEdge(
                mapping[edge.src],
                mapping[edge.dst],
                type=edge.type,
                label=edge.label,
                meta=dict(edge.meta),
            )
        )
    if root_hint is not None and root_hint in mapping:
        return mapping[root_hint]
    if other.anchors:
        anchor_target = other.anchors[0].node_id
        if anchor_target in mapping:
            return mapping[anchor_target]
    if "ROOT" in mapping:
        return mapping["ROOT"]
    return next(iter(mapping.values()))


def _attach_view_title(runtime: BuilderRuntime, _: str, name: str, __: str) -> None:
    if not name:
        return
    runtime_graph: VisualGraph = runtime["graph"]
    runtime_graph.graph_attrs["label"] = f"<<font point-size='16' color='#0f172a'><b>{html_escape(name)}</b></font>>"
    runtime_graph.graph_attrs.setdefault("labelloc", "t")
    runtime_graph.graph_attrs.setdefault("labeljust", "c")
    runtime_graph.graph_attrs.setdefault("fontname", "Helvetica")
    runtime_graph.graph_attrs.setdefault("fontsize", "16")
    runtime_graph.graph_attrs.setdefault("fontcolor", "#0f172a")


def _build_tree_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    root_hint, tg = build_tree(
        value,
        name=name,
        max_nodes=runtime["item_limit"],
        nested_depth=depth,
        max_items=runtime["item_limit"],
    )
    prefix = _new_node_id(runtime, ViewKind.TREE)
    merged_root = _merge_visual_graph(runtime, tg, prefix, root_hint=root_hint)
    _attach_view_title(runtime, merged_root, name, "tree_label")
    return merged_root


def _build_graph_view(runtime: BuilderRuntime, value: Any, name: str, depth: int) -> str:
    graph_data = _extract_graph_data(value)
    if graph_data is None:
        raise TypeError("graph view expects a networkx graph or mapping with nodes/edges")

    nodes, edges, directed = graph_data
    item_limit = runtime["item_limit"]
    depth_budget = max(0, depth)
    node_label_depth = depth_budget - 1 if depth_budget > 0 else 0
    limit = min(len(nodes), item_limit)
    g = VisualGraph()
    container_id = _new_node_id(runtime, "graph_root")
    g.add_node(
        VisualNode(
            container_id,
            NodeKind.OBJECT,
            "",
            {"kind": "graph_root", "node_attrs": {"shape": "point", "style": "invis", "width": "0.01", "height": "0.01"}},
        )
    )

    id_map: dict[Any, str] = {}
    node_ids: list[str] = []
    for idx, (key, payload) in enumerate(nodes[:limit]):
        label_text, is_html = _format_value_label(
            payload,
            node_label_depth,
            item_limit,
            None,
            f"{name}.nodes[{idx}]",
        )
        meta: dict[str, Any] = {"kind": "graph_node"}
        if is_html:
            meta["html_label"] = True
            meta["node_attrs"] = {"shape": "plain"}
        local_id = f"{container_id}_n{idx}"
        g.add_node(VisualNode(local_id, NodeKind.OBJECT, label_text, meta))
        id_map[key] = local_id
        node_ids.append(local_id)

    edge_limit = min(len(edges), item_limit * 2)
    for src_key, dst_key, label in edges[:edge_limit]:
        sid = id_map.get(src_key)
        did = id_map.get(dst_key)
        if sid is None or did is None:
            continue
        edge_meta: dict[str, Any] = {}
        if not directed:
            edge_meta["edge_attrs"] = {"dir": "none"}
        g.add_edge(VisualEdge(sid, did, type=EdgeKind.LINK, label=label, meta=edge_meta))

    if node_ids:
        for node_id in node_ids:
            g.add_edge(
                VisualEdge(
                    container_id,
                    node_id,
                    type=EdgeKind.LAYOUT,
                    meta={"edge_attrs": {"style": "invis"}},
                )
            )

    prefix = _new_node_id(runtime, ViewKind.GRAPH)
    merged_root = _merge_visual_graph(runtime, g, prefix, root_hint=container_id)
    _attach_view_title(runtime, merged_root, name, "graph_label")
    return merged_root


def _extract_graph_data(value: Any) -> tuple[list[tuple[Any, Any]], list[tuple[Any, Any, Any]], bool] | None:
    nk = _try_networkx_edges_nodes(value)
    if nk is not None:
        nodes, edges, directed = nk
        normalized_nodes: list[tuple[Any, Any]] = []
        for node_key, attrs in nodes:
            payload = attrs.get("value") or attrs.get("label") or attrs.get("data") or (attrs if attrs else node_key)
            normalized_nodes.append((node_key, payload))
        normalized_edges = [(u, v, _edge_label_from_attrs(attrs)) for u, v, attrs in edges]
        return normalized_nodes, normalized_edges, directed
    if _looks_like_graph_mapping(value):
        return _graph_data_from_mapping(value)
    return None


def _edge_label_from_attrs(attrs: Mapping[str, Any]) -> Any:
    for key in ("label", "value", "weight", "text"):
        if key in attrs and attrs[key] is not None:
            return attrs[key]
    return None


def _graph_data_from_mapping(value: Any) -> tuple[list[tuple[Any, Any]], list[tuple[Any, Any, Any]], bool] | None:
    if not isinstance(value, Mapping):
        return None
    edges_raw = value.get("edges")
    if not isinstance(edges_raw, list):
        return None
    directed = bool(value.get("directed", True))
    nodes_raw = value.get("nodes")
    entries: list[tuple[Any, Any]] = []
    seen_keys: dict[Any, Any] = {}
    if isinstance(nodes_raw, list):
        for entry in nodes_raw:
            key, payload = _normalize_graph_node_entry(entry)
            if key in seen_keys:
                continue
            seen_keys[key] = payload
            entries.append((key, payload))
    edges: list[tuple[Any, Any, Any]] = []
    for entry in edges_raw:
        if isinstance(entry, Mapping):
            src = entry.get("source") or entry.get("from") or entry.get("src")
            dst = entry.get("target") or entry.get("to") or entry.get("dst")
            if src is None or dst is None:
                continue
            edges.append((src, dst, entry.get("label")))
        elif isinstance(entry, (tuple, list)) and len(entry) >= 2:
            src = entry[0]
            dst = entry[1]
            label = entry[2] if len(entry) >= 3 else None
            edges.append((src, dst, label))
    for key in seen_keys.keys():
        if key not in {k for k, _ in entries}:
            entries.append((key, seen_keys[key]))
    if not entries:
        derived_nodes = sorted({src for src, _, _ in edges} | {dst for _, dst, _ in edges})
        entries = [(node, node) for node in derived_nodes]
    return entries, edges, directed


def _normalize_graph_node_entry(entry: Any) -> tuple[Any, Any]:
    if isinstance(entry, Mapping):
        key = entry.get("id") or entry.get("name") or entry.get("key")
        if key is None:
            key = entry.get("label") or entry.get("value") or entry.get("data")
        payload = entry.get("value") or entry.get("label") or entry.get("data") or entry
        return key, payload
    if isinstance(entry, (tuple, list)) and entry:
        key = entry[0]
        payload = entry[1] if len(entry) > 1 else entry[0]
        return key, payload
    return entry, entry


_VIEW_BUILDERS: dict[ViewKind, Callable[[BuilderRuntime, Any, str, int], str]] = {
    ViewKind.ARRAY_CELLS: _build_array_view,
    ViewKind.TABLE: _build_table_view,
    ViewKind.MATRIX: _build_matrix_view,
    ViewKind.HASH_TABLE: _build_hash_table_view,
    ViewKind.LINKED_LIST: _build_linked_list_view,
    ViewKind.TREE: _build_tree_view,
    ViewKind.GRAPH: _build_graph_view,
    ViewKind.HEAP_DUAL: _build_heap_dual_view,
    ViewKind.BAR: _build_bar_view,
    ViewKind.IMAGE: _build_image_view,
}
