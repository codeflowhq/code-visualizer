from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from ..config import VisualizerConfig, default_visualizer_config
from ..graph_view_builder import build_graph_view
from ..models import (
    Anchor,
    AnchorKind,
    Artifact,
    ArtifactKind,
    NodeKind,
    VisualGraph,
    VisualNode,
)
from ..renderers import render_graphviz_node_link
from ..utils.image_sources import VisualizationImageError
from ..utils.value_formatting import format_scalar_html as _format_scalar_html
from ..view_types import ViewKind
from ..view_utils import _is_scalar_value
from ..views.nested import STRUCTURED_VIEW_KINDS
from ..visual_ir import ExtractOptions, VisualIRExtractor
from .view_resolution import (
    canonicalize_outer_view,
    determine_view,
    make_value_coercer,
    resolve_recursion_depth,
)

DirectionLiteral = Literal["LR", "TD"]
ViewResolver = Callable[[str, Any, Any], tuple[ViewKind, bool]]

_DEFAULT_NODE_VIEW_MAP: dict[ViewKind, ViewKind] = {
    ViewKind.ARRAY_CELLS: ViewKind.ARRAY_CELLS_NODE,
    ViewKind.MATRIX: ViewKind.MATRIX_NODE,
    ViewKind.TABLE: ViewKind.TABLE_NODE,
    ViewKind.HASH_TABLE: ViewKind.HASH_TABLE_NODE,
    ViewKind.LINKED_LIST: ViewKind.LINKED_LIST_NODE,
    ViewKind.HEAP_DUAL: ViewKind.HEAP_DUAL_NODE,
    ViewKind.BAR: ViewKind.BAR_NODE,
}







def render_structured_view(
    *,
    view: ViewKind,
    name: str,
    value: Any,
    direction: DirectionLiteral,
    recursion_budget: int,
    item_limit: int,
    configured_view: bool,
    value_coercer: Callable[[Any], Any],
    view_resolver: ViewResolver,
    focus_path: str | None = None,
    show_titles: bool = True,
) -> tuple[Artifact | None, bool]:
    if view not in STRUCTURED_VIEW_KINDS:
        return None, False

    rendered_view = canonicalize_outer_view(view)
    try:
        root_id, nested_graph = build_graph_view(
            value,
            name,
            rendered_view,
            recursion_budget,
            item_limit=item_limit,
            value_coercer=value_coercer,
            view_resolver=view_resolver,
            focus_path=focus_path,
            show_titles=show_titles,
        )
    except (TypeError, VisualizationImageError):
        if configured_view:
            raise
        return None, True

    anchor_meta: dict[str, Any] = {}
    if view == ViewKind.GRAPH:
        anchor_meta["connect"] = False
    nested_graph.anchors.append(Anchor(name=name, node_id=root_id, kind=AnchorKind.VAR, meta=anchor_meta))
    graph_direction: DirectionLiteral = "TD" if rendered_view in {ViewKind.TREE, ViewKind.HASH_TABLE, ViewKind.HASH_TABLE_NODE} else direction
    graph_dot = render_graphviz_node_link(nested_graph, direction=graph_direction)
    artifact_title = f"{name}: {view.value}" if show_titles else None
    return Artifact(ArtifactKind.GRAPHVIZ, graph_dot, title=artifact_title), True


def render_scalar_artifact(name: str, value: Any, direction: DirectionLiteral, *, show_titles: bool) -> Artifact:
    graph = VisualGraph()
    graph.add_node(
        VisualNode(
            "scalar_value",
            NodeKind.OBJECT,
            _format_scalar_html(value),
            {"html_label": True, "node_attrs": {"shape": "plain"}},
        )
    )
    return Artifact(
        ArtifactKind.GRAPHVIZ,
        render_graphviz_node_link(graph, direction=direction),
        title=f"{name}: value" if show_titles else None,
    )


def visualize(value: Any, *, name: str = "x", config: VisualizerConfig | None = None) -> Artifact:
    cfg = config.copy() if config is not None else default_visualizer_config()
    resolved_direction: DirectionLiteral = "TD" if cfg.graph_direction == "TB" else "LR"
    value_coercer = make_value_coercer(cfg)

    original_value = value
    value = value_coercer(value)

    def _resolver(slot: str, raw: Any, coerced: Any) -> tuple[ViewKind, bool]:
        return determine_view(slot, raw, coerced, cfg)

    view, configured_view = determine_view(name, original_value, value, cfg)
    recursion_budget = resolve_recursion_depth(name, original_value, cfg)
    focus_path = cfg.focus_path_map.get(name)

    artifact, handled = render_structured_view(
        view=view,
        name=name,
        value=value,
        direction=resolved_direction,
        recursion_budget=recursion_budget,
        item_limit=cfg.max_items_per_view,
        configured_view=configured_view,
        value_coercer=value_coercer,
        view_resolver=_resolver,
        focus_path=focus_path,
        show_titles=cfg.show_titles,
    )
    if artifact is not None:
        return artifact
    if handled:
        view = ViewKind.NODE_LINK

    if _is_scalar_value(value):
        return render_scalar_artifact(name, value, resolved_direction, show_titles=cfg.show_titles)

    extractor = VisualIRExtractor(
        ExtractOptions(max_depth=cfg.max_depth, max_items=cfg.max_items_per_view),
        value_coercer=value_coercer,
    )
    graph = extractor.extract(value, name=name)
    return Artifact(
        ArtifactKind.GRAPHVIZ,
        render_graphviz_node_link(graph, direction=resolved_direction),
        title=f"{name}: node_link" if cfg.show_titles else None,
    )
