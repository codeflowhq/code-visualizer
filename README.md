# CodeFlow Python

CodeFlow Python provides a Graphviz-first visualization pipeline for turning arbitrary Python values and traced execution into consistent visual artifacts. The project ships as a regular Python package and exposes a purely functional API so you can construct configs per session and pass them into `visualize()` or the StepTracer helpers without relying on module-level state.

## Highlights
- Graphviz-first renderers cover arrays, matrices, tables, trees, graphs, heaps, linked lists, hash tables, and fallback node-link views.
- Unified titles: even multi-node tree/graph renderers now share the same top-centered captions as HTML views, so gallery assets feel consistent.
- Scalar-friendly cards: plain strings/bools/numbers render as minimalist cards, which keeps StepTracer traces readable when you mix scalars with structural payloads.
- Minimal public API: the root package only exposes `visualize` and `visualize_algorithm`; lower-level tracing helpers stay under `code_visualizer.tracing`.
- `ViewKind` enums and structured override maps replace ad-hoc strings so IDEs and type-checkers can validate inputs.
- Converter pipelines (NumPy, pandas, or user supplied) run once per recursion layer, enabling seamless handling of nested arrays or custom tensor objects.
- Optional [step-tracer](https://github.com/edcraft-org/step-tracer) integration lets you capture algorithm executions, filter the variables you care about, and feed snapshots back into the same visualization pipeline.

## Table of contents
- [Installation](#installation)
- [Quick start](#quick-start)
- [Demo gallery](#demo-gallery)
- [Config lifecycle & customization](#config-lifecycle--customization)
- [Converter pipeline](#converter-pipeline)
- [Supported view kinds](#supported-view-kinds)
- [Step-tracer workflow](#step-tracer-workflow)
- [Public API reference](#public-api-reference)
- [Troubleshooting](#troubleshooting)

## Installation

### Requirements
- Python 3.12+ (StepTracer & Query Engine require 3.12, so the entire package targets 3.12+).
- The `graphviz` Python package plus the Graphviz CLI tools (`dot`, `neato`, ...). Install via Homebrew (`brew install graphviz`), `apt`, etc.

### Pip install
```bash
pip install codeflow-py
```

### Local development
```bash
git clone https://github.com/edcraft-org/code-visualizer.git
cd code-visualizer
python -m venv .venv && source .venv/bin/activate
pip install -e .
```
The `pip install -e .` step also installs runtime dependencies such as `graphviz`, `matplotlib`, `networkx`, `numpy`, `pandas`, and `pillow`.

## Quick start

## API usage refresher
Everything still flows through a `VisualizerConfig` that you own. Create it once per session, mutate it locally, and hand it to the helpers below.

| Task | Entry point | Notes |
|------|-------------|-------|
| Fresh config | `default_visualizer_config()` / `config.copy()` | Every call returns an isolated config; `.copy()` lets you fork tweaks without touching the original. |
| Render a Python value | `visualize(value, *, name, config)` | Converter pipeline fires at every recursion layer, so nested NumPy/pandas payloads are normalized before view selection. |
| Trace + render execution | `visualize_algorithm(source, *, watch_variables, config, max_steps=None, output="frames")` | Primary public API for traced execution. Set `output="manifest", payload=True` when a browser client needs serialized data. |
| Low-level tracing helpers | `code_visualizer.tracing.*` | Use only if you need explicit StepTracer event filtering, custom trace grouping, or manual replay. |
| Custom converters | `config.with_converters(...)` | Compose adapters (e.g., PyTorch tensors) either prepended or appended to the default NumPy/pandas pipeline. Converters run once per recursion level. |
| Per-variable step caps | `config.trace_step_limit_default` / `trace_step_limit_map` | Optional budgets for trace rendering—great when `queue_state` should stop at 3 steps but `visited_nodes` can span 10. Combine with `max_steps` for one-off overrides. |

Stick to this flow and the rest of the README examples “just work”—the root entry points stay stable even as internal modules evolve.

### Direct data visualization
```python
from code_visualizer import visualize
from code_visualizer.shared import ViewKind, default_visualizer_config
from graphviz import Source

config = default_visualizer_config()
config.view_name_map["loss_history"] = ViewKind.BAR
payload = {"epoch": [1, 2, 3], "loss_history": [0.5, 0.3, 0.2]}

artifact = visualize(payload, name="training_stats", config=config)
if artifact.kind == "graphviz":
    Source(artifact.content).render("training_stats", format="png", cleanup=True)
```
Calling `default_visualizer_config()` always returns a fresh `VisualizerConfig`. Any mutation you perform (view overrides, converter changes, nested-depth tweaks, etc.) is scoped to that instance. Pass the same config to every `visualize()` call in one session, then create another config for the next session if you need a clean slate.

### StepTracer-powered execution trace
```python
from code_visualizer.shared import default_visualizer_config
from code_visualizer import visualize_algorithm
from code_visualizer.tracing.filtering import WatchFilter

snippet = """
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

config = default_visualizer_config()
step_artifacts = visualize_algorithm(
    snippet,
    watch_variables=[
        "data",
        {"name": "swapped", "line_number": 4},
        WatchFilter(name="queue_state", scope_id=1),
    ],
    config=config,
)["data"]
```
Use dictionaries or `WatchFilter` instances (with `name`, `scope_id`, and `line_number`) to disambiguate variables that share the same identifier but live in different scopes.

### Integrated one-call visualization
```python
from code_visualizer import visualize_algorithm
from code_visualizer.shared import ViewKind, default_visualizer_config

config = default_visualizer_config()
config.view_name_map["dp"] = ViewKind.MATRIX

artifacts = visualize_algorithm(
    snippet,
    watch_variables=[
        {"name": "data"},
        {"name": "queue_state", "scope_id": 1},
    ],
    config=config,
    max_steps=3,
)
# artifacts["data"][0] already contains the rendered Graphviz source
```
`visualize_algorithm()` is the primary public API for traced execution. Lower-level tracing helpers remain available from concrete tracing modules when a caller needs custom trace filtering or replay control.

### Browser-style serialized output
```python
from code_visualizer import visualize_algorithm
from code_visualizer.shared import default_visualizer_config

payload = visualize_algorithm(
    snippet,
    watch_variables=["data"],
    config=default_visualizer_config(),
    output="manifest",
    payload=True,
)
```
This keeps browser delivery on the same public function instead of introducing a browser-only API surface.

### Browser wheel artifact
Build a browser-safe `codeflow_py` wheel without runtime dependencies:
```bash
python3 scripts/build_browser_wheel.py
```
By default the artifact is written to `dist/browser-wheels/`.

## Demo gallery
Run the end-to-end showcase to regenerate every artifact (array layouts, graph mappings with edge labels, DP matrices, numpy-nested payloads, and several StepTracer cases such as bubble sort, BFS queue state, DP tables, and graph snapshots):
```bash
python -m demo.codeflow_demo
```
All PNG/SVG outputs land in `demo/outputs/`. We removed pre-generated images from the repo to keep commits light—rerun the demo anytime to recreate them. Each StepTracer case is defined in `STEP_TRACER_CASES` inside `demo/codeflow_demo/samples.py`, so you can tweak payloads, watch filters, or append new algorithms.

## Config lifecycle & customization

### Fresh configs and copying
- `default_visualizer_config()` → returns a brand new config; call it for every visualization session.
- `config.copy()` → shallow copy if you want to fork an existing setup without mutating the original.

### View selection order
`visualize()` resolves the best renderer through this ladder:
1. **Name overrides** via `config.view_name_map`.
2. **Type-pattern overrides** via `config.view_type_map` (structural strings).
3. **Legacy type overrides** via `config.view_map` keyed by Python classes.
4. **Automatic chooser** which inspects the runtime value (graph heuristics, matrix detection, node-link fallback, etc.).

### Override maps
```python
config.view_name_map["graph_snapshot"] = ViewKind.GRAPH
config.view_type_map["tuple[list]"] = ViewKind.MATRIX
config.view_map[MyTreeNode] = ViewKind.TREE
```

### Type-pattern cheat sheet
```
pattern := atom ["[" pattern {"," pattern} "]"]
atom    := list | tuple | set | frozenset | dict | int | float | bool | number
           | str | bytes | path | any | none | linked_list | tree
```
Examples: `list[number]` for numeric arrays, `tuple[list]` for matrices, `dict[str, any]` for key-value tables, `linked_list`, `tree`.

### Nested depth, layout, and format
- `recursion_depth_default` / `recursion_depth_map` limit how deeply list/dict payloads expand inside HTML table renderers.
- `auto_recursion_depth_cap` prevents runaway recursion in arbitrarily deep payloads.
- `output_format` (`"dot"`, `"svg"`, `"png"`, or `"jpg"`) guides helper utilities such as `demo.save_artifact()`; use `"dot"` when you want raw Graphviz source instead of a rendered image. `allowed_output_formats` guards invalid requests.
- `graph_direction` sets the default Graphviz `rankdir` (`"LR"` or `"TB"`) for node-link fallbacks.
- `max_depth` / `max_items_per_view` control how far Visual IR extraction recurses and how many siblings are rendered before collapsing to ellipses.

## Converter pipeline
Converters run before every view selection, one recursion layer at a time. The default pipeline already supports:
1. NumPy arrays → `list` / nested `list[list]`
2. pandas `DataFrame` / `Series` → dict payloads
3. Identity fallback

Extend it per session:
```python
from code_visualizer.shared import default_visualizer_config

config = default_visualizer_config().with_converters(
    lambda value: (
        (True, value.tolist()) if "torch" in type(value).__module__ else (False, value)
    ),
    prepend=True,
)
```
Because conversion is invoked at each recursion level, nested `numpy.ndarray` values (including ndarray-of-ndarray payloads) get flattened lazily—exactly how the demo exercises the new matrix/array cases.

## Supported view kinds

| `ViewKind` value | Typical input                                                                    |
|------------------|------------------------------------------------------------------------------------|
| `ARRAY_CELLS`    | `list` / `tuple` / `set` / `frozenset` of scalars or nested values                 |
| `MATRIX`         | 2-D arrays (`list[list]`, nested tuples, NumPy ndarrays)                           |
| `IMAGE`          | Local paths, URLs, `pathlib.Path`, `PIL.Image`, matplotlib `Figure`, etc.          |
| `BAR`            | Homogeneous numeric lists                                                          |
| `TABLE`          | Dict-like objects (`dict[str, any]`, dataclass `asdict`, pandas dicts)              |
| `TREE`           | Objects exposing `.children` / `.left` / `.right`, or dicts containing `children`   |
| `GRAPH`          | NetworkX graphs or `{"nodes": [...], "edges": [...], "directed": bool}` mappings  |
| `LINKED_LIST`    | Objects with `.next` pointers or `[{"value": ..., "next": ...}]` payloads          |
| `HASH_TABLE`     | Buckets containing payload chains (lists/dicts/sets/linked nodes)                   |
| `HEAP_DUAL`      | Heap arrays rendered as array + tree combo                                          |
| `NODE_LINK`      | Generic Visual IR fallback when no specific view matches                           |

Tree tips: supply `.children` or dicts with `children` plus optional `label` / `value`. Graph tips: edges accept dicts (`source`/`target`, optional `label`) or tuples `(src, dst, label)`. Avoid literal `[]` characters in node IDs; prefer underscores (`node_1`) to keep Graphviz parsers happy.

## Step-tracer workflow
1. `trace_algorithm(source_code, watch_variables=...)` → runs StepTracer and captures snapshots.
2. `watch_variables` accepts:
   - plain strings (`"data"`),
   - dicts `{"name": "queue_state", "scope_id": 5, "line_number": 23}` for disambiguation,
   - or `WatchFilter` instances. Mix them freely to handle duplicate variable names that appear in different scopes or lines.
3. `query-engine` filters/sorts StepTracer snapshots according to those rules so we do not maintain bespoke loops.
4. `build_traces(events, name_factory=...)` groups snapshots per variable and returns `Trace` objects.
5. `visualize_trace(trace, config=..., max_steps=...)` renders each step via the same `visualize()` helper.
6. `visualize_traces(traces.values(), config=...)` bulk-renders everything, returning a `{name: [RenderedTraceFrame, ...]}` map.

If `step-tracer` is missing, the helpers raise `StepTracerUnavailableError` with installation hints.

## Public API reference

Root package:
- `visualize(value, *, name, config)` – render an arbitrary Python value.
- `visualize_algorithm(source, *, watch_variables=None, config=None, max_steps=None, output="frames", payload=False)` – run StepTracer and render the resulting snapshots.

Shared configuration:
- `default_visualizer_config()` – factory for fresh configs.
- `VisualizerConfig.with_converters()` / `.copy()` – scoped mutations.
- `ViewKind` – strongly typed view identifiers for overrides and rendering decisions.

Advanced tracing helpers live under concrete tracing modules such as:

- `code_visualizer.tracing.pipeline`
- `code_visualizer.tracing.filtering`
- `code_visualizer.tracing.rendering`

## Troubleshooting
- **"No module named graphviz"** – ensure you installed both the Python package (`pip install graphviz`) and the Graphviz system binary (`brew install graphviz`, `apt install graphviz`, ...). Re-run `pip install -e .` inside your virtualenv afterwards.
- **StepTracer requires Python >=3.12** – create a dedicated env (e.g., `uv venv -p 3.12 .venv312 && source .venv312/bin/activate`) before installing `step-tracer` from Git.
- **`query-engine` missing** – install via `pip install git+https://github.com/edcraft-org/query-engine.git` (it pulls `step-tracer` as well). The StepTracer helpers rely on it to filter and order snapshots.
- **`pip` missing inside a new env** – run `python -m ensurepip --upgrade` and retry `python -m pip install -e .`.
- **Graph payload not detected** – either conform to the `{nodes, edges, directed}` mapping shown above or register a custom converter that rewrites your structure into that shape.
- **Need different configs per visualization** – instantiate a new config via `default_visualizer_config()` or `config.copy()` rather than mutating a module-level singleton. This keeps concurrent notebooks or services from tripping over shared state.
