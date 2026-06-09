from __future__ import annotations

from itertools import count

from code_visualizer.shared.models import NodeKind, VisualGraph, VisualNode
from code_visualizer.views.context import ViewBuildContext
from code_visualizer.views.graph_layout import (
    add_edge,
    add_html_node,
    attach_view_title,
    flatten_nested_preview_frame,
    matrix_focus_coords,
    merge_visual_graph,
    new_node_id,
    render_nested_preview,
    safe_dot_token,
    soften_nested_preview_wrapper,
    wrap_label,
)


def _runtime(show_titles: bool = True) -> ViewBuildContext:
    return ViewBuildContext(
        graph=VisualGraph(),
        item_limit=5,
        coerce=lambda value: value,
        resolver=None,
        focus_path=None,
        accent_color=None,
        counter=count(1),
        show_titles=show_titles,
    )


def test_basic_common_helpers() -> None:
    runtime = _runtime()
    assert new_node_id(runtime, "x") == "x_1"
    assert safe_dot_token("a b", "c-d") == "a_b_c_d"
    assert matrix_focus_coords("data[1][2]") == (1, 2)
    assert matrix_focus_coords("data") is None


def test_preview_helpers_and_title_attachment() -> None:
    html = "<table border='1'><tr><td>x</td></tr></table>"
    softened = soften_nested_preview_wrapper(html)
    flattened = flatten_nested_preview_frame(
        "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'><tr><td align='center' bgcolor='#eef2ff' cellpadding='1'><table border='1' cellborder='1' cellspacing='0' cellpadding='0'><tr><td align='center' bgcolor='#ffffff' cellpadding='1'>x</td></tr></table></td></tr></table>"
    )
    assert "border='0' cellborder='0'" in softened
    assert "cellpadding='0'" in flattened

    preview = render_nested_preview({"a": 1}, 1, 5, "data")
    assert "bgcolor='#eef2ff'" in preview

    attach_view_title(_runtime(), "ignored", "data", "table")
    runtime = _runtime()
    attach_view_title(runtime, "ignored", "data", "table")
    assert "data" in runtime.graph.graph_attrs["label"]
    no_title = _runtime(show_titles=False)
    attach_view_title(no_title, "ignored", "data", "table")
    assert "label" not in no_title.graph.graph_attrs


def test_merge_visual_graph_and_add_helpers() -> None:
    runtime = _runtime()
    other = VisualGraph()
    other.add_node(VisualNode("ROOT", NodeKind.OBJECT, "root", {}))
    other.add_node(VisualNode("child", NodeKind.SCALAR, "1", {}))
    merged_root = merge_visual_graph(runtime, other, "pref", root_hint="ROOT")
    assert merged_root == "pref__ROOT"
    assert "pref__child" in runtime.graph.nodes

    add_html_node(runtime, "html", "<b>x</b>")
    add_edge(
        runtime, "pref__ROOT", "html", tailport="p0", edge_meta={"style": "dashed"}
    )
    edge = runtime.graph.edges[-1]
    assert edge.meta["tailport"] == "p0"
    assert edge.meta["edge_attrs"]["style"] == "dashed"

    wrapped = wrap_label("title", "<b>x</b>")
    assert "title" in wrapped
