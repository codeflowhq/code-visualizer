from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Literal
from .models import Anchor, AnchorKind, EdgeKind, NodeKind, VisualEdge, VisualGraph, VisualNode

@dataclass
class ExtractOptions:
    max_depth: int = 4
    max_items: int = 30
    include_object_attrs: bool = True
    max_str_len: int = 80

    string_style: Literal["pretty", "repr"] = "pretty"
    show_index_in_node: bool = False          # default: do NOT show "[0] = ..."
    show_index_on_edge: bool = True           # default: show index as edge label
    dict_style: Literal["entry_node", "kv_edges"] = "entry_node"

    max_table_rows: int = 30
    max_table_cols: int = 12

class VisualIRExtractor:
    def __init__(
        self,
        opts: ExtractOptions | None = None,
        value_coercer: Callable[[Any], Any] | None = None,
    ) -> None:
        self.opts = opts or ExtractOptions()
        self._obj_to_node: dict[int, str] = {}   # id(obj) -> node_id
        self._counter: int = 0
        self._coerce_value = value_coercer

    def extract(self, value: Any, name: str | None = None) -> VisualGraph:
        g = VisualGraph()
        root_id = self._visit(value, g, depth=0, hint=name)
        if name is not None:
            g.anchors.append(Anchor(name=name, node_id=root_id, kind=AnchorKind.VAR))
        return g

    def _new_id(self, prefix: str = "n") -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"

    def _short_str(self, s: str) -> str:
        if len(s) <= self.opts.max_str_len:
            return s
        return s[: self.opts.max_str_len - 3] + "..."

    def _is_scalar(self, v: Any) -> bool:
        return v is None or isinstance(v, (bool, int, float, str))

    # def _scalar_label(self, v: Any) -> str:
    #     if isinstance(v, str):
    #         return f'"{self._short_str(v)}"'
    #     return repr(v)

    def _pretty_str(self, s: str) -> str:
        # pretty display: no quotes, show newline explicitly, keep it small
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = s.replace("\n", "⏎")
        s = self._short_str(s)
        return s

    def _scalar_label(self, v: Any) -> str:
        if isinstance(v, str):
            if self.opts.string_style == "repr":
                return repr(self._short_str(v))
            return self._pretty_str(v)
        return repr(v)

    def _visit(self, v: Any, g: VisualGraph, depth: int, hint: str | None = None) -> str:
        if self._coerce_value is not None:
            v = self._coerce_value(v)
        # Depth cutoff
        if depth > self.opts.max_depth:
            nid = self._new_id("e")
            g.add_node(VisualNode(nid, NodeKind.ELLIPSIS, "… (max depth)", {"depth": depth}))
            return nid

        # Scalars are safe to duplicate (no need to dedup by id)
        if self._is_scalar(v):
            nid = self._new_id("s")
            label = self._scalar_label(v)
            if hint:
                label = f"{hint}={label}"
            g.add_node(VisualNode(nid, NodeKind.SCALAR, label, {"py_type": type(v).__name__}))
            return nid

        # Dedup for non-scalars to handle shared refs / cycles
        oid = id(v)
        if oid in self._obj_to_node:
            return self._obj_to_node[oid]

        # --- NetworkX graph support ---
        try:
            import networkx as nx
        except ImportError:
            nx = None

        if nx and isinstance(v, nx.Graph):
            nid = self._new_id("G")
            self._obj_to_node[id(v)] = nid

            label = f"{hint}: Graph(|V|={v.number_of_nodes()}, |E|={v.number_of_edges()})" if hint \
                    else f"Graph(|V|={v.number_of_nodes()}, |E|={v.number_of_edges()})"
            g.add_node(VisualNode(nid, NodeKind.OBJECT, label, {"graph": "networkx"}))

            # 1. create node objects
            node_map: dict[Any, str] = {}
            for u in v.nodes():
                uid = self._new_id("v")
                node_map[u] = uid
                g.add_node(VisualNode(uid, NodeKind.SCALAR, str(u), {"graph_node": True}))
                g.add_edge(VisualEdge(nid, uid, type=EdgeKind.CONTAINS, label="node"))

            # 2. create edges
            for u, w in v.edges():
                g.add_edge(VisualEdge(
                    src=node_map[u],
                    dst=node_map[w],
                    type=EdgeKind.REF,
                    label="edge"
                ))

            return nid

        # Containers / objects
        if isinstance(v, list):
            nid = self._new_id("l")
            self._obj_to_node[oid] = nid
            label = f"{hint}: list(len={len(v)})" if hint else f"list(len={len(v)})"
            g.add_node(VisualNode(nid, NodeKind.LIST, label, {"len": len(v)}))

            self._visit_sequence(v, g, nid, depth, kind="list")
            return nid

        if isinstance(v, tuple):
            nid = self._new_id("t")
            self._obj_to_node[oid] = nid
            label = f"{hint}: tuple(len={len(v)})" if hint else f"tuple(len={len(v)})"
            g.add_node(VisualNode(nid, NodeKind.TUPLE, label, {"len": len(v)}))

            self._visit_sequence(v, g, nid, depth, kind="tuple")
            return nid

        if isinstance(v, dict):
            nid = self._new_id("d")
            self._obj_to_node[oid] = nid
            label = f"{hint}: dict(len={len(v)})" if hint else f"dict(len={len(v)})"
            g.add_node(VisualNode(nid, NodeKind.DICT, label, {"len": len(v)}))

            self._visit_dict(v, g, nid, depth)
            return nid

        if isinstance(v, (set, frozenset)):
            nid = self._new_id("S")
            self._obj_to_node[oid] = nid
            label = f"{hint}: set(len={len(v)})" if hint else f"set(len={len(v)})"
            g.add_node(VisualNode(nid, NodeKind.SET, label, {"len": len(v)}))

            self._visit_set(v, g, nid, depth)
            return nid

        # Generic object (optional)
        nid = self._new_id("o")
        self._obj_to_node[oid] = nid
        cls = type(v).__name__
        label = f"{hint}: {cls}" if hint else cls
        g.add_node(VisualNode(nid, NodeKind.OBJECT, label, {"py_type": cls}))

        if self.opts.include_object_attrs and hasattr(v, "__dict__") and isinstance(v.__dict__, dict):
            items = list(v.__dict__.items())
            for i, (k, val) in enumerate(items[: self.opts.max_items_per_view]):
                child_id = self._visit(val, g, depth + 1, hint=k)
                g.add_edge(VisualEdge(nid, child_id, type=EdgeKind.ATTR, label=k))
            if len(items) > self.opts.max_items_per_view:
                more = len(items) - self.opts.max_items_per_view
                eid = self._new_id("e")
                g.add_node(VisualNode(eid, NodeKind.ELLIPSIS, f"… (+{more} attrs)", {"more": more}))
                g.add_edge(VisualEdge(nid, eid, type=EdgeKind.ATTR, label="more"))

        return nid

    def _visit_sequence(self, seq: Any, g: VisualGraph, parent_id: str, depth: int, kind: str) -> None:
        n = len(seq)
        if n == 0:
            eid = self._new_id("e")
            g.add_node(VisualNode(eid, NodeKind.ELLIPSIS, "∅ (empty)", {"empty": True}))
            g.add_edge(VisualEdge(parent_id, eid, type=EdgeKind.CONTAINS, label="empty"))
            return

        limit = min(n, self.opts.max_items_per_view)
        for i in range(limit):
            # Important: omit the hint so scalar children remain "5" instead of "[4]=5".
            child_id = self._visit(seq[i], g, depth + 1, hint=None)
            g.add_edge(VisualEdge(parent_id, child_id, type=EdgeKind.INDEX, label=str(i)))

        if n > self.opts.max_items_per_view:
            more = n - self.opts.max_items_per_view
            eid = self._new_id("e")
            g.add_node(VisualNode(eid, NodeKind.ELLIPSIS, f"… (+{more} items)", {"more": more}))
            g.add_edge(VisualEdge(parent_id, eid, type=EdgeKind.CONTAINS, label="more"))


    def _visit_dict(self, d: dict[Any, Any], g: VisualGraph, parent_id: str, depth: int) -> None:
        if len(d) == 0:
            eid = self._new_id("e")
            g.add_node(VisualNode(eid, NodeKind.ELLIPSIS, "∅ (empty)", {"empty": True}))
            g.add_edge(VisualEdge(parent_id, eid, type=EdgeKind.CONTAINS, label="empty"))
            return

        items = list(d.items())
        limit = min(len(items), self.opts.max_items_per_view)

        for i in range(limit):
            k, val = items[i]
            entry_id = self._new_id("E")
            g.add_node(VisualNode(entry_id, NodeKind.ENTRY, f"entry[{i}]", {"index": i}))
            g.add_edge(VisualEdge(parent_id, entry_id, type=EdgeKind.CONTAINS, label=str(i)))

            key_id = self._visit(k, g, depth + 1, hint=None)
            val_id = self._visit(val, g, depth + 1, hint=None)

            g.add_edge(VisualEdge(entry_id, key_id, type=EdgeKind.KEY, label="key"))
            g.add_edge(VisualEdge(entry_id, val_id, type=EdgeKind.VALUE, label="val"))

        if len(items) > self.opts.max_items_per_view:
            more = len(items) - self.opts.max_items_per_view
            eid = self._new_id("e")
            g.add_node(VisualNode(eid, NodeKind.ELLIPSIS, f"… (+{more} entries)", {"more": more}))
            g.add_edge(VisualEdge(parent_id, eid, type=EdgeKind.CONTAINS, label="more"))

    def _visit_set(self, s: set[Any] | frozenset[Any], g: VisualGraph, parent_id: str, depth: int) -> None:
        if len(s) == 0:
            eid = self._new_id("e")
            g.add_node(VisualNode(eid, NodeKind.ELLIPSIS, "∅ (empty)", {"empty": True}))
            g.add_edge(VisualEdge(parent_id, eid, type=EdgeKind.CONTAINS, label="empty"))
            return

        items = list(s)
        limit = min(len(items), self.opts.max_items_per_view)
        for i in range(limit):
            child_id = self._visit(items[i], g, depth + 1, hint=None)
            g.add_edge(VisualEdge(parent_id, child_id, type=EdgeKind.CONTAINS, label=None))
