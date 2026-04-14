from code_visualizer.builders.graph_artifacts import (
    determine_view,
    resolve_recursion_depth,
    visualize,
)
from code_visualizer.config import default_visualizer_config
from code_visualizer.models import ArtifactKind
from code_visualizer.view_types import ViewKind


def test_determine_view_prefers_name_override() -> None:
    config = default_visualizer_config()
    config.view_name_map["data"] = ViewKind.TABLE

    view, configured = determine_view("data", {"a": 1}, {"a": 1}, config)

    assert view is ViewKind.TABLE
    assert configured is True


def test_resolve_recursion_depth_uses_auto_mode_for_negative_default() -> None:
    config = default_visualizer_config()
    config.recursion_depth_default = -1
    config.auto_recursion_depth_cap = 3
    config.recursion_depth_map = {}

    resolved = resolve_recursion_depth("data", {"a": {"b": [1, 2, 3]}}, config)

    assert 0 <= resolved <= 3


def test_visualize_returns_graphviz_artifact_for_structured_values() -> None:
    artifact = visualize({"score": 92, "passed": True}, name="data")

    assert artifact.kind is ArtifactKind.GRAPHVIZ
    assert "digraph" in artifact.content
    assert artifact.title == "data: table"
