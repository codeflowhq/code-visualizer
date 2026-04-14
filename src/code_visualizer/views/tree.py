from __future__ import annotations

from typing import Any

from ..renderers import build_tree
from ..view_types import ViewKind
from .common import attach_view_title, merge_visual_graph, new_node_id


def build_tree_view(runtime: dict[str, Any], value: Any, name: str, depth: int) -> str:
    root_hint, tg = build_tree(
        value,
        name=name,
        max_nodes=runtime["item_limit"],
        nested_depth=depth,
        max_items=runtime["item_limit"],
    )
    prefix = new_node_id(runtime, ViewKind.TREE)
    merged_root = merge_visual_graph(runtime, tg, prefix, root_hint=root_hint)
    attach_view_title(runtime, merged_root, name, "tree_label")
    return merged_root
