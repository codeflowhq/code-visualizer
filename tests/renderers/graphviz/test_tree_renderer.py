from dataclasses import dataclass

from code_visualizer.renderers.graphviz.tree_renderer import build_tree


@dataclass
class Node:
    val: int
    left: "Node | None" = None
    right: "Node | None" = None


def test_build_tree_returns_root_and_graph() -> None:
    root = Node(1, left=Node(2), right=Node(3))

    root_id, graph = build_tree(root)

    assert root_id in graph.nodes
    assert len(graph.edges) == 2


def test_build_tree_uses_subtree_structure_for_stable_ids() -> None:
    before = {
        "label": "A",
        "children": [
            {"label": "B", "children": []},
            {"label": "C", "children": [{"label": "D", "children": []}]},
        ],
    }
    after = {
        "label": "B",
        "children": [
            {"label": "B", "children": []},
            {"label": "A", "children": [{"label": "D", "children": []}]},
        ],
    }

    before_root, before_graph = build_tree(before)
    after_root, after_graph = build_tree(after)

    assert before_root != after_root
    shared_ids = (set(before_graph.nodes) & set(after_graph.nodes)) - {"CUT"}
    assert shared_ids


def test_build_tree_preserves_binary_left_right_order_in_ids() -> None:
    left_first = Node(8, left=Node(3), right=Node(10))
    right_first = Node(8, left=Node(10), right=Node(3))

    left_root, left_graph = build_tree(left_first)
    right_root, right_graph = build_tree(right_first)

    assert left_root != right_root
    assert set(left_graph.nodes) != set(right_graph.nodes)


def test_build_tree_requests_outgoing_edge_order_for_layout() -> None:
    root = Node(8, left=Node(3), right=Node(10))

    _root_id, graph = build_tree(root)

    assert graph.graph_attrs["ordering"] == "out"
