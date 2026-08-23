from __future__ import annotations

from typing import Any

from .size_estimates import estimate_visual_width


def _estimate_inline_scalar_width(value: object) -> int:
    text = str(value)
    return min(220, max(34, 18 + len(text) * 9))


def _estimate_inline_preview_width(value: Any, max_items: int = 6) -> int:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _estimate_inline_scalar_width(value)

    if isinstance(value, dict):
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

    if isinstance(value, (list, tuple)):
        visible = list(value)[:max_items]
        if not visible:
            return 64
        width = sum(_estimate_inline_preview_width(item, max_items) for item in visible)
        if any(not isinstance(item, (str, int, float, bool)) and item is not None for item in visible):
            width += (len(visible) * 8) + 8
        if len(value) > len(visible):
            width += 34
        return min(920, max(64, width))

    if isinstance(value, (set, frozenset)):
        visible = sorted(value, key=lambda item: str(item))[:max_items]
        if not visible:
            return 64
        width = sum(_estimate_inline_preview_width(item, max_items) for item in visible)
        if any(not isinstance(item, (str, int, float, bool)) and item is not None for item in visible):
            width += (len(visible) * 8) + 8
        if len(value) > len(visible):
            width += 34
        return min(920, max(64, width))

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
