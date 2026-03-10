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


def _ensure_tracer(instance: StepTracer | None) -> StepTracer:
    if instance is not None:
        return instance
    if StepTracer is None:
        raise StepTracerUnavailableError(
            "step-tracer 未安装。请先运行 `pip install git+https://github.com/edcraft-org/step-tracer.git`。"
        )
    return StepTracer()


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
    events: list[VariableTraceEvent] = []
    for snapshot in exec_ctx.variables:
        if filters and not any(rule.matches(snapshot) for rule in filters):
            continue
        events.append(
            VariableTraceEvent(
                variable=snapshot.name,
                value=snapshot.value,
                line_number=snapshot.line_number,
                scope_id=snapshot.scope_id,
                execution_id=snapshot.execution_id,
                access_path=snapshot.access_path,
                order=len(events) + 1,
            )
        )
        if max_events is not None and len(events) >= max_events:
            break
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
    max_frames: int | None = None,
    direction: str = "LR",
) -> list[Artifact]:
    """Render each trace frame via the main visualize() helper."""

    cfg = config.copy() if config is not None else default_visualizer_config()
    artifacts: list[Artifact] = []
    selected_frames = trace.frames if max_frames is None else trace.frames[: max(0, max_frames)]
    for frame in selected_frames:
        slot_name = f"{trace.name}_{frame.step}"
        base_override = cfg.view_name_map.get(trace.name)
        if base_override is not None and slot_name not in cfg.view_name_map:
            cfg.view_name_map[slot_name] = base_override
        artifacts.append(
            visualize(
                frame.value,
                name=slot_name,
                direction=direction,  # keep LR to preserve default layout unless overridden
                config=cfg,
            )
        )
    return artifacts


def visualize_traces(
    traces: Iterable[Trace],
    *,
    config: VisualizerConfig | None = None,
    max_frames: int | None = None,
    direction: str = "LR",
) -> dict[str, list[Artifact]]:
    """Render multiple traces at once."""

    rendered: dict[str, list[Artifact]] = {}
    for trace in traces:
        rendered[trace.name] = visualize_trace(trace, config=config, max_frames=max_frames, direction=direction)
    return rendered


__all__ = [
    "StepTracerUnavailableError",
    "VariableTraceEvent",
    "WatchFilter",
    "build_traces",
    "trace_algorithm",
    "visualize_trace",
    "visualize_traces",
]
