from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ....utils.value_formatting import (
    estimate_table_column_widths as _estimate_table_column_widths,
)
from ....utils.value_formatting import table_cell_text as _table_cell_text
from ....utils.value_formatting.table_sizes import _estimate_inline_preview_width
from ....utils.value_shapes import _is_scalar_value
from ...shared.theme import BG_HEADER_MUTED
from ..labels import html_cell, html_row, html_table

FormatNestedValue = Callable[[Any, int, int, Any, str], str]
ColumnWidthOverrides = dict[str, int]


def dict_html(
    value: dict[object, object],
    next_depth: int,
    max_items: int,
    nested_renderer: Any,
    slot_name: str,
    format_nested_value: FormatNestedValue,
    *,
    key_width_override: int | None = None,
    value_width_overrides: ColumnWidthOverrides | None = None,
) -> str:
    def _is_inline_value(html: str) -> bool:
        return not html.lstrip().startswith("<table")

    items = list(value.items())
    limit = min(len(items), max_items)
    key_width, value_width = _estimate_table_column_widths(items[:limit], max_items)
    if key_width_override is not None:
        key_width = max(key_width, key_width_override)
    if value_width_overrides is not None:
        normalized_value_width = max(
            (
                value_width_overrides.get(
                    _table_cell_text(key),
                    _estimate_inline_preview_width(item_value, max_items),
                )
                for key, item_value in items[:limit]
            ),
            default=value_width,
        )
        value_width = max(value_width, normalized_value_width)
    rows = [
        html_row(
            html_cell(
                "<b>Key</b>",
                width=key_width,
                bgcolor=BG_HEADER_MUTED,
                align="center",
            ),
            html_cell(
                "<b>Value</b>",
                width=value_width,
                bgcolor=BG_HEADER_MUTED,
                align="center",
            ),
        )
    ]
    if not items:
        rows.append(html_row(html_cell("∅", colspan="2")))
    else:
        for key, item_value in items[:limit]:
            key_text = _table_cell_text(key)
            value_html = format_nested_value(
                item_value,
                next_depth,
                max_items,
                nested_renderer,
                f"{slot_name}.{key_text}",
            )
            is_inline_value = _is_scalar_value(item_value) or _is_inline_value(value_html)
            value_align = "center" if is_inline_value else "left"
            value_padding = "2" if is_inline_value else "0"
            rows.append(
                html_row(
                    html_cell(key_text, width=key_width, align="center"),
                    html_cell(
                        value_html,
                        width=value_width,
                        align=value_align,
                        cellpadding=value_padding,
                    ),
                )
            )
        if len(items) > max_items:
            rows.append(html_row(html_cell("… (+more)", colspan="2")))
    return html_table(*rows, border="1", cellborder="1", cellspacing="0")
