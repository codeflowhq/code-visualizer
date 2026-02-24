"""Graphviz view builder shared by nested visualizations."""

from __future__ import annotations

from html import escape as html_escape
from typing import Any, Mapping, Callable

from edcraft_engine.code_visualizer.models import VisualGraph, VisualNode, VisualEdge
from edcraft_engine.code_visualizer.renderers import build_rooted_tree_graph, render_graphviz_node_link
from edcraft_engine.code_visualizer.view_types import ViewKind
from edcraft_engine.code_visualizer.view_utils import (
    _collect_linked_list_labels,
    _bar_chart_html,
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


_NESTED_HTML_VIEWS: set[ViewKind] = {
    "array_cells",
    "table",
    "matrix",
    "hash_table",
    "linked_list",
    "tree",
    "graph",
    "heap_dual",
    "bar",
}
_STRUCTURAL_VIEWS: set[ViewKind] = {"tree", "linked_list", "graph", "hash_table", "heap_dual"}


class GraphViewBuilder:
    """Compose VisualGraph nodes whose labels embed Graphviz HTML tables."""

    def __init__(
        self,
        max_items: int,
        *,
        value_coercer: Callable[[Any], Any] | None = None,
        view_resolver: Callable[[str, Any, Any], tuple[ViewKind, bool]] | None = None,
    ):
        self.graph = VisualGraph()
        self.max_items = max_items
        self._counter = 0
        self._coerce_value = value_coercer or (lambda x: x)
        self._view_resolver = view_resolver

    def _new_node_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def build(self, value: Any, name: str, view: ViewKind, depth: int) -> str:
        coerced = self._coerce_value(value)
        return self._build_view(coerced, name, view, depth)

    def _build_view(self, value: Any, name: str, view: ViewKind, depth: int) -> str:
        if view == "array_cells":
            return self._build_array(value, name, depth)
        if view == "table":
            return self._build_table(value, name, depth)
        if view == "matrix":
            return self._build_matrix(value, name, depth)
        if view == "hash_table":
            return self._build_hash_table(value, name, depth)
        if view == "linked_list":
            return self._build_linked_list(value, name, depth)
        if view == "tree":
            return self._build_tree(value, name, depth)
        if view == "graph":
            return self._build_graph(value, name, depth)
        if view == "heap_dual":
            return self._build_heap_dual(value, name, depth)
        if view == "bar":
            return self._build_bar(value, name, depth)
        raise ValueError(f"Unsupported nested view: {view}")

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _wrap_label(self, title: str | None, inner_html: str, *, show_title: bool = True) -> str:
        rows: list[str] = []
        if show_title and title:
            safe_title = html_escape(title)
            rows.append(f"<tr><td align='center'><font point-size='16'><b>{safe_title}</b></font></td></tr>")
        rows.append(f"<tr><td>{inner_html}</td></tr>")
        return "<table border='0' cellborder='0' cellspacing='2'>" + "".join(rows) + "</table>"

    def _add_html_node(self, node_id: str, label_html: str) -> None:
        meta = {"html_label": True, "node_attrs": {"shape": "plain"}}
        self.graph.add_node(VisualNode(node_id, "object", label_html, meta))

    def _add_edge(self, src: str, dst: str, *, tailport: str | None = None) -> None:
        meta: dict[str, Any] = {}
        if tailport:
            meta["tailport"] = tailport
        self.graph.add_edge(VisualEdge(src, dst, type="contains", meta=meta))

    def _legacy_nested_view(self, value: Any) -> ViewKind | None:
        if value is None:
            return None
        if _tree_children(value) is not None:
            return "tree"
        if _collect_linked_list_labels(value, min(8, self.max_items)) is not None:
            return "linked_list"
        if isinstance(value, list) and _looks_like_hash_table(value):
            return "hash_table"
        if _try_networkx_edges_nodes(value) is not None or _looks_like_graph_mapping(value):
            return "graph"
        if _is_matrix_value(value):
            return "matrix"
        if isinstance(value, dict):
            return "table"
        if isinstance(value, (list, tuple, set, frozenset)):
            return "array_cells"
        return None

    def _select_nested_view(
        self,
        slot_name: str,
        original_value: Any,
        coerced_value: Any,
        depth_remaining: int,
    ) -> ViewKind | None:
        if depth_remaining <= 0:
            return None

        if self._view_resolver is not None:
            resolved_view, configured = self._view_resolver(slot_name, original_value, coerced_value)
            if configured and resolved_view in _NESTED_HTML_VIEWS:
                return resolved_view
            if resolved_view in _STRUCTURAL_VIEWS:
                return resolved_view

        legacy_view = self._legacy_nested_view(coerced_value)
        if legacy_view in _STRUCTURAL_VIEWS:
            return legacy_view
        return None

    def _make_nested_renderer(self, parent_id: str, port_name: str, slot_name: str):
        def _renderer(child_value: Any, _: str, depth_remaining: int) -> str | None:
            coerced = self._coerce_value(child_value)
            next_view = self._select_nested_view(slot_name, child_value, coerced, depth_remaining)
            if next_view is None:
                return None
            inline_html = self._render_inline_child_view(
                coerced, slot_name, next_view, max(0, depth_remaining)
            )
            if inline_html is not None:
                return inline_html
            child_id = self._build_view(coerced, slot_name, next_view, max(0, depth_remaining))
            self._add_edge(parent_id, child_id, tailport=port_name)
            return "<font color='#2563eb'>&#10549;</font>"

        return _renderer

    def _render_inline_child_view(
        self,
        coerced_value: Any,
        slot_name: str,
        view: ViewKind,
        depth_remaining: int,
    ) -> str | None:
        """
        Try to render the nested view directly inside the parent cell.
        Falls back to None so the caller can spawn a separate node if needed.
        """
        local_builder = self.__class__(
            self.max_items,
            value_coercer=self._coerce_value,
            view_resolver=self._view_resolver,
        )
        try:
            root_id = local_builder.build(coerced_value, slot_name, view, depth_remaining)
        except Exception:
            return None

        root_node = local_builder.graph.nodes.get(root_id)
        if (
            root_node is not None
            and not local_builder.graph.edges
            and len(local_builder.graph.nodes) == 1
            and root_node.meta.get("html_label")
        ):
            return root_node.label

        direction = "TD" if view in {"tree", "hash_table"} else "LR"
        dot_source = render_graphviz_node_link(local_builder.graph, direction=direction)
        img_src = _render_dot_to_image(dot_source, fmt="png")
        if img_src is None:
            return None
        return _image_html(img_src)

    # ------------------------------------------------------------------
    # Array / table primitives
    # ------------------------------------------------------------------

    def _build_array(self, value: Any, name: str, depth: int) -> str:
        if isinstance(value, (set, frozenset)):
            array = sorted(value, key=lambda x: str(x))
        elif isinstance(value, (list, tuple)):
            array = list(value)
        else:
            raise TypeError("array_cells view expects list-like input")

        node_id = self._new_node_id("arr")
        n = len(array)
        limit = min(n, self.max_items)
        depth_budget = max(0, depth)
        cell_depth = depth_budget - 1 if depth_budget > 0 else 0
        value_cells: list[str] = []
        index_cells: list[str] = []
        for i in range(limit):
            port = f"{node_id}_item_{i}"
            nested_renderer = self._make_nested_renderer(node_id, port, f"{name}[{i}]")
            cell_html = _format_nested_value(
                array[i],
                cell_depth,
                self.max_items,
                nested_renderer,
                f"{name}[{i}]",
            )
            value_cells.append(
                f'<td port="{port}" align="center" bgcolor="#ffffff" cellpadding="4">{cell_html}</td>'
            )
            index_cells.append(
                f"<td align='center'><font color='#dc2626' point-size='12'>{html_escape(str(i))}</font></td>"
            )
        if n > self.max_items:
            value_cells.append('<td align="center" bgcolor="#ffffff">…</td>')
            index_cells.append('<td align="center"></td>')
        table_html = _graphviz_array_block(value_cells, index_cells)
        label = self._wrap_label(name, table_html)
        self._add_html_node(node_id, label)
        return node_id

    def _build_table(self, mapping: Any, name: str, depth: int) -> str:
        if not isinstance(mapping, dict):
            raise TypeError("table view expects dict input")
        items = list(mapping.items())
        limit = min(len(items), self.max_items)
        node_id = self._new_node_id("table")
        depth_budget = max(0, depth)
        inner_depth = depth_budget - 1 if depth_budget > 0 else 0
        rows: list[str] = []
        rows.append('<tr><td bgcolor="#e5e7eb"><b>Key</b></td><td bgcolor="#e5e7eb"><b>Value</b></td></tr>')
        for idx in range(limit):
            key, val = items[idx]
            port = f"{node_id}_val_{idx}"
            nested_renderer = self._make_nested_renderer(node_id, port, f"{name}.{key}")
            val_html = _format_nested_value(
                val,
                inner_depth,
                self.max_items,
                nested_renderer,
                f"{name}.{key}",
            )
            rows.append(f"<tr><td>{_table_cell_text(key)}</td><td port='{port}'>{val_html}</td></tr>")
        if len(items) == 0:
            rows.append('<tr><td colspan="2">∅</td></tr>')
        elif len(items) > self.max_items:
            rows.append('<tr><td colspan="2">… (+more)</td></tr>')
        table_html = f"<table border='1' cellborder='1' cellspacing='0'>{''.join(rows)}</table>"
        label = self._wrap_label(name, table_html)
        self._add_html_node(node_id, label)
        return node_id

    def _build_matrix(self, value: Any, name: str, depth: int) -> str:
        if not isinstance(value, (list, tuple)):
            raise TypeError("matrix view expects a list of lists/tuples")
        rows = []
        for row in value:
            if not isinstance(row, (list, tuple)):
                raise TypeError("matrix view expects uniform sublists")
            rows.append(list(row))
        row_count = len(rows)
        node_id = self._new_node_id("matrix")
        depth_budget = max(0, depth)
        cell_depth = depth_budget - 1 if depth_budget > 0 else 0
        row_limit = min(row_count, min(self.max_items, 25))
        width = max((len(r) for r in rows), default=0)
        col_limit = min(width, min(self.max_items, 25))
        body: list[str] = []
        body.append('<table border="1" cellborder="1" cellspacing="0">')
        if row_count == 0:
            body.append("<tr><td>∅</td></tr>")
        else:
            header_cells = ['<td bgcolor="#f3f4f6"></td>']
            for c in range(col_limit):
                header_cells.append(f"<td bgcolor='#f3f4f6'><font color='#dc2626'>{c}</font></td>")
            if width > col_limit:
                header_cells.append('<td bgcolor="#f3f4f6">…</td>')
            body.append(f"<tr>{''.join(header_cells)}</tr>")
            for r_idx in range(row_limit):
                row = rows[r_idx]
                cells: list[str] = [
                    f"<td bgcolor='#fef3c7'><font color='#b45309'>{r_idx}</font></td>"
                ]
                for c_idx in range(col_limit):
                    val = row[c_idx] if c_idx < len(row) else ""
                    port = f"{node_id}_r{r_idx}_c{c_idx}"
                    nested_renderer = self._make_nested_renderer(
                        node_id, port, f"{name}[{r_idx}][{c_idx}]"
                    )
                    cell_html = _format_nested_value(
                        val,
                        cell_depth,
                        self.max_items,
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
        label = self._wrap_label(name, "".join(body))
        self._add_html_node(node_id, label)
        return node_id

    # ------------------------------------------------------------------
    # Specialized views
    # ------------------------------------------------------------------

    def _build_hash_table(self, value: Any, name: str, depth: int) -> str:
        if not isinstance(value, list):
            raise TypeError("hash_table view expects list input")

        root_id = self._new_node_id("hash_root")
        header = "<font color='#94a3b8' point-size='11'>hash_table</font>"
        self._add_html_node(root_id, self._wrap_label(None, header, show_title=False))

        depth_budget = max(0, depth)
        chain_depth = depth_budget - 1 if depth_budget > 0 else 0
        limit = min(len(value), self.max_items)
        bucket_ids: list[str] = []
        bucket_rank_group = f"{root_id}_row"

        for idx in range(limit):
            bucket_id = self._make_hash_bucket_node(idx, bucket_rank_group)
            bucket_ids.append(bucket_id)
            # keep bucket under root without drawing an actual edge
            self.graph.add_edge(
                VisualEdge(
                    root_id,
                    bucket_id,
                    type="contains",
                    meta={"edge_attrs": {"style": "invis"}},
                )
            )
            self._populate_hash_bucket(bucket_id, value[idx], idx, name, chain_depth)

        if len(bucket_ids) > 1:
            for left, right in zip(bucket_ids, bucket_ids[1:]):
                self.graph.add_edge(
                    VisualEdge(
                        left,
                        right,
                        type="layout",
                        meta={"edge_attrs": {"style": "invis"}},
                    )
                )

        if len(value) > limit:
            more_id = self._new_node_id("hash_more")
            self._add_html_node(
                more_id,
                "<font color='#475569'>… (+more buckets)</font>",
            )
            self._add_edge(root_id, more_id)

        return root_id

    def _build_bar(self, value: Any, name: str, depth: int) -> str:
        if not isinstance(value, (list, tuple)):
            raise TypeError("bar view expects list-like numeric input")
        seq = list(value)
        limit = min(len(seq), self.max_items)
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
        node_id = self._new_node_id("bar")
        self._add_html_node(node_id, self._wrap_label(name, chart_html))
        return node_id

    def _make_hash_bucket_node(self, idx: int, rank_group: str) -> str:
        bucket_id = self._new_node_id("hash_bucket")
        label = (
            "<table border='0' cellborder='0' cellspacing='0'>"
            "<tr><td>"
            "<table border='1' cellborder='0' cellspacing='0' cellpadding='6'>"
            "<tr><td><font point-size='12'><b>H</b></font></td></tr>"
            "</table>"
            "</td></tr>"
            f"<tr><td align='center'><font color='#dc2626'>{idx}</font></td></tr>"
            "</table>"
        )
        meta = {"html_label": True, "node_attrs": {"shape": "plain"}, "rank": rank_group}
        self.graph.add_node(VisualNode(bucket_id, "object", label, meta))
        return bucket_id

    def _populate_hash_bucket(
        self,
        bucket_id: str,
        bucket_value: Any,
        idx: int,
        name: str,
        depth_remaining: int,
    ) -> None:
        entries, clipped = _hash_bucket_entries(bucket_value, min(self.max_items, 8))
        prev = bucket_id
        slot_prefix = f"{name}[{idx}]"
        for j, entry in enumerate(entries):
            entry_id = self._make_hash_entry_node(entry, f"{slot_prefix}[{j}]", depth_remaining)
            self.graph.add_edge(
                VisualEdge(
                    prev,
                    entry_id,
                    type="contains",
                    meta={"edge_attrs": {"color": "#1f2933"}},
                )
            )
            prev = entry_id
        if clipped:
            ellipsis_id = self._new_node_id("hash_clip")
            self._add_html_node(ellipsis_id, "<font color='#0f172a'>…</font>")
            self.graph.add_edge(
                VisualEdge(
                    prev,
                    ellipsis_id,
                    type="contains",
                    meta={"edge_attrs": {"color": "#1f2933", "style": "dashed"}},
                )
            )

    def _make_hash_entry_node(self, value: Any, slot_name: str, depth_remaining: int) -> str:
        node_id = self._new_node_id("hash_val")
        label = self._hash_entry_label(value)
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
        self.graph.add_node(VisualNode(node_id, "object", label, meta))
        if depth_remaining >= 0:
            coerced = self._coerce_value(value)
            next_view = self._select_nested_view(slot_name, value, coerced, depth_remaining)
            if next_view is not None:
                child_id = self._build_view(coerced, slot_name, next_view, max(0, depth_remaining))
                self._add_edge(node_id, child_id)
        return node_id

    def _hash_entry_label(self, value: Any) -> str:
        if value is None:
            return "∅"
        if isinstance(value, float):
            display = f"{value:.2f}".rstrip("0").rstrip(".")
        else:
            display = str(value)
        display = display.strip()
        if not display:
            display = type(value).__name__
        if len(display) > 6:
            display = display[:5] + "…"
        return display

    def _build_linked_list(self, head: Any, name: str, depth: int) -> str:
        seq = _collect_linked_list_labels(head, self.max_items)
        if seq is None:
            raise TypeError("linked_list view expects objects with .next")
        values, truncated = seq
        node_id = self._new_node_id("list")
        depth_budget = max(0, depth)
        cell_depth = depth_budget - 1 if depth_budget > 0 else 0
        if not values:
            html = (
                "<table border='1' cellborder='1' cellspacing='0'>"
                "<tr><td align='center'>∅</td></tr>"
                "</table>"
            )
        else:
            cells: list[str] = []
            for idx, val in enumerate(values):
                port = f"{node_id}_node_{idx}"
                nested_renderer = self._make_nested_renderer(
                    node_id, port, f"{name}[{idx}]"
                )
                cell_html = _format_nested_value(
                    val,
                    cell_depth,
                    self.max_items,
                    nested_renderer,
                    f"{name}[{idx}]",
                )
                value_block = (
                    "<table border='1' cellborder='1' cellspacing='0'>"
                    f"<tr><td port='{port}' bgcolor='#ffffff' cellpadding='6'>{cell_html}</td></tr>"
                    "</table>"
                )
                cells.append(f"<td border='0' cellborder='0'>{value_block}</td>")
                cells.append(
                    "<td border='0' cellborder='0' sides='' width='24' align='center'>"
                    "<font color='#94a3b8'>&rarr;</font>"
                    "</td>"
                )
            tail_inner = "<font color='#9ca3af'>∅</font>"
            if truncated:
                tail_inner = "…"
            tail = (
                "<table border='1' cellborder='1' cellspacing='0'>"
                f"<tr><td align='center'>{tail_inner}</td></tr>"
                "</table>"
            )
            cells.append(f"<td border='0' cellborder='0'>{tail}</td>")
            html = (
                "<table border='0' cellborder='0' cellspacing='2'>"
                f"<tr>{''.join(cells)}</tr>"
                "</table>"
            )
        label = self._wrap_label(name, html)
        self._add_html_node(node_id, label)
        return node_id

    def _build_heap_dual(self, value: Any, name: str, depth: int) -> str:
        if not isinstance(value, list):
            raise TypeError("heap_dual view expects list input")
        container_id = self._new_node_id("heap")
        container_label = (
            "<table border='0' cellborder='0' cellspacing='0'>"
            f"<tr><td align='center'><font point-size='16'><b>{html_escape(name)}</b></font></td></tr>"
            "<tr><td align='center'><font color='#64748b' point-size='11'>heap_dual</font></td></tr>"
            "</table>"
        )
        self._add_html_node(container_id, container_label)

        array_id = self._build_array(value, f"{name}[array]", depth)
        self._add_edge(container_id, array_id)

        tree_payload = self._heap_tree_payload(value)
        if tree_payload is not None:
            tree_id = self._build_tree(tree_payload, f"{name}[tree]", depth)
            self._add_edge(container_id, tree_id)
        else:
            empty_id = self._new_node_id("heap_empty")
            empty_html = (
                "<table border='1' cellborder='1' cellspacing='0'>"
                "<tr><td align='center'>∅</td></tr>"
                "</table>"
            )
            self._add_html_node(empty_id, self._wrap_label(f"{name}[tree]", empty_html))
            self._add_edge(container_id, empty_id)

        return container_id

    def _heap_tree_payload(self, heap: list[Any]) -> Any | None:
        if not heap:
            return None
        limit = min(len(heap), self.max_items)

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

    # ------------------------------------------------------------------
    # Graph / tree adapters
    # ------------------------------------------------------------------

    def _merge_visual_graph(self, other: VisualGraph, prefix: str, root_hint: str | None = None) -> str:
        mapping: dict[str, str] = {}
        for node_id, node in other.nodes.items():
            new_id = f"{prefix}__{node_id}"
            mapping[node_id] = new_id
            self.graph.add_node(VisualNode(new_id, node.type, node.label, dict(node.meta)))
        for edge in other.edges:
            self.graph.add_edge(
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

    def _build_tree(self, value: Any, name: str, depth: int) -> str:
        tg = build_rooted_tree_graph(
            value,
            name=name,
            max_nodes=self.max_items,
            nested_depth=depth,
            max_items=self.max_items,
        )
        prefix = self._new_node_id("tree")
        return self._merge_visual_graph(tg, prefix, root_hint="ROOT")

    def _build_graph(self, value: Any, name: str, depth: int) -> str:
        graph_data = self._extract_graph_data(value)
        if graph_data is None:
            raise TypeError("graph view expects a networkx graph or mapping with nodes/edges")
        nodes, edges, directed = graph_data
        depth_budget = max(0, depth)
        node_label_depth = depth_budget - 1 if depth_budget > 0 else 0
        limit = min(len(nodes), self.max_items)
        truncated = len(nodes) > limit

        g = VisualGraph()
        container_id = self._new_node_id("graph_root")
        g.add_node(
            VisualNode(
                container_id,
                "object",
                "",
                {
                    "kind": "graph_root",
                    "node_attrs": {"shape": "point", "style": "invis", "width": "0", "height": "0"},
                },
            )
        )

        id_map: dict[Any, str] = {}
        for idx, (key, payload) in enumerate(nodes[:limit]):
            label_text, is_html = _format_value_label(
                payload,
                node_label_depth,
                self.max_items,
                None,
                f"{name}.nodes[{idx}]",
            )
            meta: dict[str, Any] = {"kind": "graph_node"}
            if is_html:
                meta["html_label"] = True
                meta["node_attrs"] = {"shape": "plain"}
            local_id = f"{container_id}_n{idx}"
            g.add_node(VisualNode(local_id, "object", label_text, meta))
            id_map[key] = local_id

        edge_limit = min(len(edges), self.max_items * 2)
        for src_key, dst_key, label in edges[:edge_limit]:
            sid = id_map.get(src_key)
            did = id_map.get(dst_key)
            if sid is None or did is None:
                continue
            edge_meta: dict[str, Any] = {}
            if not directed:
                edge_meta["edge_attrs"] = {"dir": "none"}
            g.add_edge(VisualEdge(sid, did, type="link", label=label, meta=edge_meta))

        prefix = self._new_node_id("graph")
        return self._merge_visual_graph(g, prefix, root_hint=container_id)

    def _extract_graph_data(
        self, value: Any
    ) -> tuple[list[tuple[Any, Any]], list[tuple[Any, Any, Any]], bool] | None:
        nk = _try_networkx_edges_nodes(value)
        if nk is not None:
            nodes, edges, directed = nk
            normalized_nodes: list[tuple[Any, Any]] = []
            for node_key, attrs in nodes:
                payload = (
                    attrs.get("value")
                    or attrs.get("label")
                    or attrs.get("data")
                    or (attrs if attrs else node_key)
                )
                normalized_nodes.append((node_key, payload))
            normalized_edges = [
                (u, v, self._edge_label_from_attrs(attrs)) for (u, v, attrs) in edges
            ]
            return normalized_nodes, normalized_edges, directed
        if _looks_like_graph_mapping(value):
            return self._graph_data_from_mapping(value)
        return None

    def _edge_label_from_attrs(self, attrs: Mapping[str, Any]) -> Any:
        for key in ("label", "value", "weight", "text"):
            if key in attrs and attrs[key] is not None:
                return attrs[key]
        return None

    def _graph_data_from_mapping(
        self, value: Any
    ) -> tuple[list[tuple[Any, Any]], list[tuple[Any, Any, Any]], bool] | None:
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
                key, payload = self._normalize_graph_node_entry(entry)
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
                label = (
                    entry.get("label")
                    or entry.get("value")
                    or entry.get("weight")
                    or entry.get("text")
                )
                edges.append((src, dst, label))
                for key in (src, dst):
                    if key not in seen_keys:
                        seen_keys[key] = key
                        entries.append((key, key))
            elif isinstance(entry, (tuple, list)) and len(entry) >= 2:
                src, dst = entry[0], entry[1]
                label = entry[2] if len(entry) > 2 else None
                edges.append((src, dst, label))
                for key in (src, dst):
                    if key not in seen_keys:
                        seen_keys[key] = key
                        entries.append((key, key))

        if not entries and not edges:
            return None
        if not entries:
            seen: dict[Any, Any] = {}
            for src, dst, _ in edges:
                if src not in seen:
                    seen[src] = src
                    entries.append((src, src))
                if dst not in seen:
                    seen[dst] = dst
                    entries.append((dst, dst))
        return entries, edges, directed

    def _normalize_graph_node_entry(self, entry: Any) -> tuple[Any, Any]:
        if isinstance(entry, Mapping):
            key = (
                entry.get("id")
                or entry.get("key")
                or entry.get("name")
                or entry.get("label")
            )
            payload = entry.get("value")
            if payload is None:
                payload = entry.get("label") or entry.get("data")
            if key is None:
                key = id(entry)
            if payload is None:
                payload = key
            return key, payload
        return entry, entry
