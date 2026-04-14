"""Core view kind definitions and helper types."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, TypeVar, Union, overload


class ViewKind(str, Enum):
    """All supported visualization views."""

    AUTO = "auto"
    NODE_LINK = "node_link"
    ARRAY_CELLS = "array_cells"
    ARRAY_CELLS_NODE = "array_cells_node"  # compatibility alias
    MATRIX = "matrix"
    MATRIX_NODE = "matrix_node"  # compatibility alias
    IMAGE = "image"
    BAR = "bar"
    BAR_NODE = "bar_node"  # compatibility alias
    TABLE = "table"
    TABLE_NODE = "table_node"  # compatibility alias
    TREE = "tree"
    GRAPH = "graph"
    HEAP_DUAL = "heap_dual"
    HEAP_DUAL_NODE = "heap_dual_node"  # compatibility alias
    LINKED_LIST = "linked_list"
    LINKED_LIST_NODE = "linked_list_node"  # compatibility alias
    HASH_TABLE = "hash_table"
    HASH_TABLE_NODE = "hash_table_node"  # compatibility alias

    def __str__(self) -> str:  # pragma: no cover - Enum convenience
        return self.value


_ViewConvertible = TypeVar("_ViewConvertible", str, "ViewKind")


@overload
def ensure_view_kind(value: str) -> ViewKind:
    ...


@overload
def ensure_view_kind(value: ViewKind) -> ViewKind:
    ...


def ensure_view_kind(value: Union[str, ViewKind]) -> ViewKind:
    """Normalize arbitrary ViewKind literals into the Enum."""

    if isinstance(value, ViewKind):
        return value
    return ViewKind(value)


ViewOverrideMap = Mapping[str | type[Any], ViewKind]


__all__ = ["ViewKind", "ViewOverrideMap", "ensure_view_kind"]
