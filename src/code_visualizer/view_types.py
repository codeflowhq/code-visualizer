"""Core view kind definitions and helper types."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, TypeVar, Union, overload


class ViewKind(str, Enum):
    """All supported visualization views."""

    AUTO = "auto"
    NODE_LINK = "node_link"
    ARRAY_CELLS = "array_cells"
    MATRIX = "matrix"
    IMAGE = "image"
    BAR = "bar"
    TABLE = "table"
    TREE = "tree"
    GRAPH = "graph"
    HEAP_DUAL = "heap_dual"
    LINKED_LIST = "linked_list"
    HASH_TABLE = "hash_table"

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
