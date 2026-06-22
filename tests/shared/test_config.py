from __future__ import annotations

from code_visualizer.shared.config import (
    VisualizerConfig,
    default_visualizer_config,
    merge_override_map,
)
from code_visualizer.shared.view_kinds import ViewKind


def test_visualizer_config_output_and_step_limit_precedence() -> None:
    config = VisualizerConfig(output_format="png", trace_step_limit_default=7)
    config.trace_step_limit_map["data"] = -3

    assert config.ensure_output_format("jpeg") == "jpg"
    assert config.ensure_output_format("gif") == "png"
    assert config.step_limit_for("data", override=9) == 0
    assert config.step_limit_for("other", override=9) == 9
    assert config.step_limit_for("missing") == 7


def test_visualizer_config_copy_and_with_converters_preserve_value_semantics() -> None:
    config = default_visualizer_config()
    copied = config.copy()
    copied.view_name_map["data"] = ViewKind.TABLE

    assert "data" not in config.view_name_map

    same = config.with_converters()
    assert same is config

    updated = config.with_converters(lambda value: (True, value), prepend=True)
    assert updated is not config
    assert (
        len(updated.converter_pipeline.converters)
        == len(config.converter_pipeline.converters) + 1
    )


def test_visualizer_config_normalized_clamps_public_boundary_values() -> None:
    config = VisualizerConfig(
        view_name_map={"data": "table"},
        recursion_depth_default=-5,
        recursion_depth_map={"data": 40, list: -2},
        auto_recursion_depth_cap=0,
        max_depth=99,
        max_items_per_view=0,
        output_format="jpeg",
        show_titles=1,  # type: ignore[arg-type]
        allowed_output_formats={"jpeg", "gif"},
        graph_direction="sideways",  # type: ignore[arg-type]
        trace_step_limit_default=-3,
        trace_step_limit_map={"data": -8},
        focus_path_map={"data": "", "item": 123},  # type: ignore[dict-item]
        view_color_map={"data": "  ", "item": 123},  # type: ignore[dict-item]
    )

    normalized = config.normalized()

    assert normalized.view_name_map["data"] is ViewKind.TABLE
    assert normalized.recursion_depth_default == -1
    assert normalized.recursion_depth_map["data"] == 20
    assert normalized.recursion_depth_map[list] == 0
    assert normalized.auto_recursion_depth_cap == 1
    assert normalized.max_depth == 20
    assert normalized.max_items_per_view == 1
    assert normalized.output_format == "jpg"
    assert normalized.show_titles is True
    assert normalized.allowed_output_formats == {"jpg"}
    assert normalized.graph_direction == "LR"
    assert normalized.trace_step_limit_default == 0
    assert normalized.trace_step_limit_map["data"] == 0
    assert normalized.focus_path_map == {"item": "123"}
    assert normalized.view_color_map == {"item": "123"}


def test_merge_override_map_normalizes_string_views() -> None:
    merged = merge_override_map({list: ViewKind.ARRAY_CELLS}, {"data": "table"})

    assert merged[list] is ViewKind.ARRAY_CELLS
    assert merged["data"] is ViewKind.TABLE
