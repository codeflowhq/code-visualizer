from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def _try_networkx_edges_nodes(
    value: Any,
) -> tuple[list[tuple[Any, dict[Any, Any]]], list[tuple[Any, Any, dict[Any, Any]]], bool] | None:
    try:
        import networkx as nx  # type: ignore
    except Exception:
        return None

    if isinstance(value, (nx.DiGraph, nx.MultiDiGraph)):
        nodes = [(node, dict(data)) for (node, data) in value.nodes(data=True)]
        edges = [(u, v, dict(data)) for (u, v, data) in value.edges(data=True)]
        return nodes, edges, True

    if isinstance(value, (nx.Graph, nx.MultiGraph)):
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
        left_child = getattr(value, "left", None)
        right_child = getattr(value, "right", None)
        if left_child is not None:
            kids.append(left_child)
        if right_child is not None:
            kids.append(right_child)
        return label, kids

    if hasattr(value, "children"):
        try:
            children = list(value.children)
        except Exception:
            children = []
        label = getattr(value, "val", None)
        if label is None:
            label = getattr(value, "value", None)
        if label is None:
            label = type(value).__name__
        return label, children

    if isinstance(value, Mapping) and "children" in value:
        try:
            children = list(value.get("children") or [])
        except Exception:
            children = []
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
        return label, children

    return None


def _extract_node_value(value: Any) -> Any:
    if hasattr(value, "val"):
        return value.val
    if hasattr(value, "value"):
        return value.value
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
        object_id = id(current)
        if object_id in seen:
            truncated = True
            break
        seen.add(object_id)
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
        if isinstance(bucket, (dict, set)):
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
        if isinstance(entry, Mapping) and any(key in entry for key in ("source", "target", "from", "to", "src", "dst")):
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
        entries = [bucket] if seq is None else seq[0]
        truncated = False if seq is None else seq[1]
    else:
        entries = [bucket]

    if len(entries) > max_items:
        truncated = True
        entries = entries[:max_items]
    return entries, truncated
