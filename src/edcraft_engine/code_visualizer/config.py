# config.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .graph_builder import ViewKind

"""
Visualization mapper configuration
----------------------------------
The graph builder resolves a view in this order:
1. `DEFAULT_VIEW_NAME_MAP`: exact variable names or dotted/index paths.
2. `DEFAULT_VIEW_TYPE_MAP`: lightweight structural patterns (see doc below).
3. `DEFAULT_VIEW_MAP`: legacy isinstance overrides.
4. Automatic chooser in `renderers.choose_view`.

Available ViewKind literals (see README for detailed examples):
    array_cells, matrix, image, bar, table, tree, graph,
    heap_dual, linked_list, hash_table, node_link (fallback).

Type-pattern syntax:
    pattern := atom ["[" pattern {"," pattern} "]"]
    atom    := list | tuple | set | frozenset | dict | int | float
               | bool | number | str | bytes | path | any | none
               | linked_list | tree
Examples:
    "list[number]"          -> homogeneous numeric array
    "tuple[list]"           -> tuple whose elements are lists
    "dict[str, any]"        -> mapping with string keys
    "linked_list"           -> objects exposing `.next`
    "tree"                  -> nodes with `.left/.right` or `.children`

You can edit the dictionaries below (or mutate them at runtime) to
customize default renderings for your own datasets.
"""

# Default mapping for overriding visualization views (legacy support).
# Keys can be variable names (str) or Python types; values must be a ViewKind.
DEFAULT_VIEW_MAP: dict[str | type[Any], "ViewKind"] = {}

# Name-based overrides keyed by variable names or simple index/key paths such as
# "profile.history[0].scores". Whitespace inside the key is ignored when matching.
DEFAULT_VIEW_NAME_MAP: dict[str, "ViewKind"] = {}

# Type-pattern overrides keyed by lightweight structural descriptions. Patterns
# support nested brackets plus the atoms: list, tuple, set, dict, int, float,
# bool, str, number, path, any, none. They are evaluated in insertion order.
# The defaults below replicate the legacy auto-view heuristics.
# Empty by default; add your own pattern overrides here. The runtime still
# falls back to automatic heuristics defined in `renderers._AUTO_VIEW_TYPE_MAP`.
DEFAULT_VIEW_TYPE_MAP: dict[str, "ViewKind"] = {}

# Default maximum nested depth for recursive list/dict rendering. Depth is counted
# as "how many levels below the top-level view should still expand". 0 disables
# nested rendering and falls back to scalar text. Use a negative value to enable
# automatic inference (bounded by AUTO_NESTED_DEPTH_CAP).
DEFAULT_NESTED_DEPTH: int = -1

# Optional per-variable/per-type overrides for nested depth. Takes precedence over
# DEFAULT_NESTED_DEPTH but can be overridden at call time via visualize(...).
# Provide sensible defaults for common container types so nested structures stay
# inline unless a caller explicitly opts out.
NESTED_DEPTH_MAP: dict[str | type[Any], int] = {
    list: 4,
    tuple: 4,
    dict: 4,
}

# Safety cap for automatically inferred nested depth (only used when the resolved
# depth is negative). Prevents runaway recursion for pathological inputs.
AUTO_NESTED_DEPTH_CAP: int = 6

# Default artifact render format ("svg", "png", or "jpg") used by demos/helpers.
DEFAULT_OUTPUT_FORMAT: str = "png"
ALLOWED_OUTPUT_FORMATS: set[str] = {"svg", "png", "jpg"}
