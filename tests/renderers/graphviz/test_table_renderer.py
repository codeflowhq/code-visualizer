from code_visualizer.renderers.graphviz.table_renderer import render_graphviz_table


def test_render_graphviz_table_returns_digraph() -> None:
    dot = render_graphviz_table({"a": 1}, title="data")

    assert "digraph" in dot
    assert "Key" in dot
    assert "Value" in dot


def test_render_graphviz_table_inlines_nested_dict_values() -> None:
    dot = render_graphviz_table(
        {"meta": {"level": 1, "track": "math"}},
        title="data",
        nested_depth=3,
    )

    assert "level" in dot
    assert "track" in dot
    assert "dict keys=2" not in dot
