# view_types.py
from __future__ import annotations

from typing import Any, Literal, Mapping

ViewKind = Literal[
    "auto",
    "node_link",      # generic VisualIR node-link
    "array_cells",    # list -> array cells
    "matrix",         # 2D list -> matrix grid
    "image",          # scalar image
    "bar",            # list[number] -> bar chart (xychart-beta)
    "table",          # dict -> table-like
    "tree",           # tree -> rooted layout
    "graph",          # graph -> static node-edge (no force)
    "heap_dual",      # heap list -> array + binary tree dual
    "linked_list",    # linked list -> pointer chain
    "hash_table",     # hash table buckets + chains
]

ViewOverrideMap = Mapping[str | type[Any], ViewKind]
