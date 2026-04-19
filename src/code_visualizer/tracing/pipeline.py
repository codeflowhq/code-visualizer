from __future__ import annotations

import ast
import json
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..config import VisualizerConfig, default_visualizer_config
from ..graph_builder import visualize
from ..models import Artifact, Frame, Trace
from .common import (
    RenderedTraceFrame,
    VariableTraceEvent,
    WatchFilter,
    WatchTarget,
    _format_trace_slot_name,
    _normalize_access_path,
    _normalize_watch_filters,
    _watch_filter_conditions,
)

try:  # pragma: no cover - soft dependency
    from step_tracer import StepTracer  # type: ignore
except Exception:  # pragma: no cover - tracer optional
    StepTracer = None  # type: ignore[misc, assignment]

try:  # pragma: no cover - optional dependency
    from query_engine import QueryEngine  # type: ignore
except Exception:  # pragma: no cover - query engine optional
    QueryEngine = None  # type: ignore[misc, assignment]


class StepTracerUnavailableError(RuntimeError):
    """Raised when step-tracer is not installed but required."""


@dataclass(frozen=True, slots=True)
class PopMutation:
    receiver: str
    method: str
    argument: Any = None
    has_argument: bool = False


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


def _literal_arg(node: ast.AST | None) -> tuple[bool, Any]:
    if isinstance(node, ast.Constant):
        return True, node.value
    return False, None


def _pop_mutation_receivers(source_code: str) -> dict[int, PopMutation]:
    """Map assignment lines such as `node = queue.popleft()` to mutated containers."""

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}
    receivers: dict[int, PopMutation] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
            continue
        receiver = value.func.value
        if not isinstance(receiver, ast.Name):
            continue
        method = value.func.attr
        if method == "popleft":
            receivers[node.lineno] = PopMutation(receiver=receiver.id, method=method)
        elif method == "pop":
            has_argument, argument = _literal_arg(value.args[0] if value.args else None)
            receivers[node.lineno] = PopMutation(
                receiver=receiver.id,
                method=method,
                argument=argument,
                has_argument=has_argument,
            )
    return receivers


def _is_watched_name(name: str, filters: Sequence[WatchFilter]) -> bool:
    if not filters:
        return True
    return any(rule.name == name and rule.access_path is None for rule in filters)


def _matching_watch_filter(event: VariableTraceEvent, filters: Sequence[WatchFilter]) -> WatchFilter | None:
    for rule in filters:
        if rule.name != event.variable or rule.access_path is None:
            continue
        normalized_rule = _normalize_access_path(rule.access_path)
        normalized_event = _normalize_access_path(event.access_path)
        if normalized_rule is None or normalized_event is None:
            continue
        if normalized_event == normalized_rule or normalized_event.startswith(normalized_rule + "[") or normalized_event.startswith(normalized_rule + "."):
            return rule
    return None


_MISSING = object()


def _extract_access_path_value(root_value: Any, expression: str, root_name: str) -> Any:  # noqa: C901
    try:
        parsed = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return _MISSING
    if not isinstance(parsed, ast.Name | ast.Subscript | ast.Attribute):
        return _MISSING

    def walk(node: ast.AST, value: Any) -> Any:
        if isinstance(node, ast.Name):
            return value if node.id == root_name else _MISSING
        if isinstance(node, ast.Subscript):
            base = walk(node.value, value)
            if base is _MISSING:
                return _MISSING
            key_node = node.slice
            if isinstance(key_node, ast.Constant):
                key = key_node.value
            else:
                return _MISSING
            try:
                return base[key]
            except (KeyError, IndexError, TypeError):
                return _MISSING
        if isinstance(node, ast.Attribute):
            base = walk(node.value, value)
            if base is _MISSING:
                return _MISSING
            if isinstance(base, Mapping):
                return base.get(node.attr, _MISSING)
            return getattr(base, node.attr, _MISSING)
        return _MISSING

    return walk(parsed, root_value)


def _project_expression_watch_events(events: Sequence[VariableTraceEvent], filters: Sequence[WatchFilter]) -> list[VariableTraceEvent]:
    if not filters:
        return list(events)
    expression_rules = [rule for rule in filters if rule.name and rule.access_path]
    root_names = {rule.name for rule in filters if rule.name and rule.access_path is None}
    if not expression_rules:
        return list(events)

    updated: list[VariableTraceEvent] = []
    for event in events:
        if event.variable in root_names:
            updated.append(event)
        for rule in expression_rules:
            if rule.access_path is None:
                continue
            trace_name = rule.trace_name or rule.access_path
            if rule.name is None or event.variable not in {rule.name, trace_name}:
                continue
            projected_value = _extract_access_path_value(event.value, rule.access_path, rule.name)
            if projected_value is _MISSING:
                continue
            updated.append(
                VariableTraceEvent(
                    variable=rule.trace_name or rule.access_path,
                    value=projected_value,
                    line_number=event.line_number,
                    scope_id=event.scope_id,
                    execution_id=event.execution_id,
                    var_id=event.var_id,
                    access_path=rule.access_path,
                    order=event.order,
                    access_paths=(rule.access_path,),
                )
            )
    return updated


def _pop_index(mutation: PopMutation) -> int:
    return mutation.argument if mutation.has_argument and isinstance(mutation.argument, int) else -1


def _simulate_sequence_pop(value: list[Any], mutation: PopMutation) -> list[Any]:
    next_value = list(value)
    if next_value:
        try:
            next_value.pop(_pop_index(mutation))
        except IndexError:
            pass
    return next_value


def _simulate_pop_value(value: Any, mutation: PopMutation, popped_value: Any) -> Any:
    if isinstance(value, deque):
        deque_value = deque(value)
        if deque_value:
            if mutation.method == "popleft":
                deque_value.popleft()
            else:
                deque_value.pop()
        return deque_value
    if isinstance(value, list):
        return _simulate_sequence_pop(value, mutation)
    if isinstance(value, tuple):
        return tuple(_simulate_sequence_pop(list(value), mutation))
    if isinstance(value, dict):
        dict_value = dict(value)
        if mutation.has_argument:
            dict_value.pop(mutation.argument, None)
        return dict_value
    if isinstance(value, set):
        set_value = set(value)
        set_value.discard(popped_value)
        return set_value
    if isinstance(value, frozenset):
        set_value = set(value)
        set_value.discard(popped_value)
        return frozenset(set_value)
    return value


def _stable_value_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=repr)
    except TypeError:
        return repr(value)


def _merge_duplicate_root_events(events: Sequence[VariableTraceEvent]) -> list[VariableTraceEvent]:
    merged: list[VariableTraceEvent] = []
    index_by_key: dict[tuple[str, int, int, str], int] = {}
    for event in events:
        key = (event.variable, event.execution_id, event.line_number, _stable_value_key(event.value))
        existing_index = index_by_key.get(key)
        if existing_index is None:
            access_paths = event.access_paths or (event.access_path,)
            index_by_key[key] = len(merged)
            merged.append(
                VariableTraceEvent(
                    variable=event.variable,
                    value=event.value,
                    line_number=event.line_number,
                    scope_id=event.scope_id,
                    execution_id=event.execution_id,
                    var_id=event.var_id,
                    access_path=event.access_path,
                    order=event.order,
                    access_paths=access_paths,
                )
            )
            continue

        existing = merged[existing_index]
        access_paths = tuple(dict.fromkeys((*existing.access_paths, event.access_path, *event.access_paths)))
        merged[existing_index] = VariableTraceEvent(
            variable=existing.variable,
            value=existing.value,
            line_number=existing.line_number,
            scope_id=existing.scope_id,
            execution_id=existing.execution_id,
            var_id=existing.var_id,
            access_path=existing.access_path,
            order=existing.order,
            access_paths=access_paths,
        )
    return merged


def _compact_event_orders(events: Sequence[VariableTraceEvent]) -> list[VariableTraceEvent]:
    order_by_execution: dict[tuple[int, int], int] = {}
    next_order = 1
    compacted: list[VariableTraceEvent] = []
    for event in events:
        key = (event.execution_id, event.line_number)
        order = order_by_execution.get(key)
        if order is None:
            order = next_order
            order_by_execution[key] = order
            next_order += 1
        compacted.append(
            VariableTraceEvent(
                variable=event.variable,
                value=event.value,
                line_number=event.line_number,
                scope_id=event.scope_id,
                execution_id=event.execution_id,
                var_id=event.var_id,
                access_path=event.access_path,
                order=order,
                access_paths=event.access_paths,
            )
        )
    return compacted


def _augment_pop_mutation_events(
    events: Sequence[VariableTraceEvent],
    source_code: str,
    filters: Sequence[WatchFilter],
) -> list[VariableTraceEvent]:
    mutation_lines = _pop_mutation_receivers(source_code)
    if not mutation_lines:
        return list(events)

    augmented: list[VariableTraceEvent] = []
    last_values: dict[str, Any] = {}
    next_var_id = max((event.var_id for event in events), default=0) + 1
    for event in events:
        mutation = mutation_lines.get(event.line_number)
        if mutation is not None:
            receiver_name = mutation.receiver
            if receiver_name in last_values and _is_watched_name(receiver_name, filters):
                synthetic_value = _simulate_pop_value(last_values[receiver_name], mutation, event.value)
                augmented.append(
                    VariableTraceEvent(
                        variable=receiver_name,
                        value=synthetic_value,
                        line_number=event.line_number,
                        scope_id=event.scope_id,
                        execution_id=event.execution_id,
                        var_id=next_var_id,
                        access_path=receiver_name,
                        order=event.order,
                        access_paths=(receiver_name,),
                    )
                )
                last_values[receiver_name] = synthetic_value
                next_var_id += 1
        augmented.append(event)
        last_values[event.variable] = event.value
    return augmented


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

    events: list[VariableTraceEvent] = []
    for index, snapshot in enumerate(limited, start=1):
        trace_name = snapshot.name
        for rule in filters:
            if rule.matches(snapshot):
                trace_name = rule.trace_name or rule.access_path or rule.name or snapshot.name
                break
        events.append(
            VariableTraceEvent(
                variable=trace_name,
                value=snapshot.value,
                line_number=snapshot.line_number,
                scope_id=snapshot.scope_id,
                execution_id=snapshot.execution_id,
                var_id=snapshot.var_id,
                access_path=snapshot.access_path,
                order=index,
            )
        )
    augmented = _augment_pop_mutation_events(events, source_code, filters)
    projected = _project_expression_watch_events(augmented, filters)
    return _compact_event_orders(_merge_duplicate_root_events(projected))


def build_traces(
    events: Sequence[VariableTraceEvent],
    *,
    name_factory: Callable[[str], str] | None = None,
) -> dict[str, Trace]:
    """Group trace events by variable name and convert them to Trace objects."""

    grouped: dict[str, list[Frame]] = defaultdict(list)
    for event in events:
        grouped[event.variable].append(
            Frame(
                step=event.execution_id,
                value=event.value,
                note=event.note(),
                meta={
                    "var_id": event.var_id,
                    "access_path": event.access_path,
                    "access_paths": list(event.access_paths or (event.access_path,)),
                    "scope_id": event.scope_id,
                    "line_number": event.line_number,
                    "execution_id": event.execution_id,
                    "order": event.order,
                },
            )
        )

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
        focus_path = frame.meta.get("access_path")
        if focus_path:
            cfg.focus_path_map[slot_name] = focus_path
        else:
            cfg.focus_path_map.pop(slot_name, None)
        artifacts.append(visualize(frame.value, name=slot_name, config=cfg))
    return artifacts


def visualize_traces(
    traces: Iterable[Trace],
    *,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
) -> dict[str, list[RenderedTraceFrame]]:
    """Render multiple traces at once while preserving each frame's global step."""

    cfg = config.copy() if config is not None else default_visualizer_config()
    rendered: dict[str, list[RenderedTraceFrame]] = {}
    for trace in traces:
        limit = cfg.step_limit_for(trace.name, override=max_steps)
        selected_steps = trace.frames if limit is None else trace.frames[:limit]
        artifacts = visualize_trace(trace, config=cfg, max_steps=max_steps)
        rendered[trace.name] = [
            RenderedTraceFrame(step=frame.step, artifact=artifact, meta=dict(frame.meta))
            for frame, artifact in zip(selected_steps, artifacts, strict=False)
        ]
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
) -> dict[str, list[RenderedTraceFrame]]:
    """Run StepTracer and render traces while preserving global execution steps."""

    events = trace_algorithm(
        source_code,
        watch_variables,
        tracer=tracer,
        globals_dict=globals_dict,
    )
    traces = build_traces(events, name_factory=name_factory)
    return visualize_traces(traces.values(), config=config, max_steps=max_steps)
