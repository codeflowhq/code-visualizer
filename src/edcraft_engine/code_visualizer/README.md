# Code Visualizer Mapper Guide

The visualizer picks a rendering "view" for every value you pass to
`graph_builder.visualize()`. The decision pipeline matches overrides in the
following order:

1. **Name overrides** - `config.DEFAULT_VIEW_NAME_MAP` matches exact variable
   names or simple key/index paths such as `profile.history[0].scores`.
2. **Type-pattern overrides** - `config.DEFAULT_VIEW_TYPE_MAP` consumes
   lightweight structural patterns (see syntax below).
3. **Legacy isinstance overrides** - `config.DEFAULT_VIEW_MAP`.
4. **Automatic chooser** - `renderers.choose_view()` inspects the runtime value
   and falls back to a Visual IR node-link view if nothing else matches.

## Available views

| ViewKind      | Ideal inputs / behavior                                                          |
|---------------|-----------------------------------------------------------------------------------|
| `array_cells` | `list`/`tuple`/`set`/`frozenset` of scalars or nested structures                 |
| `matrix`      | 2D arrays (list/tuple of lists/tuples)                                           |
| `image`       | Local paths/URLs/data URIs, `pathlib.Path`, `PIL.Image`, matplotlib `Figure` etc. |
| `bar`         | Numeric lists (homogeneous)                                                      |
| `table`       | Dict-like objects (string or mixed keys)                                         |
| `tree`        | Binary or n-ary nodes exposing `.children`/`.left/.right`, or dicts with `children` |
| `graph`       | NetworkX graphs or plain mappings with `nodes` + `edges` (edge labels supported)  |
| `heap_dual`   | Heap arrays rendered via the shared array/tree builders                          |
| `linked_list` | Objects with `.next` pointer chain or lists of nodes representing a chain        |
| `hash_table`  | Buckets with pointer-style chains (lists/dicts/sets/linked nodes)                |
| `node_link`   | Generic fallback (Visual IR) for anything else                                   |

## Module layout

- `graph_builder.visualize` resolves the mapper (name -> type-pattern -> legacy overrides) and dispatches to the appropriate renderer.
- `graph_view_builder.GraphViewBuilder` houses every composite Graphviz view (array / matrix / table / hash_table / linked_list / tree / graph / heap_dual / bar). Because all of them share the same builder, they can mount nested ports uniformly and recursively ask the mapper for child views.
- `renderers.py` keeps the atomic views (`image`, `scalar`, Visual IR node-link). Bars are emitted as HTML labels inside Graphviz nodes so they can be embedded elsewhere. Atomic views are leaf nodes-they do not recurse further.

With this split, `hash_table` regains the "bucket + chain" style, `heap_dual` reuses the array + tree builders, and any complex structure can attach to the global graph through the same port mechanism.

## Graphviz-first rendering strategy

- **Prefer Graphviz APIs** - arrays, matrices, trees, graphs, hash tables, heaps, and linked lists are all translated into a `VisualGraph` and rendered through `render_graphviz_node_link()` via the official `Digraph` API. Rank, ports, and layout are fully delegated to Graphviz.
- **HTML labels only** - every snippet of HTML in `graph_view_builder` is an HTML-like label that Graphviz natively understands (mostly `<TABLE>` tags). They never bypass Graphviz's renderer, so the pipeline still honours the "Graphviz first" requirement.
- **Nested views still use Graphviz** - when a cell needs to embed another view (tree/graph/etc.), the builder spins up a nested `VisualGraph`, renders it to DOT, converts it to PNG/SVG through `_render_dot_to_image()`, and drops the resulting `<IMG>` back into the parent cell. Only if Graphviz fails do we fall back to plain text placeholders.
- **Atomic views stay minimal** - helpers such as `render_graphviz_image`, `render_graphviz_scalar`, and the bar/array fallbacks still build tiny `Digraph`s themselves so that leaf views can be embedded anywhere without adding another recursion layer.

## Type-pattern syntax

```
pattern := atom ["[" pattern {"," pattern} "]"]
atom    := list | tuple | set | frozenset | dict | int | float
           | bool | number | str | bytes | path | any | none
           | linked_list | tree
```

Examples:

| Pattern            | Meaning / common use             |
|--------------------|----------------------------------|
| `list[number]`     | numeric array -> `array_cells`    |
| `tuple[list]`      | tuple of lists -> `matrix`        |
| `dict[str, any]`   | object-like dict -> `table`       |
| `linked_list`      | objects exposing `.next`         |
| `tree`             | object/dict nodes exposing `children` |

## Customizing views

Override the dictionaries in `config.py` (either editing the file or mutating
them before calling `visualize()`):

```python
from edcraft_engine.code_visualizer import config as viz_config

# Force a specific variable to render as a bar chart.
viz_config.DEFAULT_VIEW_NAME_MAP["loss_history"] = "bar"

# Treat every tuple of tuples as a matrix.
viz_config.DEFAULT_VIEW_TYPE_MAP["tuple[tuple]"] = "matrix"

# Map a custom class to the tree view.
from mynodes import TreeNode
viz_config.DEFAULT_VIEW_MAP[TreeNode] = "tree"
```

You can also adjust nested depth via `viz_config.DEFAULT_NESTED_DEPTH` or
`viz_config.NESTED_DEPTH_MAP` to control how deeply lists/dicts expand inside
the array/table renderers.

- `viz_config.DEFAULT_OUTPUT_FORMAT` (allowed values: `"svg"`, `"png"`, `"jpg"`)
controls the default format emitted by helpers such as `demo.save_artifact`.
Change it to `"png"` or `"jpg"` if you prefer rasterized previews.

### Tree inputs at a glance

The `tree` view accepts a unified structure so you can mix binary and n-ary
nodes:

- **Objects with `.children`** - any iterable works; node labels come from
  `.val`, `.value`, or fall back to the class name.
- **Binary nodes** - `.left`/`.right` pointers remain supported, no adapter
  needed.
- **Plain mappings** - provide a `children` list plus optional `label`, `name`,
  `value`, `board`, or `data`. Remaining keys are rendered inline so you can
  embed extra metadata.

### Graph inputs and edge labels

`graph` can now ingest either NetworkX graphs or simple dictionaries:

```python
graph_payload = {
    "nodes": [
        {"id": "A", "value": {"name": "Alpha"}},
        {"id": "B", "value": {"name": "Beta"}},
        "C",  # scalar entries double as both id & label
    ],
    "edges": [
        {"source": "A", "target": "B", "label": "win"},
        ("B", "C", "assist"),  # tuple form also works
    ],
    "directed": True,
}
```

- Node entries may be scalars or mappings with `id`/`name` keys plus optional
  `value`/`label`/`data`.
- Edge entries accept `source`/`target` (or `from`/`to`) and optional
  `label`/`value`/`weight` text, which is rendered directly on the edge.
- Undirected graphs automatically suppress arrow heads (`dir=none`).

Because the graph view now shares the same composite builder as the other
Graphviz tables, you can nest a graph inside any array/table cell or render it
recursively as part of a larger visualization.

## Demo output gallery

All previews below are generated by running `python -m edcraft_engine.code_visualizer.demo`.
Artifacts are saved under `code_visualizer/demo_outputs/`; rerun the demo whenever
you update the data to refresh the screenshots.

### Arrays, matrices & scalar views

| Demo | Description | Preview |
|------|-------------|---------|
| `arr_array.png` | Default `array_cells` for `list[int]` | ![arr_array](demo_outputs/arr_array.png) |
| `tuple_as_array.png` | Tuple overridden to render as array cells | ![tuple_as_array](demo_outputs/tuple_as_array.png) |
| `numpy_array.png` | NumPy `ndarray` auto-coerced to list -> array view | ![numpy_array](demo_outputs/numpy_array.png) |
| `matrix_grid.png` | `matrix` view for 2D lists | ![matrix_grid](demo_outputs/matrix_grid.png) |
| `heap_dual.png` | Heap rendered as array + tree combo | ![heap_dual](demo_outputs/heap_dual.png) |
| `value.png` | Scalar fallback (plain text) | ![value](demo_outputs/value.png) |
| `avatar_image.png` | Standalone `image` view (local PNG) | ![avatar_image](demo_outputs/avatar_image.png) |

### Tables, dictionaries & nested payloads

| Demo | Description | Preview |
|------|-------------|---------|
| `metrics_table.png` | `table` view for `dict[str, float]` | ![metrics_table](demo_outputs/metrics_table.png) |
| `profile_table.png` | Table embedding a local avatar + nested depth override | ![profile_table](demo_outputs/profile_table.png) |
| `nested_array.png` | List-of-dicts auto-expands nested cells | ![nested_array](demo_outputs/nested_array.png) |
| `complex_auto.png` | Deep dict/list/tuple structure rendered via auto view picking | ![complex_auto](demo_outputs/complex_auto.png) |
| `combo_nested.png` | Single list containing tree / graph / bar / image views | ![combo_nested](demo_outputs/combo_nested.png) |

### Linked structures, tree & graph views

| Demo | Description | Preview |
|------|-------------|---------|
| `linked_list.png` | `.next` chain with recursive cells inside each node | ![linked_list](demo_outputs/linked_list.png) |
| `hash_table.png` | Bucket + chain layout (buckets horizontal, chains vertical) | ![hash_table](demo_outputs/hash_table.png) |
| `tree_rooted.png` | Generic rooted tree (binary + n-ary supported) | ![tree_rooted](demo_outputs/tree_rooted.png) |
| `tictactoe_tree.png` | Tree nodes embed 3x3 boards (matrix-in-tree nesting) | ![tictactoe_tree](demo_outputs/tictactoe_tree.png) |
| `graph_demo.png` | Custom graph payload with edge labels | ![graph_demo](demo_outputs/graph_demo.png) |
| `network_graph.png` | NetworkX Graph automatically rendered as `graph` view | ![network_graph](demo_outputs/network_graph.png) |

### Algorithm traces

| Demo | Description | Preview |
|------|-------------|---------|
| `shortest_path.png` | Dijkstra-style trace with table embedding `graph`, frontier frames, tree, and distance table | ![shortest_path](demo_outputs/shortest_path.png) |

### Sorting frames & bar charts

| Demo | Description | Preview |
|------|-------------|---------|
| `arr_bar.png` | `bar` view for `list[number]` | ![arr_bar](demo_outputs/arr_bar.png) |
| `sort_frame_0~4.png` | Bubble-sort trace, each frame rendered as a bar chart | ![sort_frame_0](demo_outputs/sort_frame_0.png) |

### Miscellaneous notes

- `hash_table.png`, `linked_list.png`, and `graph_demo.png` highlight how nested ports allow complex structures to plug into larger diagrams.
- `value.txt` shows the fallback artifact when a renderer returns plain text instead of Graphviz content.
