"""Integration helpers for the external `step-tracer` project."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from .config import VisualizerConfig, default_visualizer_config
from .graph_builder import visualize
from .models import Artifact, Frame, Trace

try:  # pragma: no cover - soft dependency
    from step_tracer.tracer import StepTracer  # type: ignore
except Exception:  # pragma: no cover - tracer optional
    StepTracer = None  # type: ignore[misc, assignment]

try:  # pragma: no cover - optional dependency
    from query_engine import QueryEngine  # type: ignore
except Exception:  # pragma: no cover - query engine optional
    QueryEngine = None  # type: ignore[misc, assignment]


class StepTracerUnavailableError(RuntimeError):
    """Raised when step-tracer is not installed but required."""


@dataclass(slots=True)
class VariableTraceEvent:
    """Single variable snapshot produced by StepTracer."""

    variable: str
    value: Any
    line_number: int
    scope_id: int
    execution_id: int
    access_path: str
    order: int

    def note(self) -> str:
        return f"line {self.line_number} · exec#{self.execution_id} · scope#{self.scope_id}"


@dataclass(frozen=True, slots=True)
class WatchFilter:
    """Filter rules for selecting which snapshots to keep."""

    name: str | None = None
    scope_id: int | None = None
    line_number: int | None = None

    def matches(self, snapshot: Any) -> bool:
        if self.name is not None and getattr(snapshot, "name", None) != self.name:
            return False
        if self.scope_id is not None and getattr(snapshot, "scope_id", None) != self.scope_id:
            return False
        if self.line_number is not None and getattr(snapshot, "line_number", None) != self.line_number:
            return False
        return True


WatchTarget = str | WatchFilter | Mapping[str, Any]


def _normalize_watch_filters(watch_variables: Sequence[WatchTarget] | None) -> list[WatchFilter]:
    filters: list[WatchFilter] = []
    if not watch_variables:
        return filters
    for raw in watch_variables:
        if isinstance(raw, WatchFilter):
            filters.append(raw)
        elif isinstance(raw, str):
            filters.append(WatchFilter(name=raw))
        elif isinstance(raw, Mapping):
            filters.append(
                WatchFilter(
                    name=raw.get("name"),
                    scope_id=raw.get("scope_id"),
                    line_number=raw.get("line_number"),
                )
            )
        else:
            raise TypeError(f"Unsupported watch target type: {type(raw)!r}")
    return filters



def _format_trace_slot_name(base_name: str, step: int) -> str:
    name = base_name or "trace"
    return f"{name} [step {step}]"


def _ensure_tracer(instance: StepTracer | None) -> StepTracer:
    if instance is not None:
        return instance
    if StepTracer is None or QueryEngine is None:
        raise StepTracerUnavailableError(
            "step-tracer or query-engine is missing. Install both via "
            "`pip install git+https://github.com/edcraft-org/step-tracer.git` "
            "and `pip install git+https://github.com/edcraft-org/query-engine.git`."
        )
    return StepTracer()


def _watch_filter_conditions(rule: WatchFilter) -> list[tuple[str, str, Any]]:
    conditions: list[tuple[str, str, Any]] = []
    if rule.name:
        conditions.append(("name", "==", rule.name))
    if rule.scope_id is not None:
        conditions.append(("scope_id", "==", rule.scope_id))
    if rule.line_number is not None:
        conditions.append(("line_number", "==", rule.line_number))
    return conditions


def _query_variable_snapshots(execution_context: Any, filters: Sequence[WatchFilter]) -> list[Any]:
    if QueryEngine is None:
        raise StepTracerUnavailableError(
            "query-engine is missing. Install it via "
            "`pip install git+https://github.com/edcraft-org/query-engine.git`."
        )

    query_engine = QueryEngine(execution_context)
    snapshots: list[Any] = []
    base_condition = ("__class__.__name__", "==", "VariableSnapshot")

    def _make_query() -> Any:
        return query_engine.create_query().where(base_condition)

    if not filters:
        snapshots = _make_query().order_by("execution_id").execute()
    else:
        for rule in filters:
            query = _make_query()
            for field, op, value in _watch_filter_conditions(rule):
                query.where((field, op, value))
            snapshots.extend(query.order_by("execution_id").execute())

    deduped: list[Any] = []
    seen: set[tuple[Any, Any, Any, Any]] = set()
    for snapshot in snapshots:
        if not hasattr(snapshot, "name") or not hasattr(snapshot, "value"):
            continue
        identity = (
            getattr(snapshot, "execution_id", None),
            getattr(snapshot, "scope_id", None),
            getattr(snapshot, "line_number", None),
            getattr(snapshot, "access_path", None),
        )
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(snapshot)
    deduped.sort(key=lambda snap: (getattr(snap, "execution_id", 0), getattr(snap, "line_number", 0)))
    return deduped


def trace_algorithm(
    source_code: str,
    watch_variables: Sequence[WatchTarget] | None = None,
    *,
    tracer: StepTracer | None = None,
    globals_dict: Mapping[str, Any] | None = None,
    max_events: int | None = None,
) -> list[VariableTraceEvent]:
    """Execute `source_code` via StepTracer and collect variable snapshots."""

    engine = _ensure_tracer(tracer)
    transformed = engine.transform_code(source_code)
    globals_env = dict(globals_dict or {})
    exec_ctx = engine.execute_transformed_code(transformed, globals_env)

    filters = _normalize_watch_filters(watch_variables)
    snapshots = _query_variable_snapshots(exec_ctx, filters)
    limited = snapshots if max_events is None else snapshots[: max(0, max_events)]

    events = [
        VariableTraceEvent(
            variable=snapshot.name,
            value=snapshot.value,
            line_number=snapshot.line_number,
            scope_id=snapshot.scope_id,
            execution_id=snapshot.execution_id,
            access_path=snapshot.access_path,
            order=index,
        )
        for index, snapshot in enumerate(limited, start=1)
    ]
    return events


def build_traces(
    events: Sequence[VariableTraceEvent],
    *,
    name_factory: Callable[[str], str] | None = None,
) -> dict[str, Trace]:
    """Group trace events by variable name and convert them to Trace objects."""

    grouped: dict[str, list[Frame]] = defaultdict(list)
    counters: dict[str, int] = defaultdict(int)
    for event in events:
        counters[event.variable] += 1
        grouped[event.variable].append(Frame(step=counters[event.variable], value=event.value, note=event.note()))

    traces: dict[str, Trace] = {}
    for var, frames in grouped.items():
        trace_name = name_factory(var) if name_factory else var
        traces[var] = Trace(name=trace_name, frames=frames)
    return traces


def visualize_trace(
    trace: Trace,
    *,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
) -> list[Artifact]:
    """Render each trace step via the main visualize() helper."""

    cfg = config.copy() if config is not None else default_visualizer_config()
    artifacts: list[Artifact] = []
    limit = cfg.step_limit_for(trace.name, override=max_steps)
    selected_steps = trace.frames if limit is None else trace.frames[:limit]
    for frame in selected_steps:
        slot_name = _format_trace_slot_name(trace.name, frame.step)
        base_override = cfg.view_name_map.get(trace.name)
        if base_override is not None and slot_name not in cfg.view_name_map:
            cfg.view_name_map[slot_name] = base_override
        artifacts.append(visualize(frame.value, name=slot_name, config=cfg))
    return artifacts


def visualize_traces(
    traces: Iterable[Trace],
    *,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
) -> dict[str, list[Artifact]]:
    """Render multiple traces at once."""

    rendered: dict[str, list[Artifact]] = {}
    for trace in traces:
        rendered[trace.name] = visualize_trace(trace, config=config, max_steps=max_steps)
    return rendered


def visualize_algorithm(
    source_code: str,
    *,
    watch_variables: Sequence[WatchTarget] | None = None,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
    tracer: StepTracer | None = None,
    globals_dict: Mapping[str, Any] | None = None,
    name_factory: Callable[[str], str] | None = None,
) -> dict[str, list[Artifact]]:
    """Convenience helper that runs StepTracer and renders the resulting traces."""

    events = trace_algorithm(
        source_code,
        watch_variables,
        tracer=tracer,
        globals_dict=globals_dict,
    )
    traces = build_traces(events, name_factory=name_factory)
    return visualize_traces(traces.values(), config=config, max_steps=max_steps)


__all__ = [
    "StepTracerUnavailableError",
    "VariableTraceEvent",
    "WatchFilter",
    "build_traces",
    "trace_algorithm",
    "visualize_trace",
    "visualize_traces",
    "visualize_algorithm",
]
