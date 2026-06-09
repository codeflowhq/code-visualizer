from __future__ import annotations

from itertools import count

import pytest

from code_visualizer.shared.models import VisualGraph
from code_visualizer.shared.view_kinds import ViewKind
from code_visualizer.views.composite_view import (
    experimental_array_nested_resolver,
    legacy_nested_view,
    select_nested_view,
)
from code_visualizer.views.context import ViewBuildContext
from code_visualizer.views.dispatcher import build_graph_view


class _TreeNode:
    def __init__(self, value: int, children: list[_TreeNode] | None = None) -> None:
        self.value = value
        self.children = children or []


def _runtime(*, resolver=None) -> ViewBuildContext:
    return ViewBuildContext(
        graph=VisualGraph(),
        item_limit=5,
        coerce=lambda value: value,
        resolver=resolver,
        focus_path=None,
        accent_color=None,
        counter=count(1),
        show_titles=False,
    )


def test_bar_view_builds_empty_and_truncated_graph() -> None:
    root_id, empty_graph = build_graph_view([], "data", ViewKind.BAR, 2, item_limit=2)
    assert root_id == "bar_exp_1"
    assert "bar_empty_data" in empty_graph.nodes

    _, graph = build_graph_view([7, -3, 5], "data", ViewKind.BAR, 2, item_limit=2)
    assert "bar_item_data_7_0" in graph.nodes
    assert "bar_item_data_3_0" in graph.nodes
    assert "bar_more_data" in graph.nodes


def test_bar_view_rejects_non_numeric_entries() -> None:
    with pytest.raises(TypeError):
        build_graph_view([1, True], "data", ViewKind.BAR, 2, item_limit=5)
    with pytest.raises(TypeError):
        build_graph_view({"a": 1}, "data", ViewKind.BAR, 2, item_limit=5)


def test_legacy_nested_view_prefers_expected_structures() -> None:
    runtime = _runtime()

    assert legacy_nested_view(runtime, {"score": 1}) is ViewKind.TABLE
    assert legacy_nested_view(runtime, [[1, 2], [3, 4]]) is ViewKind.MATRIX
    assert legacy_nested_view(runtime, [1, 2, 3]) is ViewKind.ARRAY_CELLS
    assert legacy_nested_view(runtime, "data:image/png;base64,AAAA") is ViewKind.IMAGE
    assert legacy_nested_view(runtime, _TreeNode(1, [_TreeNode(2)])) is ViewKind.TREE


def test_select_nested_view_honors_configured_and_fallback_resolution() -> None:
    runtime = _runtime(resolver=lambda name, original, coerced: (ViewKind.TABLE, True))
    assert select_nested_view(runtime, "data", {"a": 1}, {"a": 1}, 2) is ViewKind.TABLE
    assert select_nested_view(runtime, "data", {"a": 1}, {"a": 1}, 0) is None

    fallback_runtime = _runtime(resolver=None)
    assert (
        select_nested_view(fallback_runtime, "data", [1, 2], [1, 2], 2)
        is ViewKind.ARRAY_CELLS
    )
    assert select_nested_view(fallback_runtime, "data", {"a": 1}, {"a": 1}, 2) is None


def test_experimental_array_nested_resolver_promotes_plain_lists_to_node_view() -> None:
    runtime = _runtime()
    resolver = experimental_array_nested_resolver(runtime, None)

    assert resolver("data", [1, 2, 3], [1, 2, 3]) == (ViewKind.ARRAY_CELLS, False)
    assert resolver("data", {"a": 1}, {"a": 1}) == (ViewKind.NODE_LINK, False)


def test_bar_view_uses_accent_color() -> None:
    root_id, graph = build_graph_view(
        [7, 3],
        "data",
        ViewKind.BAR,
        2,
        item_limit=5,
        accent_color="#9333ea",
    )
    assert root_id == "bar_exp_1"
    bar_node = graph.nodes["bar_item_data_7_0"]
    assert bar_node.meta["node_attrs"]["color"] == "#9333ea"
    assert "#9333ea" in bar_node.label


def test_array_and_table_views_use_accent_color() -> None:
    _, array_graph = build_graph_view(
        [7, 3],
        "data",
        ViewKind.ARRAY_CELLS,
        2,
        item_limit=5,
        accent_color="#16a34a",
    )
    array_node = array_graph.nodes["arr_item_data_7_0"]
    assert array_node.meta["node_attrs"]["color"] == "#62b889"

    _, table_graph = build_graph_view(
        {"score": 1},
        "data",
        ViewKind.TABLE,
        2,
        item_limit=5,
        accent_color="#f97316",
    )
    header_node = table_graph.nodes["table_header_data"]
    assert header_node.meta["node_attrs"]["color"] == "#e89863"


def test_matrix_view_uses_accent_color() -> None:
    _, graph = build_graph_view(
        [[7, 3]],
        "data",
        ViewKind.MATRIX,
        2,
        item_limit=5,
        accent_color="#2563eb",
    )
    column_node = graph.nodes["matrix_col_data_0"]
    assert column_node.meta["node_attrs"]["color"] == "#749bed"
