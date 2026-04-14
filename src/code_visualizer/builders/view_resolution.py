from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..config import VisualizerConfig
from ..converters import ConverterPipeline
from ..renderers import choose_view
from ..utils.type_patterns import _match_type_pattern_override
from ..view_types import ViewKind, ViewOverrideMap
from ..view_utils import _auto_nested_depth, _match_named_override

_DEFAULT_NODE_VIEW_MAP: dict[ViewKind, ViewKind] = {
    ViewKind.ARRAY_CELLS: ViewKind.ARRAY_CELLS_NODE,
    ViewKind.MATRIX: ViewKind.MATRIX_NODE,
    ViewKind.TABLE: ViewKind.TABLE_NODE,
    ViewKind.HASH_TABLE: ViewKind.HASH_TABLE_NODE,
    ViewKind.LINKED_LIST: ViewKind.LINKED_LIST_NODE,
    ViewKind.HEAP_DUAL: ViewKind.HEAP_DUAL_NODE,
    ViewKind.BAR: ViewKind.BAR_NODE,
}


def canonicalize_outer_view(view: ViewKind) -> ViewKind:
    return _DEFAULT_NODE_VIEW_MAP.get(view, view)


def make_value_coercer(config: VisualizerConfig) -> Callable[[Any], Any]:
    pipeline: ConverterPipeline = config.converter_pipeline

    def _coerce(value: Any) -> Any:
        coerced, _ = pipeline.coerce(value)
        return coerced

    return _coerce


def apply_view_override(name: str, value: Any, view_map: ViewOverrideMap | None) -> ViewKind | None:
    if not view_map:
        return None
    if name in view_map:
        return view_map[name]
    for key, override in view_map.items():
        if isinstance(key, type) and isinstance(value, key):
            return override
    return None


def resolve_recursion_depth(name: str, value: Any, config: VisualizerConfig) -> int:
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

    resolved_depth = config.recursion_depth_default if resolved is None else resolved
    if resolved_depth < 0:
        resolved_depth = _auto_nested_depth(value, config.auto_recursion_depth_cap)
    resolved_depth = max(0, resolved_depth)
    return min(resolved_depth, max(0, config.max_depth))


def determine_view(
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
    override_view = apply_view_override(name, original_value, config.view_map)
    if override_view is not None:
        return override_view, True
    return choose_view(coerced_value), False
