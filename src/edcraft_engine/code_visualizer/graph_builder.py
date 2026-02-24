# graph_builder.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy optional
    np = None  # type: ignore

try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas optional
    pd = None  # type: ignore

from edcraft_engine.code_visualizer.visual_ir import VisualIRExtractor, ExtractOptions
from edcraft_engine.code_visualizer import config as viz_config
from edcraft_engine.code_visualizer.models import VisualGraph, VisualNode, VisualEdge, Anchor
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
from .graph_view_builder import GraphViewBuilder as _GraphViewBuilder


HTML_EMBED_VIEWS: set[str] = {
    "array_cells",
    "table",
    "matrix",
    "hash_table",
    "linked_list",
    "tree",
    "graph",
    "heap_dual",
}

ArtifactKind = Literal["graphviz", "mermaid", "markdown", "text"]

@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    content: str
    title: str | None = None

def _coerce_known_types(value: Any) -> Any:
    if np is not None and isinstance(value, np.ndarray):  # type: ignore[has-type]
        return value.tolist()
    if pd is not None:
        if isinstance(value, pd.DataFrame):  # type: ignore[has-type]
            return value.to_dict(orient="list")
        if isinstance(value, pd.Series):  # type: ignore[has-type]
            return value.to_dict()
    return value


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
) -> int:
    if explicit_depth is not None:
        resolved = explicit_depth
    else:
        depth_map = nested_depth_map or viz_config.NESTED_DEPTH_MAP
        if name in depth_map:
            resolved = depth_map[name]
        else:
            resolved = None
            for key, depth in depth_map.items():
                if isinstance(key, type) and isinstance(value, key):
                    resolved = depth
                    break
            if resolved is None:
                resolved = viz_config.DEFAULT_NESTED_DEPTH

    if resolved < 0:
        cap = getattr(viz_config, "AUTO_NESTED_DEPTH_CAP", 6)
        return _auto_nested_depth(value, cap)

    return max(0, resolved)


def _determine_view(name: str, original_value: Any, coerced_value: Any) -> tuple[ViewKind, bool]:
    override_view = _match_named_override(name, getattr(viz_config, "DEFAULT_VIEW_NAME_MAP", {}))
    if override_view is not None:
        return override_view, True
    override_view = _match_type_pattern_override(original_value, getattr(viz_config, "DEFAULT_VIEW_TYPE_MAP", {}))
    if override_view is not None:
        return override_view, True
    override_view = _apply_view_override(name, original_value, viz_config.DEFAULT_VIEW_MAP)
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
) -> Artifact:
    """
    Stage 1: Python-only static output.
    Returns Graphviz DOT text (most views) as Artifact(kind="graphviz").

    View selection is entirely mapper-driven via `code_visualizer.config`:
    `DEFAULT_VIEW_NAME_MAP` (exact variable names/key paths) takes precedence,
    followed by `DEFAULT_VIEW_TYPE_MAP` (lightweight structural patterns such as
    `list[number]`, `tuple[list]`, `dict`, etc.), then the legacy
    `DEFAULT_VIEW_MAP` (isinstance overrides). If none of these match,
    `renderers.choose_view` infers a fallback ViewKind.

    `nested_depth` controls how many nested list/dict levels are expanded inside
    HTML-based renderers (array/table). If not provided, the function consults
    `nested_depth_map` and finally `config.DEFAULT_NESTED_DEPTH`. Supplying a
    negative value instructs the renderer to auto-infer the necessary depth,
    bounded by `config.AUTO_NESTED_DEPTH_CAP`.
    """
    original_value = value
    value = _coerce_known_types(value)

    view, configured_view = _determine_view(name, original_value, value)

    depth_budget = _resolve_nested_depth(name, original_value, nested_depth, nested_depth_map)

    # Specialized views (from raw value)
    if view in HTML_EMBED_VIEWS:
        builder = _GraphViewBuilder(
            max_items,
            value_coercer=_coerce_known_types,
            view_resolver=_determine_view,
        )
        try:
            root_id = builder.build(value, name, view, depth_budget)
        except TypeError:
            if configured_view:
                raise
            view = "node_link"
        else:
            anchor_meta = {}
            if view == "graph":
                anchor_meta["connect"] = False
            builder.graph.anchors.append(Anchor(name=name, node_id=root_id, kind="var", meta=anchor_meta))
            if view in {"tree", "hash_table"}:
                graph_direction = "TD"
            else:
                graph_direction = direction
            graph_dot = render_graphviz_node_link(builder.graph, direction=graph_direction)
            return Artifact("graphviz", graph_dot, title=f"{name}: {view}")

    if view == "image":
        try:
            return Artifact("graphviz", render_graphviz_image(value, title=name), title=f"{name}: image")
        except VisualizationImageError:
            if configured_view:
                raise
            view = "node_link"

    if view == "bar":
        if not isinstance(value, list):
            if configured_view:
                raise TypeError("bar view expects a list of numbers")
            view = "node_link"
        else:
            return Artifact("graphviz", render_graphviz_bar(value, title=name, max_items=max_items), title=f"{name}: bar")

    # Fallback: VisualIR node-link (generic)
    if view == "node_link" and _is_scalar_value(value):
        return Artifact(
            "graphviz",
            render_graphviz_scalar(value, title=name, nested_depth=depth_budget, max_items=max_items),
            title=f"{name}: scalar",
        )

    extractor = VisualIRExtractor(ExtractOptions(max_depth=max_depth, max_items=max_items))
    g = extractor.extract(value, name=name)
    return Artifact("graphviz", render_graphviz_node_link(g, direction=direction), title=f"{name}: node_link")
