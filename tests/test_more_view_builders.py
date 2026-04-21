from code_visualizer.graph_view_builder import build_graph_view
from code_visualizer.view_types import ViewKind


class LinkedNode:
    def __init__(self, val: int, next_node: "LinkedNode | None" = None) -> None:
        self.val = val
        self.next = next_node


def test_hash_table_node_builder_creates_bucket_heads_and_chain_nodes() -> None:
    value = [[1, 2], [], [{"id": 1, "value": "a"}]]
    root_id, graph = build_graph_view(value, "data", ViewKind.HASH_TABLE_NODE, 2, item_limit=10)

    assert root_id == "hash_exp_1"
    assert "hash_bucket_node_data_0" in graph.nodes
    assert "hash_bucket_node_data_1" in graph.nodes
    assert "hash_bucket_node_data_2" in graph.nodes
    assert "hash_chain_node_data_0_0" in graph.nodes
    assert "hash_chain_node_data_0_1" in graph.nodes
    assert any(edge.dst == "hash_chain_node_data_0_0" for edge in graph.edges)



def test_linked_list_node_builder_creates_nodes_and_tail() -> None:
    head = LinkedNode(1, LinkedNode(2, LinkedNode(3)))
    root_id, graph = build_graph_view(head, "linked", ViewKind.LINKED_LIST_NODE, 2, item_limit=10)

    assert root_id == "linked_exp_1"
    assert any(node_id.startswith("linked_item_linked_1") for node_id in graph.nodes)
    assert any(node_id.startswith("linked_item_linked_2") for node_id in graph.nodes)
    assert any(node_id.startswith("linked_item_linked_3") for node_id in graph.nodes)
    assert "linked_tail_linked" in graph.nodes



def test_heap_dual_node_builder_creates_array_and_tree_sections() -> None:
    root_id, graph = build_graph_view([9, 7, 5, 3], "heap", ViewKind.HEAP_DUAL_NODE, 2, item_limit=10)

    assert root_id == "heap_exp_1"
    assert any(node_id.startswith("heap_arr_") for node_id in graph.nodes)
    assert any("heap_item_heap_array_9_0" == node_id for node_id in graph.nodes)
    assert any(edge.src == root_id for edge in graph.edges)



def test_graph_view_builder_creates_root_and_node_entries() -> None:
    payload = {
        "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        "edges": [{"source": "A", "target": "B", "label": "ab"}],
        "directed": True,
    }
    root_id, graph = build_graph_view(payload, "graph_demo", ViewKind.GRAPH, 2, item_limit=10)

    assert root_id.startswith("graph_")
    assert graph.nodes[root_id].meta.get("kind") == "graph_root"
    assert any(edge.label == "ab" for edge in graph.edges)



def test_image_view_builder_creates_html_image_node() -> None:
    png_data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0l8AAAAASUVORK5CYII="
    root_id, graph = build_graph_view(png_data_url, "img", ViewKind.IMAGE, 1, item_limit=10)

    assert root_id.startswith("image_")
    assert root_id in graph.nodes
    assert "IMG SRC=" in graph.nodes[root_id].label


def test_remote_image_url_without_extension_uses_content_type(monkeypatch) -> None:
    from code_visualizer.utils import image_sources

    class Response:
        headers = {"Content-Type": "image/jpeg"}

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"fake-jpeg"

    monkeypatch.setattr(image_sources, "urlopen", lambda *_args, **_kwargs: Response())

    src = image_sources._detect_image_source("https://example.com/photo?w=1024&h=1024", strict=True)

    assert src is not None
    assert src.endswith(".jpg")


def test_nested_table_header_uses_widest_value_width() -> None:
    import re

    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": 2, "tags": ["c", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE_NODE, 3, item_limit=10)

    header = graph.nodes["table_header_data"].label
    users = graph.nodes["table_row_data_users"].label
    meta = graph.nodes["table_row_data_meta"].label

    header_widths = re.findall(r"width='(\d+)'", header)
    header_value_width = header_widths[-1] if header_widths else None
    users_value_width = re.search(r"width='(\d+)' port='table_row_data_users_value'", users)
    meta_value_width = re.search(r"width='(\d+)' port='table_row_data_meta_value'", meta)

    assert header_value_width is not None
    assert users_value_width is not None
    assert meta_value_width is not None
    assert header_value_width == users_value_width.group(1) == meta_value_width.group(1)


def test_tree_view_preserves_node_identity_when_children_swap() -> None:
    original = {
        "label": "root",
        "children": [
            {"label": "left", "children": [{"label": "leaf_a", "children": []}]},
            {"label": "right", "children": [{"label": "leaf_b", "children": []}]},
        ],
    }
    swapped = {
        "label": "root",
        "children": [
            {"label": "right", "children": [{"label": "leaf_b", "children": []}]},
            {"label": "left", "children": [{"label": "leaf_a", "children": []}]},
        ],
    }

    _, original_graph = build_graph_view(original, "tree_demo", ViewKind.TREE, 3, item_limit=20)
    _, swapped_graph = build_graph_view(swapped, "tree_demo", ViewKind.TREE, 3, item_limit=20)

    original_ids = {node_id for node_id in original_graph.nodes if node_id != "CUT"}
    swapped_ids = {node_id for node_id in swapped_graph.nodes if node_id != "CUT"}

    assert original_ids == swapped_ids


def test_tree_view_keeps_parent_ids_when_descendant_is_removed() -> None:
    from code_visualizer.graph_view_builder import build_graph_view
    from code_visualizer.view_types import ViewKind

    before = {"label": "A", "children": [{"label": "B", "children": []}, {"label": "C", "children": [{"label": "D", "children": []}]}]}
    after = {"label": "A", "children": [{"label": "B", "children": []}, {"label": "C", "children": []}]}

    _, before_graph = build_graph_view(before, "data", ViewKind.TREE, 3, item_limit=20)
    _, after_graph = build_graph_view(after, "data", ViewKind.TREE, 3, item_limit=20)

    before_ids = set(before_graph.nodes.keys())
    after_ids = set(after_graph.nodes.keys())
    shared_tree_ids = {node_id for node_id in before_ids & after_ids if "_t_" in node_id or node_id.startswith("t_")}
    assert shared_tree_ids
