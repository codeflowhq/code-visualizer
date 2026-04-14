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
