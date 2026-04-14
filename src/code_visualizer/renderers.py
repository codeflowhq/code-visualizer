# renderers.py
# mypy: disable-error-code=import-untyped,no-any-return,arg-type
from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from graphviz import Digraph

from .models import (
    EdgeKind,
    NodeKind,
    VisualEdge,
    VisualGraph,
    VisualNode,
)
from .utils.image_sources import _detect_image_source
from .utils.structure_detection import (
    _collect_linked_list_labels,
    _hash_bucket_entries,
    _looks_like_graph_mapping,
    _looks_like_hash_table,
    _tree_children,
    _try_networkx_edges_nodes,
)
from .utils.type_patterns import _match_type_pattern_override
from .view_types import ViewKind
from .utils.value_formatting import dot_escape_label, stable_svg_id as _stable_svg_id, table_cell_text as _table_cell_text
from .view_utils import (
    NestedRenderer,
    _digraph_edge,
    _format_matrix_html,
    _format_nested_value,
    _format_value_label,
    _is_list_numbers,
    _is_matrix_value,
)

ARRAY_RENDERER_VERSION = "cell-node-v1"

_AUTO_VIEW_TYPE_MAP: dict[str, ViewKind] = {
    # matrix-like
    "list[list]": ViewKind.MATRIX,
    "list[tuple]": ViewKind.MATRIX,
    "tuple[list]": ViewKind.MATRIX,
    "tuple[tuple]": ViewKind.MATRIX,
    # numeric/sequence defaults
    "list[number]": ViewKind.ARRAY_CELLS,
    "tuple[number]": ViewKind.ARRAY_CELLS,
    "set[number]": ViewKind.ARRAY_CELLS,
    "frozenset[number]": ViewKind.ARRAY_CELLS,
    # generic sequence fallback
    "list[any]": ViewKind.ARRAY_CELLS,
    "tuple[any]": ViewKind.ARRAY_CELLS,
    "set[any]": ViewKind.ARRAY_CELLS,
    "frozenset[any]": ViewKind.ARRAY_CELLS,
    # dict/table fallbacks
    "dict[str, any]": ViewKind.TABLE,
    "dict[any, any]": ViewKind.TABLE,
    "dict": ViewKind.TABLE,
    # structural detectors
    "linked_list": ViewKind.LINKED_LIST,
    "tree": ViewKind.TREE,
}


def choose_view(value: Any) -> ViewKind:
    if _detect_image_source(value) is not None:
        return ViewKind.IMAGE
    if _try_networkx_edges_nodes(value) is not None:
        return ViewKind.GRAPH
    if _looks_like_graph_mapping(value):
        return ViewKind.GRAPH
    if _collect_linked_list_labels(value, max_nodes=10) is not None:
        return ViewKind.LINKED_LIST
    if isinstance(value, (list, tuple)) and _looks_like_hash_table(list(value)):
        return ViewKind.HASH_TABLE
    if _tree_children(value) is not None:
        return ViewKind.TREE
    pattern_view = _match_type_pattern_override(value, _AUTO_VIEW_TYPE_MAP)
    if pattern_view is not None:
        return pattern_view
    return ViewKind.NODE_LINK


def render_graphviz_node_link(g: VisualGraph, direction: Literal["LR", "TD"] = "LR") -> str:
    rankdir = "LR" if direction == "LR" else "TB"
    dot = Digraph("G")
    graph_attrs = {"rankdir": rankdir, "nodesep": "0.6", "ranksep": "0.7"}
    graph_attrs.update({k: str(v) for k, v in g.graph_attrs.items()})
    dot.attr("graph", **graph_attrs)
    dot.attr("node", shape="box", style="rounded,filled", fillcolor="#ffffff", color="#1f2933", fontname="Helvetica")
    dot.attr("edge", color="#4b5563", fontname="Helvetica")

    rank_groups: dict[str, list[str]] = defaultdict(list)
    min_rank: list[str] = []
    max_rank: list[str] = []

    def _assign_rank(spec: str, node_id: str) -> None:
        if spec == "min":
            min_rank.append(node_id)
        elif spec == "max":
            max_rank.append(node_id)
        else:
            rank_groups[spec].append(node_id)

    for nid in sorted(g.nodes.keys()):
        node = g.nodes[nid]
        node_attrs = dict(node.meta.get("node_attrs", {}))
        if node.meta.get("html_label"):
            label = node.label
            wrapper = f"<{label}>"
            dot.node(str(nid), label=wrapper, **node_attrs)
        else:
            label = dot_escape_label(node.label)
            dot.node(str(nid), label=label, **node_attrs)
        rank_spec = node.meta.get("rank")
        if isinstance(rank_spec, str):
            _assign_rank(rank_spec, str(nid))
        elif isinstance(rank_spec, (list, tuple, set)):
            for spec in rank_spec:
                if isinstance(spec, str):
                    _assign_rank(spec, str(nid))

    for e in g.edges:
        attrs = dict(e.meta.get("edge_attrs", {}))
        tailport = e.meta.get("tailport")
        headport = e.meta.get("headport")
        if tailport:
            attrs["tailport"] = tailport
        if headport:
            attrs["headport"] = headport
        if e.label is not None:
            attrs["label"] = dot_escape_label(e.label)
        dot.edge(str(e.src), str(e.dst), **attrs)

    for group, members in rank_groups.items():
        if len(members) > 1:
            dot.body.append(f"{{rank=same; {' '.join(members)} }}")

    if min_rank:
        dot.body.append(f"{{rank=min; {' '.join(min_rank)} }}")
    if max_rank:
        dot.body.append(f"{{rank=max; {' '.join(max_rank)} }}")

    return dot.source


def render_graphviz_array_cells(
    arr: list[Any],
    title: str = "array",
    *,
    max_items: int = 50,
    nested_depth: int = 0,
    nested_renderer: NestedRenderer | None = None,
) -> str:
    n = len(arr)
    limit = min(n, max_items)

    dot = Digraph("array")
    dot.attr("graph", labelloc="t", label=dot_escape_label(f"{title} [cell-node-v1]"), ranksep="0.18", nodesep="0.02")
    dot.attr("node", shape="plain", margin="0", fontname="Helvetica")
    dot.attr("edge", style="invis")
    depth_budget = max(0, nested_depth)

    if n == 0:
        empty_label = (
            f'<table border="1" cellborder="1" cellspacing="0">'
            f'<tr><td id="{_stable_svg_id(title, "value", "empty")}" cellpadding="6">∅</td></tr>'
            '</table>'
        )
        dot.node(
            "array_empty",
            label=f"<{empty_label}>",
            id=_stable_svg_id(title, "node", "empty"),
        )
        return dot.source

    value_node_ids: list[str] = []
    index_node_ids: list[str] = []
    for i in range(limit):
        cell_depth = depth_budget - 1 if depth_budget > 0 else 0
        if cell_depth == 0 and _is_matrix_value(arr[i]):
            cell_depth = 1
        slot_name = f"{title}[{i}]"
        cell_html = _format_nested_value(
            arr[i],
            cell_depth,
            max_items,
            nested_renderer,
            slot_name,
        )
        value_node_id = f"value_{i}"
        index_node_id = f"index_{i}"
        value_node_ids.append(value_node_id)
        index_node_ids.append(index_node_id)

        value_label = (
            f'<table border="1" cellborder="1" cellspacing="0">'
            f'<tr><td id="{_stable_svg_id(title, "value", i)}" align="center" bgcolor="#eef6ff" color="#2563eb" cellpadding="4">CELL {i}: {cell_html}</td></tr>'
            '</table>'
        )
        index_label = (
            '<table border="0" cellborder="0" cellspacing="0">'
            f'<tr><td id="{_stable_svg_id(title, "index", i)}" width="48" align="center"><font color="#dc2626" point-size="12">{i}</font></td></tr>'
            '</table>'
        )
        dot.node(value_node_id, label=f"<{value_label}>", id=_stable_svg_id(title, "node", "value", i))
        dot.node(index_node_id, label=f"<{index_label}>", id=_stable_svg_id(title, "node", "index", i))

    if n > max_items:
        value_node_ids.append("value_ellipsis")
        index_node_ids.append("index_ellipsis")
        ellipsis_label = (
            f'<table border="1" cellborder="1" cellspacing="0">'
            f'<tr><td id="{_stable_svg_id(title, "value", "ellipsis")}" width="48" height="36" align="center">…</td></tr>'
            '</table>'
        )
        index_ellipsis_label = (
            '<table border="0" cellborder="0" cellspacing="0">'
            f'<tr><td id="{_stable_svg_id(title, "index", "ellipsis")}" width="48"></td></tr>'
            '</table>'
        )
        dot.node("value_ellipsis", label=f"<{ellipsis_label}>", id=_stable_svg_id(title, "node", "value", "ellipsis"))
        dot.node("index_ellipsis", label=f"<{index_ellipsis_label}>", id=_stable_svg_id(title, "node", "index", "ellipsis"))

    for left, right in zip(value_node_ids, value_node_ids[1:]):
        dot.edge(left, right)
    for left, right in zip(index_node_ids, index_node_ids[1:]):
        dot.edge(left, right)

    if value_node_ids:
        dot.body.append("{rank=same; " + " ".join(value_node_ids) + " }")
    if index_node_ids:
        dot.body.append("{rank=same; " + " ".join(index_node_ids) + " }")

    return dot.source


def render_graphviz_matrix(
    matrix: list[list[Any]],
    title: str = "matrix",
    *,
    max_rows: int = 25,
    max_cols: int = 25,
    nested_depth: int = 0,
    max_items: int = 50,
    nested_renderer: NestedRenderer | None = None,
) -> str:
    rows = [list(r) for r in matrix]
    dot = Digraph("matrix")
    dot.attr("graph", labelloc="t", label=dot_escape_label(title))
    dot.attr("node", shape="plain")

    depth_budget = max(0, nested_depth)
    nested_depth_inner = depth_budget - 1 if depth_budget > 0 else 0
    table_html = _format_matrix_html(
        rows,
        nested_depth_inner,
        max_items,
        include_headers=True,
        row_limit=max_rows,
        col_limit=max_cols,
        nested_renderer=nested_renderer,
        slot_name=title,
    )
    dot.node("matrix", label=f"<{table_html}>")
    return dot.source


def render_graphviz_bar(arr: list[Any], title: str = "bar", *, max_items: int = 50) -> str:
    if not _is_list_numbers(arr):
        raise TypeError("bar expects list[number]")

    labels: list[str] = []
    nums: list[float] = []

    for i, v in enumerate(arr[:max_items]):
        labels.append(str(i))
        nums.append(float(v))

    if len(arr) > max_items:
        labels.append("…")
        nums.append(0.0)

    if not labels:
        dot = Digraph("bar")
        dot.attr("graph", labelloc="t", label=dot_escape_label(title))
        dot.attr("node", shape="plain")
        dot.node("bars", label=f'<<table id="{_stable_svg_id(title, "wrapper")}" border="0"><tr><td id="{_stable_svg_id(title, "value", "empty")}">∅</td></tr></table>>')
        return dot.source

    max_abs = max(abs(n) for n in nums)
    max_abs = max_abs if max_abs != 0 else 1.0

    max_height_px = 160
    dot = Digraph("bar")
    dot.attr("graph", labelloc="t", label=dot_escape_label(title))
    dot.attr("node", shape="plain")
    table: list[str] = []
    table.append('<table border="0" cellborder="0" cellspacing="10"><tr>')

    def bar_column(label: str, val: float, height: int, color: str) -> str:
        value_text = int(val) if float(val).is_integer() else round(val, 2)
        gap = max(0, max_height_px - height)
        inner = (
            "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
            f"<tr><td height='{gap}'></td></tr>"
            f"<tr><td bgcolor='{color}' width='34' height='{height}'></td></tr>"
            f"<tr><td align='center'><font point-size='11' color='#0f172a'>{value_text}</font></td></tr>"
            f"<tr><td align='center'><font point-size='9' color='#dc2626'>{label}</font></td></tr>"
            "</table>"
        )
        return f"<td id='{_stable_svg_id(title, 'bar', label)}' valign='bottom'>{inner}</td>"

    for lbl, val in zip(labels, nums):
        norm = abs(val) / max_abs if max_abs != 0 else 0
        height = max(24, int(max_height_px * norm))
        color = "#bae6fd" if val >= 0 else "#fecaca"
        table.append(bar_column(lbl, val, height, color))

    if len(arr) > max_items:
        ellipsis_inner = (
            "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
            "<tr><td align='center'>…</td></tr>"
            "<tr><td align='center'><font point-size='11'>+</font></td></tr>"
            "<tr><td></td></tr>"
            "</table>"
        )
        table.append(f"<td>{ellipsis_inner}</td>")

    table.append("</tr></table>")
    table_html = "".join(table)
    dot.node("bars", label=f"<{table_html}>")
    return dot.source


def render_graphviz_table(
    d: dict[Any, Any],
    title: str = "dict",
    *,
    max_items: int = 50,
    nested_depth: int = 0,
    nested_renderer: NestedRenderer | None = None,
) -> str:
    items = list(d.items())
    n = len(items)
    limit = min(n, max_items)

    dot = Digraph("dict")
    dot.attr("graph", labelloc="t", label=dot_escape_label(title))
    dot.attr("node", shape="plain")
    depth_budget = max(0, nested_depth)
    table: list[str] = []
    table.append(f'<table id="{_stable_svg_id(title, "wrapper")}" border="1" cellborder="1" cellspacing="0">')
    table.append(f'<tr><td id="{_stable_svg_id(title, "header", "key")}" bgcolor="#e5e7eb"><b>Key</b></td><td id="{_stable_svg_id(title, "header", "value")}" bgcolor="#e5e7eb"><b>Value</b></td></tr>')

    if n == 0:
        table.append(f'<tr><td id="{_stable_svg_id(title, "row", "empty")}" colspan="2">∅</td></tr>')
    else:
        inner_depth = depth_budget - 1 if depth_budget > 0 else 0
        for i in range(limit):
            k, v = items[i]
            val_html = _format_nested_value(
                v,
                inner_depth,
                max_items,
                nested_renderer,
                f"{title}.{k}",
            )
            table.append(f'<tr><td id="{_stable_svg_id(title, "row", i, "key")}">{_table_cell_text(k)}</td><td id="{_stable_svg_id(title, "row", i, "value")}">{val_html}</td></tr>')
        if n > max_items:
            table.append(f'<tr><td id="{_stable_svg_id(title, "row", "ellipsis")}" colspan="2">… (+more)</td></tr>')

    table.append("</table>")
    table_html = "".join(table)
    dot.node("dictview", label=f"<{table_html}>")
    return dot.source


def build_tree(
    root: Any,
    *,
    name: str = "root",
    max_nodes: int = 80,
    nested_depth: int = 0,
    max_items: int = 50,
) -> tuple[str, VisualGraph]:
    g = VisualGraph()

    info_cache: dict[int, tuple[Any, list[Any]] | None] = {}
    id_map: dict[int, str] = {}
    signature_counts: dict[str, int] = {}

    def tree_info(node: Any) -> tuple[Any, list[Any]] | None:
        key = id(node)
        if key not in info_cache:
            info_cache[key] = _tree_children(node)
        return info_cache[key]

    def node_signature(node: Any) -> str:
        info = tree_info(node)
        raw_label = info[0] if info is not None else node
        payload = f"{type(node).__name__}|{raw_label!r}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]

    def nid(node: Any) -> str:
        object_id = id(node)
        existing = id_map.get(object_id)
        if existing is not None:
            return existing

        signature = node_signature(node)
        signature_counts[signature] = signature_counts.get(signature, 0) + 1
        node_id = f"t_{signature}_{signature_counts[signature]}"
        id_map[object_id] = node_id
        return node_id

    def ensure_node(node: Any) -> str:
        node_id = nid(node)
        if node_id not in g.nodes:
            info = tree_info(node)
            raw_label = info[0] if info is not None else node
            label_text, is_html = _format_value_label(raw_label, nested_depth, max_items)
            meta: dict[str, Any] = {"kind": "tree_node", "node_attrs": {"shape": "circle"}}
            if is_html:
                meta["html_label"] = True
                meta["node_attrs"] = {"shape": "plain"}
            g.add_node(VisualNode(node_id, NodeKind.OBJECT, label_text, meta))
        return node_id

    root_id = ensure_node(root)

    stack = [root]
    seen: set[int] = set()
    made = 0

    while stack and made < max_nodes:
        cur = stack.pop()
        object_id = id(cur)
        if object_id in seen:
            continue
        seen.add(object_id)
        made += 1

        info = tree_info(cur)
        if info is None:
            continue
        _, kids = info

        src = ensure_node(cur)
        for child in kids:
            child_id = ensure_node(child)
            g.add_edge(VisualEdge(src, child_id, type=EdgeKind.CONTAINS, label=None))
            stack.append(child)

    if stack:
        eid = "CUT"
        g.add_node(VisualNode(eid, NodeKind.ELLIPSIS, "… (cutoff)", {"cutoff": True}))
        g.add_edge(VisualEdge(root_id, eid, type=EdgeKind.CONTAINS, label=None))

    return root_id, g



def render_graphviz_linked_list(
    head: Any,
    title: str = "list",
    *,
    max_nodes: int = 80,
    nested_depth: int = 0,
    max_items: int = 50,
) -> str:
    seq = _collect_linked_list_labels(head, max_nodes)
    if seq is None:
        raise TypeError("linked_list view expects an object with .next pointer")
    values, truncated = seq

    dot = Digraph("linked")
    dot.attr("graph", labelloc="t", label=dot_escape_label(title), rankdir="LR")
    dot.attr("node", shape="plaintext", fontname="Helvetica")

    if not values:
        dot.node("empty", label="∅")
        return dot.source

    for idx, value in enumerate(values):
        cell_label, html_label = _format_value_label(value, nested_depth, max_items)
        if html_label:
            value_cell = f'<td port="val" bgcolor="#ffffff">{cell_label}</td>'
        else:
            value_cell = f'<td port="val" width="60" bgcolor="#ffffff">{dot_escape_label(cell_label)}</td>'
        node_label = (
            '<<table border="1" cellborder="1" cellspacing="0" color="#1f2933">'
            f"<tr>{value_cell}"
            '<td port="next" width="24" bgcolor="#f3f4f6">&rarr;</td></tr>'
            "</table>>"
        )
        dot.node(f"n{idx}", label=node_label)

    for idx in range(len(values) - 1):
        _digraph_edge(dot, f"n{idx}:next", f"n{idx+1}:val")

    if truncated:
        dot.node("tail_ellipsis", label="…", shape="plaintext")
        _digraph_edge(dot, f"n{len(values) - 1}:next", "tail_ellipsis")
    else:
        _digraph_edge(dot, f"n{len(values) - 1}:next", "null", style="dashed", color="#9ca3af")
        dot.node("null", label="None", shape="plaintext")

    dot.body.append(f"{{rank=same; {' '.join(f'n{i}' for i in range(len(values)))} }}")

    return dot.source


def render_graphviz_hash_table(
    table: list[Any],
    title: str = "hash_table",
    *,
    max_buckets: int = 50,
    max_chain_items: int = 8,
    nested_depth: int = 0,
) -> str:
    if not isinstance(table, list):
        raise TypeError("hash_table view expects a list of buckets")

    total = len(table)
    limit = min(total, max_buckets)
    buckets = table[:limit]

    dot = Digraph("hash")
    dot.attr(
        "graph",
        labelloc="t",
        nodesep="0.9",
        ranksep="1.2",
        splines="true",
        label=f'<<font point-size="18"><b>{dot_escape_label(title)}</b></font><br/><font point-size="12">(buckets={total})</font>>',
    )
    dot.attr("edge", color="#4b5563", arrowsize="0.6")
    dot.attr("node", fontname="Helvetica")

    bucket_nodes: list[str] = []
    for idx in range(limit):
        bid = f"b{idx}"
        bucket_nodes.append(bid)
        bucket_label = (
            '<<table border="0" cellborder="0" cellspacing="0">'
            f'<tr><td id="{_stable_svg_id(title, "bucket", idx, "hook")}" port="hook" width="46" height="38" border="1" color="#1f2933">'
            '<font point-size="16"><b>H</b></font></td></tr>'
            f'<tr><td id="{_stable_svg_id(title, "bucket", idx, "index")}"><font color="#dc2626" point-size="12">{idx}</font></td></tr>'
            "</table>>"
        )
        dot.node(bid, label=bucket_label, shape="plaintext")

    if bucket_nodes:
        dot.body.append(f"{{rank=same; {' '.join(bucket_nodes)} }}")

    for idx, bucket in enumerate(buckets):
        entries, clipped = _hash_bucket_entries(bucket, max_chain_items)
        prev = f"b{idx}:hook"
        for j, val in enumerate(entries):
            nid = f"bucket_{idx}_{j}"
            label_text, is_html = _format_value_label(val, nested_depth, max_chain_items)
            if is_html:
                dot.node(nid, label=f"<{label_text}>", shape="plaintext")
            else:
                dot.node(nid, label=dot_escape_label(label_text), shape="circle", color="#1f2933")
            _digraph_edge(dot, prev, nid)
            prev = nid
        if clipped:
            ell = f"bucket_{idx}_ellipsis"
            dot.node(ell, label="…", shape="plaintext")
            _digraph_edge(dot, prev, ell)

    if total > limit and bucket_nodes:
        dot.node("more", label="… (+more buckets)", shape="plaintext")
        _digraph_edge(dot, bucket_nodes[-1], "more", style="dashed", color="#9ca3af")

    return dot.source


def render_graphviz_scalar(
    value: Any,
    title: str = "value",
    *,
    nested_depth: int = 0,
    max_items: int = 50,
) -> str:
    dot = Digraph("scalar")
    dot.attr("graph", labelloc="t", label=dot_escape_label(title))
    dot.attr("node", shape="plaintext", fontname="Helvetica", fontcolor="#0f172a", fontsize="16")
    label_text, is_html = _format_value_label(value, nested_depth, max_items)
    if is_html:
        dot.node("scalar_value", f"<{label_text}>")
    else:
        dot.node("scalar_value", dot_escape_label(label_text))
    return dot.source


def render_graphviz_image(src: Any, title: str = "image") -> str:
    dot = Digraph("image")
    dot.attr("graph", labelloc="t", label=dot_escape_label(title))
    resolved = _detect_image_source(src, strict=True)
    image_path = Path(resolved)
    dot.graph_attr["imagepath"] = str(image_path.parent)
    dot.attr("node", shape="none", label="")
    dot.node("image_value", image=image_path.name, imagescale="true")
    return dot.source
