# graph_builder.py
from __future__ import annotations

from typing import Any, Callable, Literal, Mapping

from .visual_ir import VisualIRExtractor, ExtractOptions
from .config import VisualizerConfig, default_visualizer_config
from .converters import ConverterPipeline
from .models import Anchor, AnchorKind, Artifact, ArtifactKind
from .renderers import (
    choose_view,
    render_graphviz_bar,
    render_graphviz_image,
    render_graphviz_node_link,
    render_graphviz_scalar,
)
from .view_types import ViewKind, ViewOverrideMap
from .view_utils import (
    VisualizationImageError,
    _auto_nested_depth,
    _is_scalar_value,
    _match_named_override,
    _match_type_pattern_override,
)
from .graph_view_builder import build_graph_view


HTML_EMBED_VIEWS: set[ViewKind] = {
    ViewKind.ARRAY_CELLS,
    ViewKind.TABLE,
    ViewKind.MATRIX,
    ViewKind.HASH_TABLE,
    ViewKind.LINKED_LIST,
    ViewKind.TREE,
    ViewKind.GRAPH,
    ViewKind.HEAP_DUAL,
}

def _make_value_coercer(config: VisualizerConfig) -> Callable[[Any], Any]:
    pipeline: ConverterPipeline = config.converter_pipeline

    def _coerce(value: Any) -> Any:
        coerced, _ = pipeline.coerce(value)
        return coerced

    return _coerce


def _apply_view_override(name: str, value: Any, view_map: ViewOverrideMap | None) -> ViewKind | None:
    """
    Resolve view overrides by (1) exact variable name, (2) isinstance against type keys.
    """
    if not view_map:
        return None

    if name in view_map:
        return view_map[name]

    for key, override in view_map.items():
        if isinstance(key, type) and isinstance(value, key):
            return override

    return None

def _resolve_nested_depth(
    name: str,
    value: Any,
    explicit_depth: int | None,
    nested_depth_map: Mapping[str | type[Any], int] | None,
    config: VisualizerConfig,
) -> int:
    if explicit_depth is not None:
        resolved = explicit_depth
    else:
        depth_map = nested_depth_map or config.nested_depth_map
        if name in depth_map:
            resolved = depth_map[name]
        else:
            resolved = None
            for key, depth in depth_map.items():
                if isinstance(key, type) and isinstance(value, key):
                    resolved = depth
                    break
            if resolved is None:
                resolved = config.nested_depth_default

    if resolved < 0:
        cap = config.auto_nested_depth_cap
        return _auto_nested_depth(value, cap)

    return max(0, resolved)


def _determine_view(
    name: str,
    original_value: Any,
    coerced_value: Any,
    config: VisualizerConfig,
) -> tuple[ViewKind, bool]:
    override_view = _match_named_override(name, config.view_name_map)
    if override_view is not None:
        return override_view, True
    override_view = _match_type_pattern_override(original_value, config.view_type_map)
    if override_view is not None:
        return override_view, True
    override_view = _apply_view_override(name, original_value, config.view_map)
    if override_view is not None:
        return override_view, True
    return choose_view(coerced_value), False





# Unified API: value -> static Artifact (Graphviz/Markdown)
# -----------------------------

def visualize(
    value: Any,
    *,
    name: str = "x",
    max_depth: int = 3,
    max_items: int = 50,
    direction: Literal["LR", "TD"] = "LR",
    nested_depth: int | None = None,
    nested_depth_map: Mapping[str | type[Any], int] | None = None,
    config: VisualizerConfig | None = None,
) -> Artifact:
    """
    Stage 1: Python-only static output.
    Returns Graphviz DOT text (most views) as Artifact(kind="graphviz").

    View selection is resolver-driven via `VisualizerConfig`:
    `view_name_map` (exact variable names/key paths) takes precedence,
    followed by `view_type_map` (lightweight structural patterns such as
    `list[number]`, `tuple[list]`, `dict`, etc.), then `view_map`
    (isinstance overrides). If none of these match, `renderers.choose_view`
    infers a fallback ViewKind.

    `nested_depth` controls how many nested list/dict levels are expanded inside
    HTML-based renderers (array/table). If not provided, the function consults
    `nested_depth_map` and finally `config.nested_depth_default`. Supplying a
    negative value instructs the renderer to auto-infer the necessary depth,
    bounded by `config.auto_nested_depth_cap`. Provide a custom
    `VisualizerConfig` via `config=` to override defaults without relying on
    module-level globals.
    """
    cfg = config.copy() if config is not None else default_visualizer_config()
    value_coercer = _make_value_coercer(cfg)

    original_value = value
    value = value_coercer(value)

    def _resolver(slot: str, raw: Any, coerced: Any) -> tuple[ViewKind, bool]:
        return _determine_view(slot, raw, coerced, cfg)

    view, configured_view = _determine_view(name, original_value, value, cfg)

    depth_budget = _resolve_nested_depth(name, original_value, nested_depth, nested_depth_map, cfg)

    # Specialized views (from raw value)
    if view in HTML_EMBED_VIEWS:
        try:
            root_id, nested_graph = build_graph_view(
                value,
                name,
                view,
                depth_budget,
                max_items=max_items,
                value_coercer=value_coercer,
                view_resolver=_resolver,
            )
        except TypeError:
            if configured_view:
                raise
            view = ViewKind.NODE_LINK
        else:
            anchor_meta: dict[str, Any] = {}
            if view == ViewKind.GRAPH:
                anchor_meta["connect"] = False
            nested_graph.anchors.append(Anchor(name=name, node_id=root_id, kind=AnchorKind.VAR, meta=anchor_meta))
            graph_direction = "TD" if view in {ViewKind.TREE, ViewKind.HASH_TABLE} else direction
            graph_dot = render_graphviz_node_link(nested_graph, direction=graph_direction)
            return Artifact(ArtifactKind.GRAPHVIZ, graph_dot, title=f"{name}: {view.value}")

    if view == ViewKind.IMAGE:
        try:
            return Artifact(ArtifactKind.GRAPHVIZ, render_graphviz_image(value, title=name), title=f"{name}: image")
        except VisualizationImageError:
            if configured_view:
                raise
            view = ViewKind.NODE_LINK

    if view == ViewKind.BAR:
        if not isinstance(value, list):
            if configured_view:
                raise TypeError("bar view expects a list of numbers")
            view = ViewKind.NODE_LINK
        else:
            return Artifact(
                ArtifactKind.GRAPHVIZ,
                render_graphviz_bar(value, title=name, max_items=max_items),
                title=f"{name}: bar",
            )

    # Fallback: VisualIR node-link (generic)
    if view == ViewKind.NODE_LINK and _is_scalar_value(value):
        return Artifact(
            ArtifactKind.GRAPHVIZ,
            render_graphviz_scalar(value, title=name, nested_depth=depth_budget, max_items=max_items),
            title=f"{name}: scalar",
        )

    extractor = VisualIRExtractor(
        ExtractOptions(max_depth=max_depth, max_items=max_items),
        value_coercer=value_coercer,
    )
    g = extractor.extract(value, name=name)
    return Artifact(
        ArtifactKind.GRAPHVIZ,
        render_graphviz_node_link(g, direction=direction),
        title=f"{name}: node_link",
    )
