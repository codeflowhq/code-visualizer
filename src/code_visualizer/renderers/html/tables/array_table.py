from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ....utils.value_formatting import stable_svg_id as _stable_svg_id
from ....utils.value_formatting import table_cell_text as _table_cell_text
from ....utils.value_formatting.table_sizes import _estimate_inline_preview_width
from ...shared.theme import BG_SURFACE, INDEX_FONT_SIZE, TEXT_INDEX
from ..labels import html_cell, html_font, html_row, html_table

FormatNestedValue = Callable[[Any, int, int, Any, str], str]


def _is_dict_sequence(sequence: list[object]) -> bool:
    return bool(sequence) and all(isinstance(item, dict) for item in sequence)


def _normalized_dict_sequence_widths(
    sequence: list[object], max_items: int
) -> tuple[int, dict[str, int]] | None:
    visible = sequence[:max_items]
    if not _is_dict_sequence(visible):
        return None

    key_width = 92
    value_widths: dict[str, int] = {}
    for item in visible:
        current = item if isinstance(item, dict) else {}
        for key, value in current.items():
            key_text = _table_cell_text(key)
            key_width = max(key_width, min(220, 20 + len(key_text) * 9))
            value_widths[key_text] = max(
                value_widths.get(key_text, 92),
                _estimate_inline_preview_width(value, max_items),
            )
    return key_width, value_widths


def graphviz_array_block(
    value_cells: list[str],
    index_cells: list[str],
    *,
    slot_name: str = "array",
) -> str:
    value_row = (
        html_cell(
            "&nbsp;", id=_stable_svg_id(slot_name, "value", "empty"), align="center"
        )
        if not value_cells
        else "".join(value_cells)
    )
    index_row = (
        html_cell(
            "&nbsp;", id=_stable_svg_id(slot_name, "index", "empty"), align="center"
        )
        if not index_cells
        else "".join(index_cells)
    )
    value_table = html_table(
        html_row(value_row, id=_stable_svg_id(slot_name, "value-row")),
        id=_stable_svg_id(slot_name, "value-table"),
        border="1",
        cellborder="1",
        cellspacing="0",
    )
    index_table = html_table(
        html_row(index_row, id=_stable_svg_id(slot_name, "index-row")),
        id=_stable_svg_id(slot_name, "index-table"),
        border="0",
        cellborder="0",
        cellspacing="0",
    )
    return html_table(
        html_row(
            html_cell(
                value_table, id=_stable_svg_id(slot_name, "value-table-container")
            )
        ),
        html_row(
            html_cell(
                index_table, id=_stable_svg_id(slot_name, "index-table-container")
            )
        ),
        id=_stable_svg_id(slot_name, "wrapper"),
        border="0",
        cellborder="0",
        cellspacing="0",
    )


def sequence_html(
    sequence: list[object],
    next_depth: int,
    max_items: int,
    nested_renderer: Any,
    slot_name: str,
    format_nested_value: FormatNestedValue,
) -> str:
    limit = min(len(sequence), max_items)
    normalized_widths = _normalized_dict_sequence_widths(sequence, max_items)
    value_cells: list[str] = []
    index_cells: list[str] = []
    for index in range(limit):
        item = sequence[index]
        item_slot = f"{slot_name}[{index}]"
        if normalized_widths is not None and isinstance(item, dict):
            from .dict_table import dict_html

            key_width_override, value_width_overrides = normalized_widths
            cell_html = dict_html(
                item,
                max(0, next_depth - 1),
                max_items,
                nested_renderer,
                item_slot,
                format_nested_value,
                key_width_override=key_width_override,
                value_width_overrides=value_width_overrides,
            )
        else:
            cell_html = format_nested_value(
                item,
                next_depth,
                max_items,
                nested_renderer,
                item_slot,
            )
        value_cells.append(
            html_cell(cell_html, align="center", bgcolor=BG_SURFACE, cellpadding="2")
        )
        index_cells.append(
            html_cell(
                html_font(
                    str(index), {"color": TEXT_INDEX, "point-size": INDEX_FONT_SIZE}
                ),
                align="center",
            )
        )
    if len(sequence) > max_items:
        value_cells.append(html_cell("…", align="center", bgcolor=BG_SURFACE))
        index_cells.append(html_cell("", align="center"))
    return graphviz_array_block(value_cells, index_cells, slot_name=slot_name)
