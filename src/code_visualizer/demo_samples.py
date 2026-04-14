from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STEP_TRACER_SNIPPET = """
data = [7, 3, 5, 1]
for i in range(len(data)):
    swapped = False
    for j in range(0, len(data) - i - 1):
        if data[j] > data[j + 1]:
            data[j], data[j + 1] = data[j + 1], data[j]
            swapped = True
    if not swapped:
        break
"""

STEP_TRACER_BFS_SNIPPET = """
graph = {
    "A": ["B", "C"],
    "B": ["D"],
    "C": ["E", "F"],
    "D": [],
    "E": [],
    "F": [],
}
queue = ["A"]
visited = []
queue_state = queue[:]
visited_nodes = visited[:]
while queue:
    node = queue.pop(0)
    if node in visited:
        continue
    visited.append(node)
    for neighbor in graph.get(node, []):
        if neighbor not in visited and neighbor not in queue:
            queue.append(neighbor)
    queue_state = queue[:]
    visited_nodes = visited[:]
"""

STEP_TRACER_DP_SNIPPET = """
weights = [2, 3, 1, 4]
target = 6
dp = [[0] * (target + 1) for _ in range(len(weights) + 1)]
dp_matrix = [row[:] for row in dp]
for i, weight in enumerate(weights, start=1):
    for capacity in range(target + 1):
        dp[i][capacity] = dp[i - 1][capacity]
    for capacity in range(weight, target + 1):
        candidate = dp[i - 1][capacity - weight] + weight
        if candidate > dp[i][capacity]:
            dp[i][capacity] = candidate
    dp_matrix = [row[:] for row in dp]
"""

STEP_TRACER_GRAPH_SNIPPET = """
adjacency = {
    "A": ["B", "C"],
    "B": ["D"],
    "C": ["E", "F"],
    "D": [],
    "E": [],
    "F": [],
}
queue = ["A"]
visited = []
spanning_edges = []
while queue:
    node = queue.pop(0)
    if node in visited:
        continue
    visited.append(node)
    for neighbor in adjacency.get(node, []):
        spanning_edges.append((node, neighbor))
        if neighbor not in visited and neighbor not in queue:
            queue.append(neighbor)
    graph_snapshot = {
        "nodes": [{"id": v, "value": {"label": v}} for v in visited],
        "edges": [{"source": src, "target": dst, "label": "edge"} for src, dst in spanning_edges],
        "directed": False,
    }
"""

STEP_TRACER_CASES: tuple[dict[str, Any], ...] = (
    {"label": "Bubble sort array states", "snippet": STEP_TRACER_SNIPPET, "watch": ["data"], "max_events": 6, "max_steps": 4, "stem": "step_trace_sort"},
    {"label": "BFS frontier + visited nodes", "snippet": STEP_TRACER_BFS_SNIPPET, "watch": ["queue_state", "visited_nodes"], "max_events": 12, "max_steps": 5, "stem": "step_trace_bfs"},
    {"label": "0/1 knapsack DP table", "snippet": STEP_TRACER_DP_SNIPPET, "watch": ["dp_matrix"], "max_events": 12, "max_steps": 5, "stem": "step_trace_dp"},
    {"label": "BFS spanning tree graph", "snippet": STEP_TRACER_GRAPH_SNIPPET, "watch": ["graph_snapshot"], "max_events": 10, "max_steps": 5, "stem": "step_trace_graph"},
)


@dataclass
class Node:
    val: Any
    left: Node | None = None
    right: Node | None = None


@dataclass
class ListNode:
    val: Any
    next: ListNode | None = None


def build_tree_demo() -> Node:
    return Node(5, left=Node(3, left=Node(1), right=Node(4)), right=Node(8, right=Node(9)))


def bubble_sort_frames(arr: list[int]) -> list[tuple[str, list[int]]]:
    a = arr[:]
    frames: list[tuple[str, list[int]]] = [("start", a[:])]
    n = len(a)
    for i in range(n):
        for j in range(0, n - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                frames.append((f"swap {j}<->{j+1}", a[:]))
    frames.append(("done", a[:]))
    return frames


def build_linked_list(values: list[Any]) -> ListNode | None:
    head: ListNode | None = None
    for value in reversed(values):
        head = ListNode(value, head)
    return head
