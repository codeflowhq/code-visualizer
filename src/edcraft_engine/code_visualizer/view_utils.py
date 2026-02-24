# view_utils.py
from __future__ import annotations

import base64
import tempfile
from dataclasses import dataclass
import io
from html import escape as html_escape
from pathlib import Path
from typing import Any, Mapping, Callable
from urllib.parse import unquote_to_bytes
from urllib.request import urlopen
from uuid import uuid4

from graphviz import Digraph, Source

from .view_types import ViewKind

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
_DATA_URI_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}
_ASCII_TMP_ROOT = Path(tempfile.gettempdir())
if any(ord(ch) > 127 for ch in str(_ASCII_TMP_ROOT)):
    _ASCII_TMP_ROOT = Path("/tmp")
_IMAGE_CACHE_DIR = (_ASCII_TMP_ROOT / "edcraft_viz_images").resolve()
_IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_TYPE_PATTERN_SAMPLE = 8
NestedRenderer = Callable[[Any, str, int], str | None]


class VisualizationImageError(RuntimeError):
    """Raised when image inputs for visualization are invalid."""


def dot_escape_label(s: str) -> str:
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    return s


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_list_numbers(x: Any) -> bool:
    return isinstance(x, list) and all(_is_number(v) for v in x)


def _is_dict(x: Any) -> bool:
    return isinstance(x, dict)


def _is_scalar_value(x: Any) -> bool:
    return isinstance(x, (str, int, float, bool)) or x is None


def _is_matrix_value(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) > 0
        and all(isinstance(row, (list, tuple)) for row in value)
    )


def _auto_nested_depth(value: Any, cap: int) -> int:
    capped = max(0, cap)

    def helper(obj: Any, depth: int) -> int:
        if depth >= capped:
            return capped
        if isinstance(obj, dict):
            if not obj:
                return depth
            best = depth
            for v in obj.values():
                best = max(best, helper(v, depth + 1))
            return best
        if isinstance(obj, (list, tuple, set, frozenset)):
            if not obj:
                return depth
            best = depth
            for item in obj:
                best = max(best, helper(item, depth + 1))
            return best
        return depth

    return helper(value, 0)


def _table_cell_text(x: Any) -> str:
    return html_escape(str(x), quote=True)


def _graphviz_array_block(value_cells: list[str], index_cells: list[str]) -> str:
    value_row = "".join(value_cells)
    index_row = "".join(index_cells)
    return (
        '<table border="0" cellborder="0" cellspacing="0">'
        '<tr><td>'
        '<table border="1" cellborder="1" cellspacing="0">'
        f'<tr>{value_row}</tr>'
        '</table>'
        '</td></tr>'
        '<tr><td>'
        '<table border="0" cellborder="0" cellspacing="4">'
        f'<tr>{index_row}</tr>'
        '</table>'
        '</td></tr>'
        '</table>'
    )


def _is_image_path(candidate: str) -> bool:
    lower = candidate.lower()
    return any(lower.endswith(ext) for ext in _IMAGE_EXTENSIONS)


def _looks_like_image_candidate(value: Any) -> bool:
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return False
        lower = candidate.lower()
        if lower.startswith("data:image/"):
            return True
        if (lower.startswith("http://") or lower.startswith("https://")) and _is_image_path(candidate):
            return True
        if _is_image_path(candidate):
            return True
        try:
            suffix = Path(candidate).suffix
        except Exception:
            return False
        return _is_image_path(suffix)
    if isinstance(value, Path):
        return _is_image_path(value.suffix)
    return False


def _assert_ascii_path(path: Path) -> None:
    path_str = str(path)
    if any(ord(ch) > 127 for ch in path_str):
        raise ValueError(
            f"Graphviz image paths must be ASCII-only; got non-ASCII path: {path_str}"
        )


def _write_cached_image(data: bytes, suffix: str) -> str:
    safe_suffix = suffix if suffix in _IMAGE_EXTENSIONS else ".img"
    target = _IMAGE_CACHE_DIR / f"img_{uuid4().hex}{safe_suffix}"
    target.write_bytes(data)
    return str(target)


def _materialize_data_uri(data_uri: str) -> str | None:
    header, sep, payload = data_uri.partition(",")
    if sep == "":
        return None
    if not header.startswith("data:image/"):
        return None
    mime_part = header[len("data:") :]
    parts = mime_part.split(";")
    mime = parts[0]
    is_base64 = any(part == "base64" for part in parts[1:])
    suffix = _DATA_URI_SUFFIX.get(mime, ".img")
    try:
        if is_base64:
            data = base64.b64decode(payload)
        else:
            data = unquote_to_bytes(payload)
    except Exception:
        return None
    return _write_cached_image(data, suffix)


def _download_remote_image(url: str) -> str | None:
    try:
        with urlopen(url, timeout=5) as resp:
            data = resp.read()
    except Exception:
        return None
    suffix = Path(url).suffix.lower()
    if suffix not in _IMAGE_EXTENSIONS:
        suffix = ".img"
    return _write_cached_image(data, suffix)


def _materialize_matplotlib_image(value: Any) -> str | None:
    try:
        from matplotlib.axes import Axes  # type: ignore
        from matplotlib.figure import Figure  # type: ignore
        from matplotlib.artist import Artist  # type: ignore
    except Exception:  # pragma: no cover - matplotlib optional
        Figure = Axes = Artist = None  # type: ignore

    fig: Any = None
    if Figure is not None and isinstance(value, Figure):
        fig = value
    elif Axes is not None and isinstance(value, Axes):
        fig = value.figure
    elif Artist is not None and isinstance(value, Artist):
        fig = getattr(value, "figure", None)
        if fig is None:
            axes = getattr(value, "axes", None)
            if axes is not None:
                fig = getattr(axes, "figure", None)

    if fig is None:
        return None

    buffer = io.BytesIO()
    try:
        fig.savefig(buffer, format="png", bbox_inches="tight")
    except Exception:
        return None
    data = buffer.getvalue()
    if not data:
        return None
    return _write_cached_image(data, ".png")


def _materialize_pil_image(value: Any) -> str | None:
    try:
        from PIL import Image  # type: ignore
    except Exception:  # pragma: no cover - pillow optional
        return None
    if not isinstance(value, Image.Image):
        return None
    buffer = io.BytesIO()
    fmt = (value.format or "PNG").upper()
    try:
        value.save(buffer, format=fmt)
    except Exception:
        return None
    data = buffer.getvalue()
    if not data:
        return None
    suffix = f".{fmt.lower()}" if f".{fmt.lower()}" in _IMAGE_EXTENSIONS else ".png"
    return _write_cached_image(data, suffix)


def _detect_image_source(value: Any, *, strict: bool = False) -> str | None:
    def _fail(detail: str) -> str | None:
        if strict:
            raise VisualizationImageError(detail)
        return None

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return _fail("Empty image path or URI")
        lower = candidate.lower()
        if lower.startswith("data:image"):
            cached = _materialize_data_uri(candidate)
            if cached is not None:
                return cached
            return _fail("Invalid data URI for image")
        if lower.startswith("http://") or lower.startswith("https://"):
            if not _is_image_path(candidate):
                return _fail("Remote image URLs must end with a known image extension")
            cached = _download_remote_image(candidate)
            if cached is not None:
                return cached
            return _fail("Failed to download remote image")
        if not _is_image_path(candidate):
            return _fail("String does not look like an image path")
        path = Path(candidate)
        if not path.exists() or not path.is_file():
            return _fail(f"Image file not found: {candidate}")
        if not _is_image_path(path.suffix):
            return _fail(f"Unsupported image extension: {path.suffix}")
        resolved = path.resolve()
        try:
            data = resolved.read_bytes()
        except OSError:
            return _fail(f"Failed to read image file: {candidate}")
        try:
            _assert_ascii_path(resolved)
            return str(resolved)
        except ValueError:
            return _write_cached_image(data, resolved.suffix.lower())
    if isinstance(value, Path):
        if not value.exists() or not value.is_file():
            return _fail(f"Image file not found: {value}")
        if not _is_image_path(value.suffix):
            return _fail(f"Unsupported image extension: {value.suffix}")
        resolved = value.resolve()
        try:
            data = resolved.read_bytes()
        except OSError:
            return _fail(f"Failed to read image file: {value}")
        try:
            _assert_ascii_path(resolved)
            return str(resolved)
        except ValueError:
            return _write_cached_image(data, resolved.suffix.lower())
    fig_src = _materialize_matplotlib_image(value)
    if fig_src is not None:
        return fig_src
    pil_src = _materialize_pil_image(value)
    if pil_src is not None:
        return pil_src
    return _fail(f"Unsupported image value type: {type(value).__name__}")


def _format_scalar_html(value: Any) -> str:
    text = html_escape(str(value))
    if text == "":
        text = "&#xa0;"
    return f'<font point-size="12" color="#0f172a">{text}</font>'


def _format_container_stub(value: Any) -> str:
    def label(kind: str, extra: str | None = None) -> str:
        suffix = f" {extra}" if extra else ""
        return f'<font point-size="12" color="#475569">{kind}{suffix}</font>'

    if isinstance(value, (list, tuple, set, frozenset)):
        kind = type(value).__name__
        return label(f"{kind}", f"len={len(value)}")
    if isinstance(value, dict):
        return label("dict", f"keys={len(value)}")
    return label(type(value).__name__)


def _image_html(src: str) -> str:
    safe_src = html_escape(src, quote=True)
    return (
        "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
        f"<tr><td><IMG SRC=\"{safe_src}\" SCALE=\"true\"/></td></tr>"
        "</table>"
    )


def _render_dot_to_image(dot_source: str, fmt: str = "png") -> str | None:
    """Render a DOT snippet to an image stored inside the ASCII-safe cache dir."""
    fmt_normalized = fmt.lower()
    if fmt_normalized == "jpeg":
        fmt_normalized = "jpg"
    if fmt_normalized not in {"png", "svg", "jpg"}:
        fmt_normalized = "png"
    try:
        src = Source(dot_source)
        src.format = fmt_normalized
        base = _IMAGE_CACHE_DIR / f"inline_{uuid4().hex}"
        rendered = Path(
            src.render(filename=base.name, directory=str(_IMAGE_CACHE_DIR), cleanup=True)
        )
        return str(rendered.with_suffix(f".{fmt_normalized}"))
    except Exception:
        return None


def _format_nested_value(
    value: Any,
    depth_remaining: int,
    max_items: int,
    nested_renderer: NestedRenderer | None = None,
    slot_name: str = "value",
) -> str:
    if nested_renderer is not None:
        nested_html = nested_renderer(value, slot_name, depth_remaining)
        if nested_html is not None:
            return nested_html

    img_src = _detect_image_source(value)
    if img_src is not None:
        return _image_html(img_src)

    inline_html = _format_inline_collection(
        value,
        depth_remaining,
        max_items,
        nested_renderer,
        slot_name,
    )
    if inline_html is not None:
        return inline_html

    if not _is_scalar_value(value):
        return _format_container_stub(value)

    return _format_scalar_html(value)


def _format_inline_collection(
    value: Any,
    depth_remaining: int,
    max_items: int,
    nested_renderer: NestedRenderer | None,
    slot_name: str,
) -> str | None:
    if depth_remaining <= 0:
        return None

    next_depth = depth_remaining - 1

    if _is_matrix_value(value):
        rows = [list(r) for r in value]  # type: ignore[arg-type]
        return _format_matrix_html(
            rows,
            next_depth,
            max_items,
            nested_renderer=nested_renderer,
            slot_name=slot_name,
            row_limit=max_items,
            col_limit=max_items,
        )

    seq: list[Any] | None = None
    if isinstance(value, (list, tuple)):
        seq = list(value)
    elif isinstance(value, (set, frozenset)):
        seq = sorted(value, key=lambda x: str(x))

    if seq is not None:
        n = len(seq)
        limit = min(n, max_items)
        value_cells: list[str] = []
        index_cells: list[str] = []
        for i in range(limit):
            cell_html = _format_nested_value(
                seq[i],
                next_depth,
                max_items,
                nested_renderer,
                f"{slot_name}[{i}]",
            )
            value_cells.append(f'<td align="center" bgcolor="#ffffff" cellpadding="4">{cell_html}</td>')
            index_cells.append(
                f'<td align="center"><font color="#dc2626" point-size="12">{html_escape(str(i))}</font></td>'
            )
        if n > max_items:
            value_cells.append('<td align="center" bgcolor="#ffffff">…</td>')
            index_cells.append('<td align="center"></td>')
        return _graphviz_array_block(value_cells, index_cells)

    if isinstance(value, dict):
        items = list(value.items())
        n = len(items)
        limit = min(n, max_items)
        rows: list[str] = []
        rows.append('<tr><td bgcolor="#e5e7eb"><b>Key</b></td><td bgcolor="#e5e7eb"><b>Value</b></td></tr>')
        if n == 0:
            rows.append('<tr><td colspan="2">∅</td></tr>')
        else:
            for idx in range(limit):
                k, v = items[idx]
                val_html = _format_nested_value(
                    v,
                    next_depth,
                    max_items,
                    nested_renderer,
                    f"{slot_name}.{_table_cell_text(k)}",
                )
                rows.append(f'<tr><td>{_table_cell_text(k)}</td><td>{val_html}</td></tr>')
            if n > max_items:
                rows.append('<tr><td colspan="2">… (+more)</td></tr>')
        return f'<table border="1" cellborder="1" cellspacing="0">{"".join(rows)}</table>'

    return None


def _bar_chart_html(values: list[float], labels: list[str], max_height_px: int = 160) -> str:
    if not values:
        return "<table border='1' cellborder='1' cellspacing='0'><tr><td>∅</td></tr></table>"

    max_abs = max(abs(v) for v in values)
    if max_abs == 0:
        max_abs = 1.0

    table: list[str] = ["<table border='0' cellborder='0' cellspacing='10'><tr>"]
    for label, val in zip(labels, values):
        norm = abs(val) / max_abs
        height = max(24, int(max_height_px * norm))
        gap = max(0, max_height_px - height)
        color = "#bae6fd" if val >= 0 else "#fecaca"
        value_text = int(val) if float(val).is_integer() else round(val, 2)
        inner = (
            "<table border='0' cellborder='0' cellspacing='0' cellpadding='0'>"
            f"<tr><td height='{gap}'></td></tr>"
            f"<tr><td bgcolor='{color}' width='34' height='{height}'></td></tr>"
            f"<tr><td align='center'><font point-size='11' color='#0f172a'>{value_text}</font></td></tr>"
            f"<tr><td align='center'><font point-size='9' color='#dc2626'>{html_escape(label)}</font></td></tr>"
            "</table>"
        )
        table.append(f"<td valign='bottom'>{inner}</td>")
    table.append("</tr></table>")
    return "".join(table)


def _format_value_label(
    value: Any,
    nested_depth: int,
    max_items: int,
    nested_renderer: NestedRenderer | None = None,
    slot_name: str = "value",
) -> tuple[str, bool]:
    image_src = _detect_image_source(value)
    if image_src is not None:
        return _image_html(image_src), True

    depth = max(0, nested_depth)
    html_depth: int | None
    if depth > 0:
        html_depth = depth
    elif _is_matrix_value(value):
        html_depth = 1
    elif isinstance(value, (list, tuple, set, frozenset, dict)):
        html_depth = 1
    else:
        html_depth = None

    if html_depth is not None:
        html = _format_nested_value(value, html_depth, max_items, nested_renderer, slot_name)
        return html, True
    return str(value), False


def _format_matrix_html(
    rows: list[list[Any]],
    depth_remaining: int,
    max_items: int,
    *,
    include_headers: bool = False,
    row_limit: int | None = None,
    col_limit: int | None = None,
    nested_renderer: NestedRenderer | None = None,
    slot_name: str = "matrix",
) -> str:
    depth_remaining = max(0, depth_remaining)
    total_rows = len(rows)
    width = max((len(r) for r in rows), default=0)
    limit_rows = min(total_rows, row_limit if row_limit is not None else total_rows)
    limit_rows = min(limit_rows, max_items)
    limit_cols = min(width, col_limit if col_limit is not None else width)
    limit_cols = min(limit_cols, max_items)
    table: list[str] = []
    table.append('<table border="1" cellborder="1" cellspacing="0">')

    def cell(val: Any) -> str:
        return _format_nested_value(val, depth_remaining, max_items, nested_renderer, slot_name)

    if include_headers:
        header_cells = ['<td bgcolor="#f3f4f6"></td>']
        for c in range(limit_cols):
            header_cells.append(f'<td bgcolor="#f3f4f6"><font color="#dc2626">{c}</font></td>')
        if width > limit_cols:
            header_cells.append('<td bgcolor="#f3f4f6">…</td>')
        table.append(f"<tr>{''.join(header_cells)}</tr>")

    for r_idx in range(limit_rows):
        row = rows[r_idx]
        cells: list[str] = []
        if include_headers:
            cells.append(f'<td bgcolor="#fef3c7"><font color="#b45309">{r_idx}</font></td>')
        for c_idx in range(limit_cols):
            val = row[c_idx] if c_idx < len(row) else ""
            cells.append(
                f"<td>{cell(val if c_idx < len(row) else '')}</td>"
            )
        if len(row) > limit_cols:
            cells.append("<td>…</td>")
        table.append(f"<tr>{''.join(cells)}</tr>")

    if total_rows > limit_rows:
        colspan = limit_cols + (1 if include_headers else 0)
        if width > limit_cols:
            colspan += 1
        table.append(f'<tr><td colspan="{max(1, colspan)}">… (+more rows)</td></tr>')

    table.append("</table>")
    return "".join(table)


def _digraph_edge(dot: Digraph, tail: str, head: str, **attrs: str) -> None:
    if ":" not in tail and ":" not in head:
        dot.edge(tail, head, **attrs)
        return

    attr_text = ""
    if attrs:
        attr_parts = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        attr_text = f" [{attr_parts}]"
    dot.body.append(f"  {tail} -> {head}{attr_text};")


def _try_networkx_edges_nodes(
    value: Any,
) -> tuple[list[tuple[Any, Mapping[str, Any]]], list[tuple[Any, Any, Mapping[str, Any]]], bool] | None:
    try:
        import networkx as nx  # type: ignore
    except Exception:
        return None

    if isinstance(value, nx.DiGraph) or isinstance(value, nx.MultiDiGraph):
        nodes = [(node, dict(data)) for (node, data) in value.nodes(data=True)]
        edges = [(u, v, dict(data)) for (u, v, data) in value.edges(data=True)]
        return nodes, edges, True

    if isinstance(value, nx.Graph) or isinstance(value, nx.MultiGraph):
        nodes = [(node, dict(data)) for (node, data) in value.nodes(data=True)]
        edges = [(u, v, dict(data)) for (u, v, data) in value.edges(data=True)]
        return nodes, edges, False

    return None


def _tree_children(value: Any) -> tuple[Any, list[Any]] | None:
    if hasattr(value, "left") or hasattr(value, "right"):
        label = getattr(value, "val", None)
        if label is None:
            label = getattr(value, "value", None)
        if label is None:
            label = type(value).__name__
        kids: list[Any] = []
        l = getattr(value, "left", None)
        r = getattr(value, "right", None)
        if l is not None:
            kids.append(l)
        if r is not None:
            kids.append(r)
        return label, kids

    if hasattr(value, "children"):
        try:
            ch = list(getattr(value, "children"))
        except Exception:
            ch = []
        label = getattr(value, "val", None)
        if label is None:
            label = getattr(value, "value", None)
        if label is None:
            label = type(value).__name__
        return label, ch

    if isinstance(value, Mapping) and "children" in value:
        try:
            ch = list(value.get("children") or [])
        except Exception:
            ch = []
        label = (
            value.get("label")
            or value.get("name")
            or value.get("val")
            or value.get("value")
            or value.get("board")
            or value.get("data")
        )
        if label is None:
            remainder = {k: v for k, v in value.items() if k != "children"}
            label = remainder if remainder else type(value).__name__
        return label, ch

    return None


def _extract_node_value(value: Any) -> Any:
    if hasattr(value, "val"):
        return getattr(value, "val")
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


def _collect_linked_list_labels(value: Any, max_nodes: int) -> tuple[list[Any], bool] | None:
    if value is None:
        return [], False
    if not hasattr(value, "next"):
        return None

    labels: list[Any] = []
    seen: set[int] = set()
    current = value
    truncated = False

    while current is not None and len(labels) < max_nodes:
        oid = id(current)
        if oid in seen:
            truncated = True
            break
        seen.add(oid)
        labels.append(_extract_node_value(current))
        current = getattr(current, "next", None)

    if current is not None:
        truncated = True

    return labels, truncated


def _looks_like_hash_table(value: Any) -> bool:
    if not isinstance(value, list):
        return False

    saw_bucket = False
    saw_empty = False

    for bucket in value:
        if bucket is None:
            saw_empty = True
            continue

        if hasattr(bucket, "next"):
            return True

        if isinstance(bucket, dict) or isinstance(bucket, set):
            saw_bucket = True
            continue

        if isinstance(bucket, (list, tuple)):
            if not bucket:
                saw_empty = True
                continue
            inner_pointer = any(hasattr(entry, "next") for entry in bucket)
            inner_pairs = any(isinstance(entry, (tuple, list)) and len(entry) == 2 for entry in bucket)
            if inner_pointer or inner_pairs:
                saw_bucket = True
                continue
            continue

    return saw_bucket and saw_empty


def _looks_like_graph_mapping(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    edges = value.get("edges")
    if not isinstance(edges, list):
        return False
    nodes = value.get("nodes")
    if isinstance(nodes, list):
        return True
    for entry in edges:
        if isinstance(entry, Mapping) and any(
            key in entry for key in ("source", "target", "from", "to", "src", "dst")
        ):
            return True
        if isinstance(entry, (tuple, list)) and len(entry) >= 2:
            return True
    return False


def _hash_bucket_entries(bucket: Any, max_items: int) -> tuple[list[Any], bool]:
    if bucket is None:
        return [], False

    entries: list[Any]
    truncated = False

    if isinstance(bucket, dict):
        entries = [f"{k}:{bucket[k]}" for k in bucket]
    elif isinstance(bucket, set):
        entries = sorted(bucket, key=lambda x: str(x))
    elif isinstance(bucket, (list, tuple)):
        entries = list(bucket)
    elif hasattr(bucket, "next"):
        seq = _collect_linked_list_labels(bucket, max_items)
        if seq is None:
            entries = [bucket]
        else:
            entries, truncated = seq
    else:
        entries = [bucket]

    if len(entries) > max_items:
        truncated = True
        entries = entries[:max_items]

    return entries, truncated


def _normalize_view_name(name: str) -> str:
    return "".join(ch for ch in name.strip() if not ch.isspace())


def _match_named_override(name: str, mapping: Mapping[str, ViewKind] | None) -> ViewKind | None:
    if not mapping:
        return None
    normalized = _normalize_view_name(name)
    for raw_key, view in mapping.items():
        if not isinstance(raw_key, str):
            continue
        if _normalize_view_name(raw_key) == normalized:
            return view
    return None


@dataclass(frozen=True)
class _TypePattern:
    kind: str
    args: tuple["_TypePattern", ...] = ()


_TYPE_PATTERN_CACHE: dict[str, _TypePattern] = {}


class _TypePatternParser:
    def __init__(self, text: str):
        self.text = text
        self.length = len(text)
        self.pos = 0

    def parse(self) -> _TypePattern:
        node = self._parse_pattern()
        self._skip_ws()
        if self.pos != self.length:
            raise ValueError(f"unexpected trailing characters at position {self.pos}")
        return node

    def _parse_pattern(self) -> _TypePattern:
        self._skip_ws()
        ident = self._parse_identifier()
        args: list[_TypePattern] = []
        self._skip_ws()
        if self._peek() == "[":
            self.pos += 1
            while True:
                self._skip_ws()
                if self._peek() == "]":
                    self.pos += 1
                    break
                args.append(self._parse_pattern())
                self._skip_ws()
                ch = self._peek()
                if ch == ",":
                    self.pos += 1
                    continue
                if ch == "]":
                    self.pos += 1
                    break
                raise ValueError(f"expected ',' or ']' at position {self.pos}")
        return _TypePattern(kind=ident, args=tuple(args))

    def _parse_identifier(self) -> str:
        self._skip_ws()
        start = self.pos
        while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in {"_", "."}):
            self.pos += 1
        if start == self.pos:
            raise ValueError(f"expected identifier at position {self.pos}")
        return self.text[start:self.pos].lower()

    def _skip_ws(self) -> None:
        while self.pos < self.length and self.text[self.pos].isspace():
            self.pos += 1

    def _peek(self) -> str | None:
        if self.pos >= self.length:
            return None
        return self.text[self.pos]


def _compile_type_pattern(spec: str) -> _TypePattern:
    key = spec.strip()
    if not key:
        raise ValueError("type pattern cannot be empty")
    cached = _TYPE_PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    parser = _TypePatternParser(key)
    try:
        pattern = parser.parse()
    except ValueError as exc:
        raise ValueError(f"invalid type pattern '{spec}': {exc}") from exc
    _TYPE_PATTERN_CACHE[key] = pattern
    return pattern


def _sample_iterable(seq: Any, limit: int) -> list[Any]:
    if limit <= 0:
        return []
    if isinstance(seq, list):
        return seq[:limit]
    if isinstance(seq, tuple):
        return list(seq[:limit])
    sample: list[Any] = []
    for item in seq:
        sample.append(item)
        if len(sample) >= limit:
            break
    return sample


def _matches_type_pattern(value: Any, pattern: _TypePattern) -> bool:
    kind = pattern.kind
    if kind in {"any", "object"}:
        return True
    if kind == "none":
        return value is None
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return isinstance(value, float)
    if kind == "number":
        return _is_number(value)
    if kind == "str":
        return isinstance(value, str)
    if kind == "bytes":
        return isinstance(value, (bytes, bytearray))
    if kind == "path":
        return isinstance(value, Path)
    if kind == "list":
        if not isinstance(value, list):
            return False
        if not pattern.args:
            return True
        child = pattern.args[0]
        sampled = _sample_iterable(value, _TYPE_PATTERN_SAMPLE)
        return all(_matches_type_pattern(item, child) for item in sampled)
    if kind == "tuple":
        if not isinstance(value, tuple):
            return False
        if not pattern.args:
            return True
        if len(pattern.args) == len(value) and len(pattern.args) > 1:
            return all(_matches_type_pattern(item, sub) for item, sub in zip(value, pattern.args))
        child = pattern.args[0]
        sampled = _sample_iterable(value, _TYPE_PATTERN_SAMPLE)
        return all(_matches_type_pattern(item, child) for item in sampled)
    if kind == "set":
        if not isinstance(value, set):
            return False
        if not pattern.args:
            return True
        child = pattern.args[0]
        sampled = _sample_iterable(value, _TYPE_PATTERN_SAMPLE)
        return all(_matches_type_pattern(item, child) for item in sampled)
    if kind == "frozenset":
        if not isinstance(value, frozenset):
            return False
        if not pattern.args:
            return True
        child = pattern.args[0]
        sampled = _sample_iterable(value, _TYPE_PATTERN_SAMPLE)
        return all(_matches_type_pattern(item, child) for item in sampled)
    if kind == "dict":
        if not isinstance(value, dict):
            return False
        if not pattern.args:
            return True
        sampled_items = _sample_iterable(value.items(), _TYPE_PATTERN_SAMPLE)
        if len(pattern.args) == 1:
            val_pattern = pattern.args[0]
            return all(_matches_type_pattern(val, val_pattern) for _, val in sampled_items)
        key_pattern, val_pattern = pattern.args[0], pattern.args[1]
        return all(
            _matches_type_pattern(k, key_pattern) and _matches_type_pattern(v, val_pattern)
            for k, v in sampled_items
        )
    if kind == "linked_list":
        return _collect_linked_list_labels(value, max_nodes=2) is not None
    if kind == "tree":
        return _tree_children(value) is not None
    return False


def _match_type_pattern_override(value: Any, mapping: Mapping[str, ViewKind] | None) -> ViewKind | None:
    if not mapping:
        return None
    if _looks_like_image_candidate(value):
        return None
    for pattern_text, view in mapping.items():
        try:
            pattern = _compile_type_pattern(pattern_text)
        except ValueError as exc:
            raise ValueError(f"Invalid DEFAULT_VIEW_TYPE_MAP entry '{pattern_text}': {exc}") from exc
        if _matches_type_pattern(value, pattern):
            return view
    return None
