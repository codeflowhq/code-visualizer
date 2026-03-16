# graph_builder.py
from __future__ import annotations

from typing import Any, Callable, Literal

from .visual_ir import VisualIRExtractor, ExtractOptions
from .config import VisualizerConfig, default_visualizer_config
from .converters import ConverterPipeline
from .models import Anchor, AnchorKind, Artifact, ArtifactKind, NodeKind, VisualGraph, VisualNode
from .renderers import choose_view, render_graphviz_node_link
from .view_types import ViewKind, ViewOverrideMap
from .view_utils import (
    VisualizationImageError,
    _auto_nested_depth,
    _format_scalar_html,
    _is_scalar_value,
    _match_named_override,
    _match_type_pattern_override,
)
from .graph_view_builder import STRUCTURED_VIEW_KINDS, build_graph_view

DirectionLiteral = Literal["LR", "TB"]

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

def _resolve_recursion_depth(
    name: str,
    value: Any,
    config: VisualizerConfig,
) -> int:
    depth_map = config.recursion_depth_map
    if name in depth_map:
        resolved = depth_map[name]
    else:
        resolved = None
        for key, depth in depth_map.items():
            if isinstance(key, type) and isinstance(value, key):
                resolved = depth
                break
        if resolved is None:
            resolved = config.recursion_depth_default

    if resolved < 0:
        cap = config.auto_recursion_depth_cap
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


def _render_structured_view(
    *,
    view: ViewKind,
    name: str,
    value: Any,
    direction: Literal["LR", "TB"],
    recursion_budget: int,
    item_limit: int,
    configured_view: bool,
    value_coercer: Callable[[Any], Any],
    view_resolver: Callable[[str, Any, Any], tuple[ViewKind, bool]],
) -> tuple[Artifact | None, bool]:
    if view not in STRUCTURED_VIEW_KINDS:
        return None, False
    try:
        root_id, nested_graph = build_graph_view(
            value,
            name,
            view,
            recursion_budget,
            item_limit=item_limit,
            value_coercer=value_coercer,
            view_resolver=view_resolver,
        )
    except (TypeError, VisualizationImageError):
        if configured_view:
            raise
        return None, True

    anchor_meta: dict[str, Any] = {}
    if view == ViewKind.GRAPH:
        anchor_meta["connect"] = False
    nested_graph.anchors.append(Anchor(name=name, node_id=root_id, kind=AnchorKind.VAR, meta=anchor_meta))
    graph_direction = "TB" if view in {ViewKind.TREE, ViewKind.HASH_TABLE} else direction
    graph_dot = render_graphviz_node_link(nested_graph, direction=graph_direction)
    return Artifact(ArtifactKind.GRAPHVIZ, graph_dot, title=f"{name}: {view.value}"), True





def _render_scalar_artifact(name: str, value: Any, direction: DirectionLiteral) -> Artifact:
    g = VisualGraph()
    node_id = "scalar_value"
    g.add_node(
        VisualNode(
            node_id,
            NodeKind.OBJECT,
            _format_scalar_html(value),
            {"html_label": True, "node_attrs": {"shape": "plain"}},
        )
    )
    return Artifact(
        ArtifactKind.GRAPHVIZ,
        render_graphviz_node_link(g, direction=direction),
        title=f"{name}: value",
    )


# Unified API: value -> static Artifact (Graphviz/Markdown)
# -----------------------------

def visualize(
    value: Any,
    *,
    name: str = "x",
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

    HTML-based renderers (array/table) obey `config.recursion_depth_default` and the
    `recursion_depth_map` overrides, both of which users can mutate on the config
    instance. Provide a custom `VisualizerConfig` via `config=` to override
    defaults without relying on module-level globals. `graph_direction`,
    `max_depth`, and `max_items_per_view` are likewise drawn from the config.
    """
    cfg = config.copy() if config is not None else default_visualizer_config()
    resolved_direction: DirectionLiteral = cfg.graph_direction
    value_coercer = _make_value_coercer(cfg)

    original_value = value
    value = value_coercer(value)

    def _resolver(slot: str, raw: Any, coerced: Any) -> tuple[ViewKind, bool]:
        return _determine_view(slot, raw, coerced, cfg)

    view, configured_view = _determine_view(name, original_value, value, cfg)

    recursion_budget = _resolve_recursion_depth(name, original_value, cfg)

    artifact, handled = _render_structured_view(
        view=view,
        name=name,
        value=value,
        direction=resolved_direction,
        recursion_budget=recursion_budget,
        item_limit=cfg.max_items_per_view,
        configured_view=configured_view,
        value_coercer=value_coercer,
        view_resolver=_resolver,
    )
    if artifact is not None:
        return artifact
    if handled:
        view = ViewKind.NODE_LINK

    if _is_scalar_value(value):
        return _render_scalar_artifact(name, value, resolved_direction)

    extractor = VisualIRExtractor(
        ExtractOptions(max_depth=cfg.max_depth, max_items=cfg.max_items_per_view),
        value_coercer=value_coercer,
    )
    g = extractor.extract(value, name=name)
    return Artifact(
        ArtifactKind.GRAPHVIZ,
        render_graphviz_node_link(g, direction=resolved_direction),
        title=f"{name}: node_link",
    )
