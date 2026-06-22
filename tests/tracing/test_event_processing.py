from __future__ import annotations

from collections import deque

from code_visualizer.tracing.filtering import WatchFilter
from code_visualizer.tracing.processing import (
    _augment_pop_mutation_events,
    _compact_event_orders,
    _extract_access_path_value,
    _literal_arg,
    _merge_duplicate_root_events,
    _pop_mutation_receivers,
    _project_expression_watch_events,
    _simulate_pop_value,
)
from code_visualizer.tracing.types import VariableTraceEvent


class _Object:
    def __init__(self, child: object | None = None) -> None:
        self.child = child


def _event(**overrides: object) -> VariableTraceEvent:
    base = dict(
        variable="data",
        value={"items": [1, 2, 3], "meta": {"count": 3}},
        line_number=1,
        scope_id=0,
        execution_id=1,
        var_id=1,
        access_path="data",
        order=1,
        access_paths=("data",),
    )
    base.update(overrides)
    return VariableTraceEvent(**base)


def test_literal_arg_only_accepts_ast_constants() -> None:
    import ast

    assert _literal_arg(ast.parse("1", mode="eval").body) == (True, 1)
    assert _literal_arg(ast.parse("x", mode="eval").body) == (False, None)


def test_pop_mutation_receivers_collects_popleft_and_pop_assignments() -> None:
    source = """\
node = queue.popleft()
last = items.pop()
value = buckets.pop(2)
noop(queue.pop())
"""

    mutations = _pop_mutation_receivers(source)

    assert mutations[1].receiver == "queue"
    assert mutations[1].method == "popleft"
    assert mutations[2].receiver == "items"
    assert mutations[2].method == "pop"
    assert mutations[2].has_argument is False
    assert mutations[3].argument == 2
    assert mutations[3].has_argument is True
    assert 4 not in mutations


def test_extract_access_path_value_supports_subscript_and_attribute() -> None:
    root = {"items": [{"name": "a"}], "obj": _Object(child=_Object(child=3))}

    assert _extract_access_path_value(root, "data['items'][0]['name']", "data") == "a"
    assert _extract_access_path_value(root, "data.obj.child.child", "data") == 3
    assert _extract_access_path_value(root, "other['items']", "data") is not None
    assert _extract_access_path_value(root, "data[dynamic]", "data") != "a"


def test_project_expression_watch_events_keeps_root_and_projects_child() -> None:
    event = _event(
        value={"items": [{"name": "a"}, {"name": "b"}]},
        access_path="data['items'][1]['name']",
        access_paths=("data['items'][1]['name']",),
    )
    filters = [
        WatchFilter(name="data"),
        WatchFilter(
            name="data", access_path="data['items']", trace_name="data['items']"
        ),
    ]

    projected = _project_expression_watch_events([event], filters)

    assert [item.variable for item in projected] == ["data", "data['items']"]
    assert projected[1].value == [{"name": "a"}, {"name": "b"}]
    assert projected[1].access_path == "data['items'][1]['name']"


def test_simulate_pop_value_handles_common_container_types() -> None:
    assert _simulate_pop_value(
        [1, 2, 3], _pop_mutation_receivers("x = items.pop()\n")[1], 3
    ) == [1, 2]
    assert _simulate_pop_value(
        (1, 2, 3), _pop_mutation_receivers("x = items.pop(0)\n")[1], 1
    ) == (2, 3)
    assert _simulate_pop_value(
        deque([1, 2]), _pop_mutation_receivers("x = items.popleft()\n")[1], 1
    ) == deque([2])
    assert _simulate_pop_value(
        {"a": 1, "b": 2}, _pop_mutation_receivers("x = items.pop('a')\n")[1], 1
    ) == {"b": 2}
    assert _simulate_pop_value(
        {1, 2}, _pop_mutation_receivers("x = items.pop()\n")[1], 1
    ) == {2}
    assert _simulate_pop_value(
        frozenset({1, 2}), _pop_mutation_receivers("x = items.pop()\n")[1], 1
    ) == frozenset({2})


def test_merge_duplicate_root_events_unions_access_paths() -> None:
    first = _event(access_path="data['a']", access_paths=("data['a']",))
    second = _event(access_path="data['b']", access_paths=("data['b']",))

    merged = _merge_duplicate_root_events([first, second])

    assert len(merged) == 1
    assert merged[0].access_paths == ("data['a']", "data['b']")


def test_compact_event_orders_reuses_order_for_same_execution_and_line() -> None:
    events = [
        _event(order=10, line_number=2, execution_id=1),
        _event(order=11, line_number=2, execution_id=1, variable="other", var_id=2),
        _event(order=12, line_number=3, execution_id=2, variable="third", var_id=3),
    ]

    compacted = _compact_event_orders(events)

    assert [item.order for item in compacted] == [1, 1, 2]


def test_compact_event_orders_reuses_order_for_contiguous_same_line_events() -> None:
    events = [
        _event(order=10, line_number=2, execution_id=1),
        _event(order=11, line_number=2, execution_id=2, variable="other", var_id=2),
        _event(order=12, line_number=3, execution_id=3, variable="third", var_id=3),
    ]

    compacted = _compact_event_orders(events)

    assert [item.order for item in compacted] == [1, 1, 2]


def test_compact_event_orders_keeps_non_contiguous_same_line_events_distinct() -> None:
    events = [
        _event(order=10, line_number=2, execution_id=1),
        _event(order=11, line_number=3, execution_id=2, variable="other", var_id=2),
        _event(order=12, line_number=2, execution_id=3, variable="third", var_id=3),
    ]

    compacted = _compact_event_orders(events)

    assert [item.order for item in compacted] == [1, 2, 3]


def test_augment_pop_mutation_events_inserts_synthetic_receiver_snapshot() -> None:
    events = [
        _event(
            variable="queue",
            value=deque(["A"]),
            line_number=1,
            execution_id=1,
            var_id=1,
            access_path="queue",
            access_paths=("queue",),
        ),
        _event(
            variable="node",
            value="A",
            line_number=2,
            execution_id=2,
            var_id=2,
            access_path="node",
            order=2,
            access_paths=("node",),
        ),
    ]

    augmented = _augment_pop_mutation_events(
        events,
        "queue = deque(['A'])\nnode = queue.popleft()\n",
        [WatchFilter(name="queue")],
    )

    queue_events = [item for item in augmented if item.variable == "queue"]
    assert len(queue_events) == 2
    assert list(queue_events[-1].value) == []
