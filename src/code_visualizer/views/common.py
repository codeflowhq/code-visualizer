from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from html import escape as html_escape
from typing import Any

from ..models import EdgeKind, NodeKind, VisualEdge, VisualGraph, VisualNode
from ..view_utils import _format_container_stub, _format_nested_value

BuilderRuntime = dict[str, Any]
ViewResolver = Callable[[str, Any, Any], tuple[Any, bool]]


def new_node_id(runtime: BuilderRuntime, prefix: str) -> str:
    counter: Iterator[int] = runtime["counter"]
    return f"{prefix}_{next(counter)}"


def safe_dot_token(*parts: Any) -> str:
    tokens: list[str] = []
    for part in parts:
        token = re.sub(r"[^0-9A-Za-z_]+", "_", str(part)).strip("_")
        tokens.append(token or "x")
    return "_".join(tokens)


def matrix_focus_coords(focus_path: str | None) -> tuple[int, int] | None:
    if not focus_path:
        return None
    normalized = focus_path.split(" [step ", 1)[0].strip()
    coords = re.findall(r"\[(\d+)\]", normalized)
    if len(coords) < 2:
        return None
    return int(coords[-2]), int(coords[-1])


def soften_nested_preview_wrapper(html_label: str) -> str:
    stripped = html_label.strip()
    if not stripped.startswith("<table"):
        return html_label

    open_match = re.match(r"^<table\b[^>]*>", stripped)
    if not open_match:
        return html_label

    softened_open = "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
    return softened_open + stripped[open_match.end():]


def render_nested_preview(value: Any, depth_remaining: int, max_items: int, slot_name: str) -> str:
    preview_html = _format_nested_value(value, depth_remaining, max_items, None, slot_name)
    if not preview_html:
        preview_html = _format_container_stub(value)
    return (
        "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
        "<tr><td align='center' bgcolor='#eef2ff' cellpadding='1'>"
        "<table border='1' cellborder='1' cellspacing='0' cellpadding='0'>"
        f"<tr><td align='center' bgcolor='#ffffff' cellpadding='1'>{preview_html}</td></tr>"
        "</table>"
        "</td></tr>"
        "</table>"
    )


def flatten_nested_preview_frame(html_label: str) -> str:
    softened = soften_nested_preview_wrapper(html_label)
    softened = re.sub(
        r"^<table\b[^>]*>",
        "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>",
        softened.strip(),
        count=1,
    )
    softened = softened.replace(
        "<table border='1' cellborder='1' cellspacing='0' cellpadding='0'>",
        "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>",
        1,
    )
    softened = softened.replace("bgcolor='#eef2ff' cellpadding='1'", "bgcolor='#eef2ff' cellpadding='0'", 1)
    softened = softened.replace("bgcolor='#ffffff' cellpadding='1'", "bgcolor='#ffffff' cellpadding='0'", 1)
    return softened


def merge_visual_graph(runtime: BuilderRuntime, other: VisualGraph, prefix: str, root_hint: str | None = None) -> str:
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


def attach_view_title(runtime: BuilderRuntime, _: str, name: str, __: str) -> None:
    if not runtime.get("show_titles", True) or not name:
        return
    runtime_graph: VisualGraph = runtime["graph"]
    runtime_graph.graph_attrs["label"] = f"<<font point-size='16' color='#0f172a'><b>{html_escape(name)}</b></font>>"
    runtime_graph.graph_attrs.setdefault("labelloc", "t")
    runtime_graph.graph_attrs.setdefault("labeljust", "c")
    runtime_graph.graph_attrs.setdefault("fontname", "Helvetica")
    runtime_graph.graph_attrs.setdefault("fontsize", "16")
    runtime_graph.graph_attrs.setdefault("fontcolor", "#0f172a")


def wrap_label(title: str | None, inner_html: str, *, show_title: bool = True) -> str:
    rows: list[str] = []
    if show_title and title:
        rows.append(
            "<tr><td align='center'><font point-size='16'><b>"
            + html_escape(title)
            + "</b></font></td></tr>"
        )
    rows.append(f"<tr><td>{inner_html}</td></tr>")
    return "<table border='0' cellborder='0' cellspacing='2'>" + "".join(rows) + "</table>"


def add_html_node(
    runtime: BuilderRuntime,
    node_id: str,
    label_html: str,
    meta: dict[str, Any] | None = None,
) -> None:
    merged_meta: dict[str, Any] = {"html_label": True, "node_attrs": {"shape": "plain"}}
    if meta:
        merged_meta.update(meta)
    runtime["graph"].add_node(VisualNode(node_id, NodeKind.OBJECT, label_html, merged_meta))


def add_edge(
    runtime: BuilderRuntime,
    src: str,
    dst: str,
    *,
    tailport: str | None = None,
    edge_meta: dict[str, Any] | None = None,
) -> None:
    meta: dict[str, Any] = {}
    if tailport:
        meta["tailport"] = tailport
    if edge_meta:
        meta["edge_attrs"] = dict(edge_meta)
    runtime["graph"].add_edge(VisualEdge(src, dst, type=EdgeKind.CONTAINS, meta=meta))
