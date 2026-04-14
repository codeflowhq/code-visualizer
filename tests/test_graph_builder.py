from code_visualizer.graph_builder import _canonicalize_outer_view
from code_visualizer.view_types import ViewKind


def test_canonicalize_outer_view_uses_node_variants() -> None:
    assert _canonicalize_outer_view(ViewKind.ARRAY_CELLS) is ViewKind.ARRAY_CELLS_NODE
    assert _canonicalize_outer_view(ViewKind.MATRIX) is ViewKind.MATRIX_NODE
    assert _canonicalize_outer_view(ViewKind.TABLE) is ViewKind.TABLE_NODE
    assert _canonicalize_outer_view(ViewKind.HASH_TABLE) is ViewKind.HASH_TABLE_NODE
    assert _canonicalize_outer_view(ViewKind.LINKED_LIST) is ViewKind.LINKED_LIST_NODE
    assert _canonicalize_outer_view(ViewKind.HEAP_DUAL) is ViewKind.HEAP_DUAL_NODE
    assert _canonicalize_outer_view(ViewKind.BAR) is ViewKind.BAR_NODE


def test_canonicalize_outer_view_keeps_non_mapped_views() -> None:
    assert _canonicalize_outer_view(ViewKind.TREE) is ViewKind.TREE
    assert _canonicalize_outer_view(ViewKind.GRAPH) is ViewKind.GRAPH
