from __future__ import annotations

import code_visualizer.pipeline.pipeline as visualization
from code_visualizer.pipeline.pipeline import visualize
from code_visualizer.shared.config import VisualizerConfig
from code_visualizer.shared.models import ArtifactKind


def test_visualize_renders_scalar_artifact() -> None:
    artifact = visualize(
        123,
        name="data",
        config=VisualizerConfig(show_titles=False, output_format="dot"),
    )

    assert artifact.kind is ArtifactKind.GRAPHVIZ
    assert artifact.title is None
    assert "123" in artifact.content


def test_visualize_falls_back_to_node_link_when_structured_view_was_handled() -> None:
    config = VisualizerConfig(show_titles=True)

    original = visualization.render_structured_view
    visualization.render_structured_view = lambda **kwargs: (None, True)
    try:
        artifact = visualize({"a": 1}, name="data", config=config)
    finally:
        visualization.render_structured_view = original

    assert artifact.kind is ArtifactKind.GRAPHVIZ
    assert artifact.title == "data: node_link"
    assert "digraph" in artifact.content


def test_visualize_uses_ir_extractor_for_non_scalar_unstructured_values() -> None:
    class Obj:
        def __init__(self) -> None:
            self.value = 1

    artifact = visualize(Obj(), name="obj", config=VisualizerConfig(show_titles=True))

    assert artifact.kind is ArtifactKind.GRAPHVIZ
    assert artifact.title == "obj: node_link"
    assert "obj" in artifact.content


def test_visualize_normalizes_blank_slot_names_to_default() -> None:
    artifact = visualize(123, name="   ", config=VisualizerConfig(show_titles=True))

    assert artifact.kind is ArtifactKind.GRAPHVIZ
    assert artifact.title == "x: value"
    assert "123" in artifact.content


def test_visualize_applies_normalized_legacy_string_view_overrides_at_api_boundary() -> None:
    artifact = visualize(
        {"score": 92},
        name="data",
        config=VisualizerConfig(
            view_name_map={"data": "table"},  # type: ignore[dict-item]
            show_titles=True,
        ),
    )

    assert artifact.kind is ArtifactKind.GRAPHVIZ
    assert artifact.title == "data: table"
