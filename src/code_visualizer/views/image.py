from __future__ import annotations

from typing import Any

from ..models import NodeKind, VisualNode
from ..view_types import ViewKind
from ..view_utils import _detect_image_source, _image_html


def build_image_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    del depth
    src = _detect_image_source(value, strict=True)
    if src is None:
        raise TypeError("image view expects a valid image source")
    node_id = f"{ViewKind.IMAGE}_{next(runtime['counter'])}"
    html = (
        "<table border='0' cellborder='0' cellspacing='2'>"
        f"<tr><td align='center'><font point-size='16'><b>{name}</b></font></td></tr>"
        f"<tr><td>{_image_html(src)}</td></tr>"
        "</table>"
    )
    runtime["graph"].add_node(VisualNode(node_id, NodeKind.OBJECT, html, {"html_label": True, "node_attrs": {"shape": "plain"}}))
    return node_id
