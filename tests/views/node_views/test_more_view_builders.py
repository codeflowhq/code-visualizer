from code_visualizer.shared.view_kinds import ViewKind
from code_visualizer.views.dispatcher import build_graph_view


class LinkedNode:
    def __init__(self, val: int, next_node: "LinkedNode | None" = None) -> None:
        self.val = val
        self.next = next_node


def test_hash_table_node_builder_creates_bucket_heads_and_chain_nodes() -> None:
    value = [[1, 2], [], [{"id": 1, "value": "a"}]]
    root_id, graph = build_graph_view(
        value, "data", ViewKind.HASH_TABLE, 2, item_limit=10
    )

    assert root_id == "hash_exp_1"
    assert "hash_bucket_node_data_0" in graph.nodes
    assert "hash_bucket_node_data_1" in graph.nodes
    assert "hash_bucket_node_data_2" in graph.nodes
    assert "hash_chain_node_data_0_0" in graph.nodes
    assert "hash_chain_node_data_0_1" in graph.nodes
    assert any(edge.dst == "hash_chain_node_data_0_0" for edge in graph.edges)


def test_linked_list_node_builder_creates_nodes_and_tail() -> None:
    head = LinkedNode(1, LinkedNode(2, LinkedNode(3)))
    root_id, graph = build_graph_view(
        head, "linked", ViewKind.LINKED_LIST, 2, item_limit=10
    )

    assert root_id == "linked_exp_1"
    assert any(node_id.startswith("linked_item_linked_1") for node_id in graph.nodes)
    assert any(node_id.startswith("linked_item_linked_2") for node_id in graph.nodes)
    assert any(node_id.startswith("linked_item_linked_3") for node_id in graph.nodes)
    assert "linked_tail_linked" in graph.nodes


def test_heap_dual_node_builder_creates_array_and_tree_sections() -> None:
    root_id, graph = build_graph_view(
        [9, 7, 5, 3], "heap", ViewKind.HEAP_DUAL, 2, item_limit=10
    )

    assert root_id == "heap_exp_1"
    assert any(node_id.startswith("heap_arr_") for node_id in graph.nodes)
    assert any("heap_item_heap_array_9_0" == node_id for node_id in graph.nodes)
    assert any(edge.src == root_id for edge in graph.edges)
    tree_nodes = [
        node for node_id, node in graph.nodes.items() if node_id.startswith("tree_")
    ]
    assert tree_nodes
    assert all(not node.meta.get("html_label") for node in tree_nodes)
    assert all("<font" not in node.label for node in tree_nodes)


def test_heap_dual_node_builder_highlights_focused_array_index() -> None:
    _root_id, graph = build_graph_view(
        [9, 7, 5, 3],
        "data",
        ViewKind.HEAP_DUAL,
        2,
        item_limit=10,
        focus_path="data[2]",
    )

    focused = graph.nodes["heap_item_data_array_5_0"]
    assert focused.meta["node_attrs"]["color"] == "#2563eb"
    assert focused.meta["node_attrs"]["penwidth"] == "2.0"


def test_graph_view_builder_creates_root_and_node_entries() -> None:
    payload = {
        "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        "edges": [{"source": "A", "target": "B", "label": "ab"}],
        "directed": True,
    }
    root_id, graph = build_graph_view(
        payload, "graph_demo", ViewKind.GRAPH, 2, item_limit=10
    )

    assert root_id.startswith("graph_")
    assert graph.nodes[root_id].meta.get("kind") == "graph_root"
    assert any(edge.label == "ab" for edge in graph.edges)


def test_image_view_builder_creates_html_image_node() -> None:
    png_data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0l8AAAAASUVORK5CYII="
    root_id, graph = build_graph_view(
        png_data_url, "img", ViewKind.IMAGE, 1, item_limit=10
    )

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

    src = image_sources._detect_image_source(
        "https://example.com/photo?w=1024&h=1024", strict=True
    )

    assert src is not None
    assert src.endswith(".jpg")


def test_strict_remote_image_url_falls_back_to_original_url(monkeypatch) -> None:
    from code_visualizer.utils import image_sources

    monkeypatch.setattr(
        image_sources,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("blocked")),
    )

    url = "https://example.com/photo?w=1024&h=1024"

    assert image_sources._detect_image_source(url, strict=True) == url


def test_nested_table_header_uses_widest_value_width() -> None:
    import re

    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": 2, "tags": ["c", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    header = graph.nodes["table_header_data"].label
    users = graph.nodes["table_row_data_users"].label
    meta = graph.nodes["table_row_data_meta"].label

    header_widths = re.findall(r"(?:WIDTH|width)='(\d+)'", header)
    header_value_width = header_widths[-1] if header_widths else None
    assert header_value_width is not None
    users_widths = re.findall(r"(?:WIDTH|width)='(\d+)'", users)
    meta_widths = re.findall(r"(?:WIDTH|width)='(\d+)'", meta)
    assert header_value_width in users_widths
    assert header_value_width in meta_widths
    assert "table_row_data_users_value" in users
    assert "table_row_data_meta_value" in meta


def test_table_view_inlines_nested_dict_html_inside_the_value_cell() -> None:
    value = {
        "name": "Alice",
        "meta": {"level": 1, "track": "math"},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    meta_row = graph.nodes["table_row_data_meta"].label

    assert "<b>Key</b>" in meta_row
    assert "<b>Value</b>" in meta_row
    assert ">level<" in meta_row
    assert ">track<" in meta_row
    assert "#f3f4f6" in meta_row
    assert set(graph.nodes) == {
        "table_exp_1",
        "table_header_data",
        "table_row_data_name",
        "table_row_data_meta",
    }


def test_table_view_centers_nested_value_previews() -> None:
    value = {
        "mask": 21,
        "selected": [0, 2, 4],
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    selected_row = graph.nodes["table_row_data_selected"].label

    assert "ALIGN='CENTER'" in selected_row
    assert "CELLPADDING='0'" in selected_row
    assert "selected" in selected_row


def test_table_view_centers_nested_dict_value_cells() -> None:
    value = {
        "name": "Alice",
        "meta": {"level": 1, "track": "math"},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    meta_row = graph.nodes["table_row_data_meta"].label

    assert "ALIGN='CENTER'" in meta_row
    assert "CELLPADDING='0'" in meta_row


def test_table_view_sizes_nested_dict_preview_from_content_width() -> None:
    import re

    value = {
        "name": "Alice",
        "meta": {"level": 1, "track": "math"},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    header = graph.nodes["table_header_data"].label
    meta_row = graph.nodes["table_row_data_meta"].label

    header_widths = re.findall(r"(?:WIDTH|width)='(\d+)'", header)
    header_value_width = header_widths[-1] if header_widths else None
    assert header_value_width is not None
    assert int(header_value_width) < 232
    assert meta_row.count(f"WIDTH='{header_value_width}'") >= 1
    assert f"width='{int(header_value_width) - 4}'" in meta_row
    assert "FIXEDSIZE='TRUE'" in meta_row
    assert (
        f"<table border='1' cellborder='0' cellspacing='0' width='{int(header_value_width) - 4}' cellpadding='0'>"
        in meta_row
    )
    assert (
        f"<td width='{int(header_value_width) - 4}' FIXEDSIZE='TRUE' align='center' cellpadding='0'>"
        in meta_row
    )
    assert "valign='top'" in meta_row


def test_table_view_sizes_nested_sequence_preview_from_content_width() -> None:
    import re

    value = {
        "mask": 1,
        "selected": [0, 2, 4],
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    header = graph.nodes["table_header_data"].label
    selected_row = graph.nodes["table_row_data_selected"].label

    header_widths = re.findall(r"(?:WIDTH|width)='(\d+)'", header)
    header_value_width = header_widths[-1] if header_widths else None
    assert header_value_width is not None
    assert int(header_value_width) < 180
    assert "cv-data-selected-value-table" in selected_row


def test_table_view_shrinks_nested_dict_to_parent_value_budget() -> None:
    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": {"1": 2}, "tags": ["c", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    value["users"][1]["tags"][0] = "z"

    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 5, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label

    assert "width='140' align='left' cellpadding='0'" in users_row
    assert "<td width='92' bgcolor='#f3f4f6' align='center'><b>Key</b></td>" in users_row
    assert "<td width='48' bgcolor='#f3f4f6' align='center'><b>Value</b></td>" in users_row
    assert "width='92' bgcolor='#f3f4f6' align='center'><b>Value</b></td>" not in users_row


def test_table_view_shrinks_deep_nested_dict_key_and_value_within_parent_budget() -> None:
    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": {"1": {"inner": [10, 20]}}, "tags": ["c", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    value["users"][1]["id"]["1"]["inner"][0] = 99
    value["users"][1]["tags"][0] = "z"

    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 5, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label

    assert "WIDTH='94'><tr><td width='60' bgcolor='#f3f4f6' align='center'><b>Key</b></td><td width='34' bgcolor='#f3f4f6' align='center'><b>Value</b></td></tr>" in users_row
    assert "WIDTH='94'><tr><td width='92' bgcolor='#f3f4f6' align='center'><b>Key</b></td><td width='34' bgcolor='#f3f4f6' align='center'><b>Value</b></td></tr>" not in users_row


def test_table_view_shrinks_deep_nested_sequence_cells_within_wrapper_width() -> None:
    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": {"1": {"inner": [10, 20]}}, "tags": ["c", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    value["users"][1]["id"]["1"]["inner"][0] = 99
    value["users"][1]["tags"][0] = "z"

    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 6, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label

    assert "cv-data-users-1--id-1-inner-wrapper' border='0' cellborder='0' cellspacing='0' WIDTH='34'" in users_row
    assert "<td width='17' align='center' bgcolor='#ffffff' cellpadding='2'><font point-size=\"12\" color=\"#0f172a\">99</font></td><td width='17' align='center' bgcolor='#ffffff' cellpadding='2'><font point-size=\"12\" color=\"#0f172a\">20</font></td>" in users_row
    assert "<td width='34' align='center' bgcolor='#ffffff' cellpadding='2'><font point-size=\"12\" color=\"#0f172a\">99</font></td><td width='34' align='center' bgcolor='#ffffff' cellpadding='2'><font point-size=\"12\" color=\"#0f172a\">20</font></td>" not in users_row


def test_table_view_stretches_nested_sequence_cells_to_fill_value_width() -> None:
    import re

    value = {
        "mask": 21,
        "selected": [0, 2, 4],
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    selected_row = graph.nodes["table_row_data_selected"].label
    cell_widths = re.findall(
        r"<td width='(\d+)' align='center' bgcolor='#ffffff' cellpadding='2'>",
        selected_row,
    )
    index_widths = re.findall(r"<td width='(\d+)' align='center'>", selected_row)

    assert cell_widths[:3] == ["32", "32", "32"]
    assert index_widths[:3] == ["32", "32", "32"]


def test_table_view_stretches_child_dict_tables_within_sequence_cells() -> None:
    import re

    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": 2, "tags": ["z", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label

    child_table_widths = re.findall(
        r"<td width='194' align='center' bgcolor='#ffffff' cellpadding='2'><table[^>]*WIDTH='(\d+)'",
        users_row,
    )

    assert child_table_widths == ["186", "186"]


def test_table_view_centers_nested_container_stubs() -> None:
    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": 2, "tags": ["z", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label

    assert "list len=2" in users_row
    assert "<td width='94' align='center' cellpadding='2'><font point-size=\"12\" color=\"#475569\">list len=2</font></td>" in users_row


def test_table_view_stretches_sequence_of_dicts_to_the_available_value_width() -> None:
    import re

    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": 2, "tags": ["z", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label
    direct_cell_widths = re.findall(
        r"<td width='(\d+)' align='center' bgcolor='#ffffff' cellpadding='2'><table",
        users_row,
    )
    index_widths = re.findall(
        r"<td width='(\d+)' align='center'><font color='#dc2626' point-size='12'>",
        users_row,
    )

    assert direct_cell_widths == ["194", "194"]
    assert index_widths[-2:] == ["194", "194"]


def test_table_view_normalizes_list_of_dict_sibling_column_widths() -> None:
    import re

    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": {"1": 2}, "tags": ["z", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 3, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label
    id_value_widths = re.findall(
        r"<tr><td width='92' align='center'>id</td><td width='(\d+)' align='center' cellpadding='2'>",
        users_row,
    )

    assert id_value_widths == ["140", "140"]
    assert "dict keys=1" in users_row
    assert ">tags</td><td width='140' align='center' cellpadding='2'><font point-size=\"12\" color=\"#475569\">list len=2</font></td>" in users_row


def test_table_view_recursively_fits_deeper_nested_sequences() -> None:
    value = {
        "users": [
            {"id": 1, "tags": ["a", "b"]},
            {"id": {"1": 2}, "tags": ["z", "d"]},
        ],
        "meta": {"page": 1, "total": 2},
    }
    _, graph = build_graph_view(value, "data", ViewKind.TABLE, 5, item_limit=10)

    users_row = graph.nodes["table_row_data_users"].label

    assert "cv-data-users-0--tags-wrapper' border='0' cellborder='0' cellspacing='0' WIDTH='140'" in users_row
    assert "cv-data-users-0--tags-value-table' border='1' cellborder='1' cellspacing='0' WIDTH='140'" in users_row
    assert "cv-data-users-0--tags-index-row'><td width='70' align='center'><font color='#dc2626' point-size='12'>0</font>" in users_row
    assert "cv-data-users-1--tags-wrapper' border='0' cellborder='0' cellspacing='0' WIDTH='140'" in users_row
    assert "cv-data-users-1--tags-value-table' border='1' cellborder='1' cellspacing='0' WIDTH='140'" in users_row
    assert "cv-data-users-1--tags-index-row'><td width='70' align='center'><font color='#dc2626' point-size='12'>0</font>" in users_row


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

    _, original_graph = build_graph_view(
        original, "tree_demo", ViewKind.TREE, 3, item_limit=20
    )
    _, swapped_graph = build_graph_view(
        swapped, "tree_demo", ViewKind.TREE, 3, item_limit=20
    )

    original_ids = {node_id for node_id in original_graph.nodes if node_id != "CUT"}
    swapped_ids = {node_id for node_id in swapped_graph.nodes if node_id != "CUT"}

    assert original_ids == swapped_ids


def test_tree_view_keeps_parent_ids_when_descendant_is_removed() -> None:
    from code_visualizer.shared.view_kinds import ViewKind
    from code_visualizer.views.dispatcher import build_graph_view

    before = {
        "label": "A",
        "children": [
            {"label": "B", "children": []},
            {"label": "C", "children": [{"label": "D", "children": []}]},
        ],
    }
    after = {
        "label": "A",
        "children": [{"label": "B", "children": []}, {"label": "C", "children": []}],
    }

    _, before_graph = build_graph_view(before, "data", ViewKind.TREE, 3, item_limit=20)
    _, after_graph = build_graph_view(after, "data", ViewKind.TREE, 3, item_limit=20)

    before_ids = set(before_graph.nodes.keys())
    after_ids = set(after_graph.nodes.keys())
    shared_tree_ids = {
        node_id
        for node_id in before_ids & after_ids
        if "_t_" in node_id or node_id.startswith("t_")
    }
    assert shared_tree_ids
