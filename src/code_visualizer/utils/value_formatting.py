from __future__ import annotations

from html import escape as html_escape
from typing import Any


def dot_escape_label(value: str) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    return text


def table_cell_text(value: Any) -> str:
    return html_escape(str(value), quote=True)


def stable_svg_id(slot_name: str, *parts: Any) -> str:
    raw = "-".join(str(part) for part in (slot_name, *parts) if part is not None)
    normalized: list[str] = []
    for ch in raw:
        if ch.isalnum() or ch in {"_", "-"}:
            normalized.append(ch)
        else:
            normalized.append("-")
    cleaned = "".join(normalized).strip("-")
    if not cleaned:
        return "cv-code-visualizer-cell"
    return f"cv-{cleaned}"


def format_scalar_html(value: Any) -> str:
    text = html_escape(str(value))
    if text == "":
        text = "&#xa0;"
    return f'<font point-size="12" color="#0f172a">{text}</font>'


def format_container_stub(value: Any) -> str:
    def label(kind: str, extra: str | None = None) -> str:
        suffix = f" {extra}" if extra else ""
        return f'<font point-size="12" color="#475569">{kind}{suffix}</font>'

    if isinstance(value, (list, tuple, set, frozenset)):
        kind = type(value).__name__
        return label(kind, f"len={len(value)}")
    if isinstance(value, dict):
        return label("dict", f"keys={len(value)}")
    return label(type(value).__name__)


def estimate_visual_width(value: Any, max_items: int = 6, *, max_width: int = 920) -> int:
    """Estimate Graphviz HTML label width so sibling rows can share one width."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value)
        return min(max_width, max(54, 24 + len(text) * 9))

    if isinstance(value, dict):
        key_width, value_width = estimate_table_column_widths(list(value.items())[:max_items], max_items)
        return min(max_width, key_width + value_width + 56)

    if isinstance(value, (list, tuple)):
        visible = list(value)[:max_items]
        if not visible:
            return 64
        width = sum(estimate_visual_width(item, max_items, max_width=max_width) for item in visible)
        width += max(0, len(visible) - 1) * 18 + 24
        if len(value) > len(visible):
            width += 42
        return min(max_width, max(64, width))

    if isinstance(value, (set, frozenset)):
        visible = sorted(value, key=lambda item: str(item))[:max_items]
        if not visible:
            return 64
        width = sum(estimate_visual_width(item, max_items, max_width=max_width) for item in visible)
        width += max(0, len(visible) - 1) * 18 + 24
        if len(value) > len(visible):
            width += 42
        return min(max_width, max(64, width))

    return max(72, min(max_width, 24 + len(type(value).__name__) * 9))


def estimate_visual_height(value: Any, max_items: int = 6, *, max_height: int = 420) -> int:
    """Estimate Graphviz HTML label height for equal-sized sibling cells."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return 30

    if isinstance(value, dict):
        visible = list(value.items())[:max_items]
        row_count = max(1, len(visible))
        nested_extra = max(
            (estimate_visual_height(item, max_items, max_height=max_height) - 30 for _, item in visible),
            default=0,
        )
        return min(max_height, 34 + row_count * 28 + nested_extra)

    if isinstance(value, (list, tuple, set, frozenset)):
        visible = list(value)[:max_items] if not isinstance(value, (set, frozenset)) else sorted(value, key=lambda item: str(item))[:max_items]
        if not visible:
            return 34
        child_height = max(estimate_visual_height(item, max_items, max_height=max_height) for item in visible)
        # Include the nested array index row and table borders.
        return min(max_height, child_height + 34)

    return 34


def estimate_table_column_widths(items: list[tuple[Any, Any]], max_items: int = 6) -> tuple[int, int]:
    key_width = 92
    value_width = 92
    for key, val in items:
        key_text = str(key)
        key_width = max(key_width, min(220, 20 + len(key_text) * 9))
        value_width = max(value_width, estimate_visual_width(val, max_items))
    return key_width, min(920, value_width + 48)
