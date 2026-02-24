# demo.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Any

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional
    np = None  # type: ignore

from graphviz import Source

from edcraft_engine.code_visualizer import config as viz_config
from edcraft_engine.code_visualizer.graph_builder import visualize
from edcraft_engine.code_visualizer.view_types import ViewKind


# -----------------------------
# Tree demo structure
# -----------------------------

@dataclass
class Node:
    val: Any
    left: "Node | None" = None
    right: "Node | None" = None

@dataclass
class ListNode:
    val: Any
    next: "ListNode | None" = None


def build_tree_demo() -> Node:
    #     5
    #    / \
    #   3   8
    #  / \   \
    # 1   4   9
    return Node(
        5,
        left=Node(3, left=Node(1), right=Node(4)),
        right=Node(8, right=Node(9)),
    )


# -----------------------------
# Sorting trace (static frames) demo
# Stage 1: just print a few static frames (no HTML/JS)
# -----------------------------

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


def build_tictactoe_tree() -> Any:
    """
    Create a small tic-tac-toe search tree showcasing board state per node,
    using plain dict/list nodes whose values are raw 3x3 grids.
    """

    x_corner = {
        "board": [["X", "", ""], ["", "", ""], ["", "", ""]],
        "children": [
            {"board": [["X", "", ""], ["", "", "O"], ["", "", ""]], "children": []},
            {"board": [["X", "", "O"], ["", "", ""], ["", "", ""]], "children": []},
        ],
    }
    x_center = {
        "board": [["", "", ""], ["", "X", ""], ["", "", ""]],
        "children": [
            {"board": [["", "", "O"], ["", "X", ""], ["", "", ""]], "children": []},
            {"board": [["", "", ""], ["", "X", ""], ["O", "", ""]], "children": []},
        ],
    }
    x_bottom = {
        "board": [["", "", ""], ["", "", ""], ["", "", "X"]],
        "children": [
            {"board": [["O", "", ""], ["", "", ""], ["", "", "X"]], "children": []},
            {"board": [["", "", ""], ["", "O", ""], ["", "", "X"]], "children": []},
        ],
    }
    return {
        "board": [["", "", ""], ["", "", ""], ["", "", ""]],
        "children": [
            x_corner,
            x_center,
            x_bottom,
        ],
    }


def build_shortest_path_usecase() -> dict[str, Any]:
    """Synthetic Dijkstra-style trace combining graph, queue frames, and tree."""
    graph = {
        "nodes": [
            {"id": "A", "value": {"label": "Start", "h": 5}},
            {"id": "B", "value": {"label": "B", "h": 3}},
            {"id": "C", "value": {"label": "C", "h": 2}},
            {"id": "D", "value": {"label": "Goal", "h": 0}},
            {"id": "E", "value": {"label": "E", "h": 4}},
        ],
        "edges": [
            ("A", "B", "2"),
            ("A", "C", "4"),
            ("B", "C", "1"),
            ("B", "D", "7"),
            ("C", "D", "3"),
            ("B", "E", "2"),
            ("E", "D", "2"),
        ],
        "directed": True,
    }
    frontier_frames = [
        {"iter": 0, "frontier": [{"node": "A", "dist": 0}], "visited": []},
        {
            "iter": 1,
            "frontier": [{"node": "B", "dist": 2}, {"node": "C", "dist": 4}],
            "visited": ["A"],
            "relaxations": [{"edge": "A->B", "new": 2}, {"edge": "A->C", "new": 4}],
        },
        {
            "iter": 2,
            "frontier": [{"node": "C", "dist": 3}, {"node": "E", "dist": 4}, {"node": "D", "dist": 9}],
            "visited": ["A", "B"],
            "relaxations": [
                {"edge": "B->C", "new": 3},
                {"edge": "B->E", "new": 4},
                {"edge": "B->D", "new": 9},
            ],
        },
        {
            "iter": 3,
            "frontier": [{"node": "E", "dist": 4}, {"node": "D", "dist": 6}],
            "visited": ["A", "B", "C"],
            "relaxations": [{"edge": "C->D", "new": 6}],
        },
        {
            "iter": 4,
            "frontier": [{"node": "D", "dist": 6}],
            "visited": ["A", "B", "C", "E"],
            "relaxations": [{"edge": "E->D", "new": 6}],
        },
        {"iter": 5, "frontier": [], "visited": ["A", "B", "C", "E", "D"], "done": True},
    ]
    dist_table = {
        "A": {"dist": 0, "prev": None},
        "B": {"dist": 2, "prev": "A"},
        "C": {"dist": 3, "prev": "B"},
        "E": {"dist": 4, "prev": "B"},
        "D": {"dist": 6, "prev": "C"},
    }
    path_tree = {
        "label": "A",
        "children": [
            {
                "label": "B (2)",
                "children": [
                    {"label": "C (3)", "children": [{"label": "D (6)", "children": []}]},
                    {"label": "E (4)", "children": [{"label": "D (6)", "children": []}]},
                ],
            }
        ],
    }
    return {
        "graph": graph,
        "frontier_frames": frontier_frames,
        "best_dist": dist_table,
        "path_tree": path_tree,
    }


OUTPUT_DIR = Path(__file__).with_name("demo_outputs")


def set_view_override(name: str, view: ViewKind) -> None:
    """Register/replace a mapper entry so visualize() stays config-driven."""
    viz_config.DEFAULT_VIEW_NAME_MAP[name] = view


def configure_demo_view_overrides() -> None:
    """Demonstrate the new mapper: clear defaults, then add name & type rules."""
    viz_config.DEFAULT_VIEW_MAP.clear()
    viz_config.DEFAULT_VIEW_NAME_MAP.clear()
    viz_config.NESTED_DEPTH_MAP.clear()
    # 保留 config.py 的 DEFAULT_VIEW_TYPE_MAP，示例仅通过 name override 控制视图。
    overrides: dict[str, ViewKind] = {
        "arr": "array_cells",
        "arr_bar": "bar",
        "linked": "linked_list",
        "hash_table": "hash_table",
        "metrics": "table",
        "T": "tree",
        "tic_tac_toe": "tree",
        "heap": "heap_dual",
        "nested": "array_cells",
        "tuple_block": "array_cells",
        "avatar_img": "image",
        "profile": "table",
        "matrix_demo": "matrix",
        "np_values": "array_cells",
        "nested_demo": "array_cells",
        "graph_demo": "graph",
        "combo": "array_cells",
        "combo[0].tree": "tree",
        "combo[1].graph": "graph",
        "combo[2].media.trend": "bar",
        "shortest_path": "table",
        "shortest_path.graph": "graph",
        "shortest_path.path_tree": "tree",
        "shortest_path.frontier_frames": "array_cells",
        "shortest_path.best_dist": "table",
    }
    for key, view in overrides.items():
        set_view_override(key, view)
        viz_config.NESTED_DEPTH_MAP.update(
        {
            "nested": 3,
            "nested_embed": 3,
            "matrix_demo": 1,
            "tuple_block": 2,
            "profile": 2,
            "np_values": 2,
            "linked": 2,
            "hash_table": 2,
            "tic_tac_toe": 2,
            "nested_demo": 2,
            "graph_demo": 2,
            "combo": 4,
            "shortest_path": 3,
        }
    )


def _resolve_output_format(fmt: str | None = None) -> str:
    if fmt:
        return fmt
    default_fmt = getattr(viz_config, "DEFAULT_OUTPUT_FORMAT", "svg")
    allowed = getattr(viz_config, "ALLOWED_OUTPUT_FORMATS", {"svg", "png", "jpg"})
    if default_fmt not in allowed:
        raise ValueError(f"Unsupported output format configured: {default_fmt}")
    return default_fmt


def save_artifact(artifact, stem: str, fmt: str | None = None) -> Path:
    if artifact.kind == "text":
        text_path = OUTPUT_DIR / f"{stem}.txt"
        text_path.write_text(artifact.content, encoding="utf-8")
        return text_path
    if artifact.kind != "graphviz":
        raise ValueError(f"graphviz artifact expected, got: {artifact.kind}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    src = Source(artifact.content)
    resolved_fmt = _resolve_output_format(fmt)
    src.format = resolved_fmt
    rendered_path = Path(src.render(filename=stem, directory=str(OUTPUT_DIR), cleanup=True))
    return rendered_path.with_suffix(f".{resolved_fmt}")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    configure_demo_view_overrides()
    print("\n=== 模块划分提示 ===")
    print("graph_builder -> graph_view_builder (array/matrix/tree/hash_table/heap_dual 等)")
    print("renderers 保留 image/bar/scalar 等原子视图，负责最终 Graphviz 输出")

    # 1) list[int] -> array cells (default auto)
    arr = [3, 1, 2, 4, 1, 5]
    art = visualize(arr, name="arr")
    path = save_artifact(art, "arr_array")
    print("\n=== list[int] -> array strip (Visualgo style, Graphviz) ===")
    print(f"saved: {path}")

    # optional: list[int] -> bar
    # art = visualize(arr, name="arr_bar")
    # path = save_artifact(art, "arr_bar")
    # print("\n=== list[int] -> bar (Graphviz pseudo chart) ===")
    # print(f"saved: {path}")

    # linked list with nested payloads
    head = build_linked_list(
        [
            {"label": "A", "meta": [1, 2]},
            {"label": "B", "meta": {"scores": [3, {"more": [4, 5]}]}},
            {"label": "C"},
        ]
    )
    art = visualize(head, name="linked")
    path = save_artifact(art, "linked_list")
    print("\n=== linked list (nested payloads inline) ===")
    print(f"saved: {path}")

    # hash table exercising nested renderers
    hash_table = [
        [{"key": "aa", "payload": [1, 2]}, {"key": "ab", "payload": {"count": 3}}],
        [],
        [{"key": "ba", "payload": build_linked_list([1, {"deep": [2, 3]}, 4])}],
        [{"key": "ca", "payload": {"stats": {"min": 1, "max": 9}}}],
    ]
    art = visualize(hash_table, name="hash_table")
    path = save_artifact(art, "hash_table")
    print("\n=== hash table (buckets + nested cells) ===")
    print(f"saved: {path}")

    # graph snapshot (mapping-based)
    graph_snapshot = {
        "nodes": [
            {"id": "A", "value": {"name": "Alpha", "score": [1, 2]}},
            {"id": "B", "value": {"name": "Beta"}},
            "C",
        ],
        "edges": [
            {"source": "A", "target": "B", "label": "win"},
            {"source": "B", "target": "C", "label": "assist"},
            ("C", "A", "loop"),
        ],
        "directed": True,
    }
    art = visualize(graph_snapshot, name="graph_demo")
    path = save_artifact(art, "graph_demo")
    print("\n=== graph mapping -> graph view with edge labels ===")
    print(f"saved: {path}")

    # dict -> table
    metrics = {"p": 0.9, "q": 1.2, "r": 0.3}
    art = visualize(metrics, name="metrics")
    path = save_artifact(art, "metrics_table")
    print("\n=== dict -> Graphviz table ===")
    print(f"saved: {path}")

    # tree -> tree
    root = build_tree_demo()
    art = visualize(root, name="T")
    path = save_artifact(art, "tree_rooted")
    print("\n=== tree -> tree ===")
    print(f"saved: {path}")

    # tic-tac-toe search tree (nodes render as matrices)
    ttt_root = build_tictactoe_tree()
    art = visualize(ttt_root, name="tic_tac_toe")
    path = save_artifact(art, "tictactoe_tree")
    print("\n=== tic-tac-toe tree with board states ===")
    print(f"saved: {path}")

    # nested list/dict with recursive cells
    nested = [
        {"tree": root},
        {"linked": head},
        {"hash": hash_table},
        {"graph": graph_snapshot},
        {
            "profile": {
                "name": "Ada",
                "avatar": "https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png",
                "stats": {"wins": [3, 4, 5]},
            }
        },
    ]
    art = visualize(nested, name="nested_demo")
    path = save_artifact(art, "nested_array")
    print("\n=== nested list/dict (recursive cells invoking other views) ===")
    print(f"saved: {path}")

    # 7b) matrix view (2D list -> grid)
    matrix_values = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
    ]
    art = visualize(matrix_values, name="matrix_demo")
    path = save_artifact(art, "matrix_grid")
    print("\n=== matrix view (auto-selected via DEFAULT_VIEW_TYPE_MAP) ===")
    print(f"saved: {path}")

    # 8) tuple coerced to array via config name override
    tuple_block = ([1, {"deep": [2, 3]}], [4, 5])
    art = visualize(
        tuple_block,
        name="tuple_block",
    )
    path = save_artifact(art, "tuple_as_array")
    print("\n=== tuple -> array_cells via DEFAULT_VIEW_NAME_MAP ===")
    print(f"saved: {path}")

    lll=True
    art = visualize(lll, name="value")
    path = save_artifact(art, f"value")
    print(f"saved: {path}")

    # prepare avatar asset for image + table demo
    avatar_src = OUTPUT_DIR / "nus.png"
    # ascii_assets = Path(tempfile.gettempdir()) / "edcraft_demo_images"
    # ascii_assets.mkdir(exist_ok=True)
    # avatar_png = ascii_assets / "nus.png"
    # avatar_asset: Path | None = None
    # if avatar_src.exists():
    #     try:
    #         shutil.copyfile(avatar_src, avatar_png)
    #         avatar_asset = avatar_png
    #     except Exception:
    #         avatar_asset = avatar_src
    # else:
    #     print("warning: nus.png not found; skipping avatar image demos")

    # 8b) standalone image value (explicit image view)
    # if avatar_asset and avatar_asset.exists():
    #     set_view_override("avatar_img", "image")
    #     art = visualize(str(avatar_asset), name="avatar_img")
    #     path = save_artifact(art, "avatar_image")
    #     print("\n=== standalone image value ===")
    #     print(f"saved: {path}")
    # else:
    #     print("\n=== standalone image value ===")
    #     print("avatar asset missing; skipping image demo")
    art = visualize(str(avatar_src), name="avatar_img")
    path = save_artifact(art, "avatar_image")
    print("\n=== standalone image value ===")
    print(f"saved: {path}")

    # 9) dict table with per-variable nested depth map + file-backed image
    # profile_avatar_path = avatar_asset if avatar_asset else avatar_src
    profile_avatar_path =  avatar_src

    if profile_avatar_path.exists():
        avatar_value = str(profile_avatar_path)
    else:
        avatar_value = "avatar.png"
    profile_snapshot = {
        "user": {"name": "Lin", "avatar": avatar_value},
        "history": [{"scores": [91, 88, 95]}, {"notes": {"week": "2026-W06", "trend": [1, 3, 6]}}],
    }
    art = visualize(
        profile_snapshot,
        name="profile",
    )
    path = save_artifact(art, "profile_table")
    print("\n=== dict table with nested depth override & local image ===")
    print(f"saved: {path}")

    combo_payload = [
        {"tree": root},
        {"graph": graph_snapshot},
        {"media": {"avatar": avatar_value, "trend": [2.5, -1.0, 3.2, 4.1]}},
    ]
    art = visualize(combo_payload, name="combo")
    combo_path = save_artifact(art, "combo_nested", fmt="png")
    print("\n=== combo list -> nested views (tree + graph + bar + image, exported PNG) ===")
    print(f"saved: {combo_path}")

    # algorithmic use case: shortest path trace
    shortest_payload = build_shortest_path_usecase()
    art = visualize(shortest_payload, name="shortest_path")
    path = save_artifact(art, "shortest_path")
    print("\n=== shortest path trace (graph + frontier frames + tree) ===")
    print(f"saved: {path}")

    # 10) numpy ndarray auto-conversion
    if np is not None:
        np_values = np.array([[1, 2, 3], [4, 5, 6]])
        art = visualize(np_values, name="np_values")
        path = save_artifact(art, "numpy_array")
        print("\n=== numpy ndarray -> array_cells (auto) ===")
        print(f"saved: {path}")
    else:
        print("\n=== numpy ndarray -> array_cells (auto) ===")
        print("(numpy not installed; skipping)")

    # 11) complex payload auto view, recursing until scalar cells
    complex_payload = {
        "meta": {
            "id": "exp-42",
            "owner": {"name": "Ada", "team": ("vision", {"region": "us-west"})},
        },
        "batches": [
            {
                "step": 1,
                "scores": [0.91, 0.88, {"probes": (0.83, {"final": 0.8})}],
            },
            {
                "step": 2,
                "scores": [
                    0.95,
                    {
                        "ablation": [
                            {"seed": 0, "value": 0.93},
                            {"seed": 1, "value": (0.92, {"note": "best"})},
                        ]
                    },
                ],
            },
        ],
        "verdict": None,
    }
    art = visualize(
        complex_payload,
        name="complex_auto",
    )
    path = save_artifact(art, "complex_auto")
    print("\n=== complex structure -> auto (recurses down to value view) ===")
    print(f"saved: {path}")


if __name__ == "__main__":
    main()
