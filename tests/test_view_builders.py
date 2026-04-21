from code_visualizer.graph_view_builder import build_graph_view
from code_visualizer.view_types import ViewKind


def test_array_node_builder_uses_occurrence_based_item_ids() -> None:
    root_id, graph = build_graph_view([7, 3, 7], "data", ViewKind.ARRAY_CELLS_NODE, 2, item_limit=10)

    assert root_id == "arr_exp_1"
    assert "arr_item_data_7_0" in graph.nodes
    assert "arr_item_data_7_1" in graph.nodes
    assert "arr_item_data_3_0" in graph.nodes
    assert graph.graph_attrs["label"] == "<<font point-size='16' color='#0f172a'><b>data</b></font>>"


def test_array_node_builder_renders_nested_list_inline() -> None:
    _, graph = build_graph_view([7, 3, [0, 1, 2]], "data", ViewKind.ARRAY_CELLS_NODE, 2, item_limit=10)

    nested_label = graph.nodes["arr_cell_data_2"].label

    assert 'id="cv-data-2--value-table"' in nested_label
    assert "arr_cell_data_2__" not in nested_label


def test_table_node_builder_creates_header_and_row_nodes() -> None:
    value = {"score": 92, "meta": {"level": 2}}
    root_id, graph = build_graph_view(value, "data", ViewKind.TABLE_NODE, 2, item_limit=10)

    assert root_id == "table_exp_1"
    assert "table_header_data" in graph.nodes
    assert "table_row_data_score" in graph.nodes
    assert "table_row_data_meta" in graph.nodes
    assert any(edge.src == "table_header_data" and edge.dst == "table_row_data_score" for edge in graph.edges)
    assert "fixedsize='true'" in graph.nodes["table_header_data"].label


def test_matrix_node_builder_creates_headers_and_cell_nodes() -> None:
    root_id, graph = build_graph_view([[1, 2], [3, 4]], "data", ViewKind.MATRIX_NODE, 2, item_limit=10)

    assert root_id == "matrix_exp_1"
    assert "matrix_corner_data" in graph.nodes
    assert "matrix_col_data_0" in graph.nodes
    assert "matrix_col_data_1" in graph.nodes
    assert "matrix_row_data_0" in graph.nodes
    assert "matrix_row_data_1" in graph.nodes
    assert "matrix_cell_data_0_0" in graph.nodes
    assert "matrix_cell_data_1_1" in graph.nodes
