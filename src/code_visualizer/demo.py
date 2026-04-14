# demo.py
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional
    np = None  # type: ignore

from graphviz import Source

from .config import VisualizerConfig, default_visualizer_config
from .demo_samples import STEP_TRACER_CASES, build_linked_list, build_tree_demo
from .graph_builder import visualize
from .models import ArtifactKind
from .step_tracing import (
    StepTracerUnavailableError,
    build_traces,
    trace_algorithm,
    visualize_trace,
)
from .view_types import ViewKind

# moved sample snippets/builders to demo_samples.py



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


def set_view_override(config: VisualizerConfig, name: str, view: ViewKind) -> None:
    """Register/replace a mapper entry so demo_visualize() stays config-driven."""

    config.view_name_map[name] = view


def configure_demo_view_overrides(config: VisualizerConfig) -> None:
    """Demonstrate the new mapper: clear defaults, then add name & type rules."""

    config.view_map.clear()
    config.view_name_map.clear()
    config.recursion_depth_map.clear()

    overrides: dict[str, ViewKind] = {
        "arr": ViewKind.ARRAY_CELLS,
        "arr_bar": ViewKind.BAR,
        "linked": ViewKind.LINKED_LIST,
        "hash_table": ViewKind.HASH_TABLE,
        "metrics": ViewKind.TABLE,
        "T": ViewKind.TREE,
        "tic_tac_toe": ViewKind.TREE,
        "heap": ViewKind.HEAP_DUAL,
        "nested": ViewKind.ARRAY_CELLS,
        "tuple_block": ViewKind.ARRAY_CELLS,
        "avatar_img": ViewKind.IMAGE,
        "data": ViewKind.BAR,
        "queue_state": ViewKind.ARRAY_CELLS,
        "visited_nodes": ViewKind.ARRAY_CELLS,
        "dp_matrix": ViewKind.MATRIX,
        "graph_snapshot": ViewKind.GRAPH,
        "profile": ViewKind.TABLE,
        "matrix_demo": ViewKind.MATRIX,
        "np_values": ViewKind.ARRAY_CELLS,
        "nested_np": ViewKind.ARRAY_CELLS,
        "nested_demo": ViewKind.ARRAY_CELLS,
        "graph_demo": ViewKind.GRAPH,
        "combo": ViewKind.ARRAY_CELLS,
        "combo[0].tree": ViewKind.TREE,
        "combo[1].graph": ViewKind.GRAPH,
        "combo[2].media.trend": ViewKind.BAR,
        "shortest_path": ViewKind.TABLE,
        "shortest_path.graph": ViewKind.GRAPH,
        "shortest_path.path_tree": ViewKind.TREE,
        "shortest_path.frontier_frames": ViewKind.ARRAY_CELLS,
        "shortest_path.best_dist": ViewKind.TABLE,
    }
    for key, view in overrides.items():
        set_view_override(config, key, view)

    config.recursion_depth_map.update(
        {
            "nested": 3,
            "nested_embed": 3,
            "matrix_demo": 1,
            "tuple_block": 2,
            "profile": 2,
            "np_values": 2,
            "nested_np": 3,
            "linked": 2,
            "hash_table": 2,
            "tic_tac_toe": 2,
            "nested_demo": 2,
            "graph_demo": 2,
            "combo": 4,
            "shortest_path": 3,
        }
    )


def demo_visualize(value: Any, *, config: VisualizerConfig, **kwargs):
    """Wrapper that keeps the demo config explicit."""

    kwargs.setdefault("config", config)
    return visualize(value, **kwargs)


def _resolve_output_format(config: VisualizerConfig, fmt: str | None = None) -> str:
    if fmt:
        return fmt
    return config.ensure_output_format(fmt)


def save_artifact(artifact, stem: str, *, config: VisualizerConfig, fmt: str | None = None) -> Path:
    if artifact.kind == ArtifactKind.TEXT:
        text_path = OUTPUT_DIR / f"{stem}.txt"
        text_path.write_text(artifact.content, encoding="utf-8")
        return text_path
    if artifact.kind != ArtifactKind.GRAPHVIZ:
        raise ValueError(f"graphviz artifact expected, got: {artifact.kind}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    resolved_fmt = _resolve_output_format(config, fmt)
    if resolved_fmt == "dot":
        dot_path = OUTPUT_DIR / f"{stem}.dot"
        dot_path.write_text(artifact.content, encoding="utf-8")
        return dot_path

    src = Source(artifact.content)
    src.format = resolved_fmt
    rendered_path = Path(src.render(filename=stem, directory=str(OUTPUT_DIR), cleanup=True))
    return rendered_path.with_suffix(f".{resolved_fmt}")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    demo_config = default_visualizer_config()
    configure_demo_view_overrides(demo_config)
    print("\n=== module layout tips ===")
    print("graph_builder -> graph_view_builder (array/matrix/tree/hash_table/heap_dual etc.)")
    print("renderers own the atomic image/bar/scalar views and emit Graphviz output")

    # 1) list[int] -> array cells (default auto)
    arr = [3, 1, 2, 4, 1, 5]
    art = demo_visualize(arr, name="arr", config=demo_config)
    path = save_artifact(art, "arr_array", config=demo_config)
    print("\n=== list[int] -> array strip (Visualgo style, Graphviz) ===")
    print(f"saved: {path}")

    # optional: list[int] -> bar
    # art = demo_visualize(arr, name="arr_bar", config=demo_config)
    # path = save_artifact(art, "arr_bar", config=demo_config)
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
    art = demo_visualize(head, name="linked", config=demo_config)
    path = save_artifact(art, "linked_list", config=demo_config)
    print("\n=== linked list (nested payloads inline) ===")
    print(f"saved: {path}")

    # hash table exercising nested renderers
    hash_table = [
        [{"key": "aa", "payload": [1, 2]}, {"key": "ab", "payload": {"count": 3}}],
        [],
        [{"key": "ba", "payload": build_linked_list([1, {"deep": [2, 3]}, 4])}],
        [{"key": "ca", "payload": {"stats": {"min": 1, "max": 9}}}],
    ]
    art = demo_visualize(hash_table, name="hash_table", config=demo_config)
    path = save_artifact(art, "hash_table", config=demo_config)
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
    art = demo_visualize(graph_snapshot, name="graph_demo", config=demo_config)
    path = save_artifact(art, "graph_demo", config=demo_config)
    print("\n=== graph mapping -> graph view with edge labels ===")
    print(f"saved: {path}")

    # dict -> table
    metrics = {"p": 0.9, "q": 1.2, "r": 0.3}
    art = demo_visualize(metrics, name="metrics", config=demo_config)
    path = save_artifact(art, "metrics_table", config=demo_config)
    print("\n=== dict -> Graphviz table ===")
    print(f"saved: {path}")

    # tree -> tree
    root = build_tree_demo()
    art = demo_visualize(root, name="T", config=demo_config)
    path = save_artifact(art, "tree_rooted", config=demo_config)
    print("\n=== tree -> tree ===")
    print(f"saved: {path}")

    # tic-tac-toe search tree (nodes render as matrices)
    ttt_root = build_tictactoe_tree()
    art = demo_visualize(ttt_root, name="tic_tac_toe", config=demo_config)
    path = save_artifact(art, "tictactoe_tree", config=demo_config)
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
    art = demo_visualize(nested, name="nested_demo", config=demo_config)
    path = save_artifact(art, "nested_array", config=demo_config)
    print("\n=== nested list/dict (recursive cells invoking other views) ===")
    print(f"saved: {path}")

    # 7b) matrix view (2D list -> grid)
    matrix_values = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
    ]
    art = demo_visualize(matrix_values, name="matrix_demo", config=demo_config)
    path = save_artifact(art, "matrix_grid", config=demo_config)
    print("\n=== matrix view (auto-selected via DEFAULT_VIEW_TYPE_MAP) ===")
    print(f"saved: {path}")

    # 8) tuple coerced to array via config name override
    tuple_block = ([1, {"deep": [2, 3]}], [4, 5])
    art = demo_visualize(
        tuple_block,
        name="tuple_block",
        config=demo_config,
    )
    path = save_artifact(art, "tuple_as_array", config=demo_config)
    print("\n=== tuple -> array_cells via DEFAULT_VIEW_NAME_MAP ===")
    print(f"saved: {path}")

    lll=True
    art = demo_visualize(lll, name="value", config=demo_config)
    path = save_artifact(art, "value", config=demo_config)
    print(f"saved: {path}")

    # prepare avatar asset for image + table demo
    avatar_src = OUTPUT_DIR / "nus.png"
    # ascii_assets = Path(tempfile.gettempdir()) / "code_visualizer_demo_images"
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
    #     set_view_override(demo_config, "avatar_img", ViewKind.IMAGE)
    #     art = demo_visualize(str(avatar_asset), name="avatar_img", config=demo_config)
    #     path = save_artifact(art, "avatar_image", config=demo_config)
    #     print("\n=== standalone image value ===")
    #     print(f"saved: {path}")
    # else:
    #     print("\n=== standalone image value ===")
    #     print("avatar asset missing; skipping image demo")
    art = demo_visualize(str(avatar_src), name="avatar_img", config=demo_config)
    path = save_artifact(art, "avatar_image", config=demo_config)
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
    art = demo_visualize(
        profile_snapshot,
        name="profile",
        config=demo_config,
    )
    path = save_artifact(art, "profile_table", config=demo_config)
    print("\n=== dict table with nested depth override & local image ===")
    print(f"saved: {path}")

    combo_payload = [
        {"tree": root},
        {"graph": graph_snapshot},
        {"media": {"avatar": avatar_value, "trend": [2.5, -1.0, 3.2, 4.1]}},
    ]
    art = demo_visualize(combo_payload, name="combo", config=demo_config)
    combo_path = save_artifact(art, "combo_nested", config=demo_config, fmt="png")
    print("\n=== combo list -> nested views (tree + graph + bar + image, exported PNG) ===")
    print(f"saved: {combo_path}")

    # algorithmic use case: shortest path trace
    shortest_payload = build_shortest_path_usecase()
    art = demo_visualize(shortest_payload, name="shortest_path", config=demo_config)
    path = save_artifact(art, "shortest_path", config=demo_config)
    print("\n=== shortest path trace (graph + frontier frames + tree) ===")
    print(f"saved: {path}")

    # 10) numpy ndarray auto-conversion
    if np is not None:
        np_values = np.array([[1, 2, 3], [4, 5, 6]])
        art = demo_visualize(np_values, name="np_values", config=demo_config)
        path = save_artifact(art, "numpy_array", config=demo_config)
        print("\n=== numpy ndarray -> array_cells (auto) ===")
        print(f"saved: {path}")

        nested_np = np.array(
            [
                np.array([[1, 2], [3, 4]]),
                np.array([[5, 6], [7, 8]]),
            ],
            dtype=object,
        )
        art = demo_visualize(nested_np, name="nested_np", config=demo_config)
        nested_path = save_artifact(art, "nested_np_array", config=demo_config)
        print("\n=== nested numpy ndarray -> nested array cells ===")
        print(f"saved: {nested_path}")
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
    art = demo_visualize(
        complex_payload,
        name="complex_auto",
        config=demo_config,
    )
    path = save_artifact(art, "complex_auto", config=demo_config)
    print("\n=== complex structure -> auto (recurses down to value view) ===")
    print(f"saved: {path}")

    tracer_missing = False
    for case in STEP_TRACER_CASES:
        print(f"\n=== step-tracer: {case['label']} ===")
        if tracer_missing:
            print("step-tracer is missing, skipping remaining examples")
            break
        try:
            tracer_events = trace_algorithm(
                case["snippet"],
                case["watch"],
                max_events=case.get("max_events"),
            )
        except StepTracerUnavailableError as exc:
            print(f"step-tracer is missing, skipping dynamic trace demos: {exc}")
            tracer_missing = True
            break
        traces = build_traces(tracer_events)
        for target in case["watch"]:
            if isinstance(target, str):
                target_name = target
            elif isinstance(target, Mapping):
                target_name = str(target.get("name", "") or "")
            else:
                target_name = getattr(target, "name", "") or ""
            if not target_name:
                continue
            data_trace = traces.get(target_name)
            if data_trace is None:
                print(f"{target_name} not captured, skipping")
                continue
            trace_arts = visualize_trace(
                data_trace,
                config=demo_config,
                max_steps=case.get("max_steps"),
            )
            for idx, artifact in enumerate(trace_arts, start=1):
                trace_path = save_artifact(
                    artifact,
                    f"{case['stem']}_{target_name}_{idx}",
                    config=demo_config,
                )
                print(f"{target_name} frame {idx}: {trace_path}")
            if not trace_arts:
                print(f"{target_name} has no available frames")


if __name__ == "__main__":
    main()
