from __future__ import annotations

from typing import Any

from .size_estimates import estimate_visual_width

SCALAR_TYPES = (str, int, float, bool)


def _estimate_inline_scalar_width(value: object) -> int:
    text = str(value)
    return min(220, max(34, 18 + len(text) * 9))


def _is_scalar_like(value: Any) -> bool:
    return isinstance(value, SCALAR_TYPES) or value is None


def _add_nested_sequence_padding(
    width: int, visible: list[Any], total_count: int, visible_count: int
) -> int:
    padded_width = width
    if any(not _is_scalar_like(item) for item in visible):
        padded_width += (visible_count * 8) + 8
    if total_count > visible_count:
        padded_width += 34
    return min(920, max(64, padded_width))


def _estimate_inline_mapping_width(value: dict[Any, Any], max_items: int) -> int:
    items = list(value.items())[:max_items]
    if not items:
        return 64
    key_width = 92
    value_width = 92
    for key, item_value in items:
        key_text = str(key)
        key_width = max(key_width, min(220, 20 + len(key_text) * 9))
        value_width = max(
            value_width,
            _estimate_inline_preview_width(item_value, max_items),
        )
    return min(920, key_width + value_width)


def _estimate_inline_sequence_width(sequence: list[Any], max_items: int) -> int:
    visible = sequence[:max_items]
    if not visible:
        return 64
    width = sum(_estimate_inline_preview_width(item, max_items) for item in visible)
    return _add_nested_sequence_padding(width, visible, len(sequence), len(visible))


def _estimate_inline_preview_width(value: Any, max_items: int = 6) -> int:
    if _is_scalar_like(value):
        return _estimate_inline_scalar_width(value)

    if isinstance(value, dict):
        return _estimate_inline_mapping_width(value, max_items)

    if isinstance(value, (list, tuple)):
        return _estimate_inline_sequence_width(list(value), max_items)

    if isinstance(value, (set, frozenset)):
        return _estimate_inline_sequence_width(
            sorted(value, key=lambda item: str(item)),
            max_items,
        )

    return estimate_visual_width(value, max_items)


def estimate_table_column_widths(
    items: list[tuple[Any, Any]], max_items: int = 6
) -> tuple[int, int]:
    key_width = 92
    value_width = 92
    for key, val in items:
        key_text = str(key)
        key_width = max(key_width, min(220, 20 + len(key_text) * 9))
        value_width = max(value_width, _estimate_inline_preview_width(val, max_items))
    return key_width, min(920, value_width)
