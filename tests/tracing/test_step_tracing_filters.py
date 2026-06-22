from code_visualizer.tracing.filtering import (
    WatchFilter,
    _normalize_access_path,
    normalize_trace_watch_filters,
    trace_access_path_matches,
)
from code_visualizer.tracing.pipeline import (
    _focus_path_from_frame_meta,
    _project_expression_watch_events,
    trace_algorithm,
)
from code_visualizer.tracing.types import VariableTraceEvent


def test_normalize_access_path_normalizes_quotes() -> None:
    assert _normalize_access_path('data["meta"]["level"]') == "data['meta']['level']"


def testtrace_access_path_matches_descendants() -> None:
    assert trace_access_path_matches('data["meta"]', "data['meta']['level']")
    assert trace_access_path_matches("data['meta']", "data['meta']")
    assert not trace_access_path_matches("data['meta']", "data['other']")


def testnormalize_trace_watch_filters_keeps_trace_name_for_expressions() -> None:
    filters = normalize_trace_watch_filters(["data", 'data["meta"]'])
    assert filters[0].trace_name == 'data["meta"]'
    assert filters[0].access_path == "data['meta']"
    assert filters[0].name == "data"
    assert filters[1].name == "data"


def test_normalize_trace_watch_filters_trims_and_derives_mapping_root() -> None:
    filters = normalize_trace_watch_filters(
        [{"access_path": '  data["meta"]  ', "scope_id": 3, "line_number": 8}]
    )

    assert filters == [
        WatchFilter(
            name="data",
            access_path="data['meta']",
            trace_name="data['meta']",
            scope_id=3,
            line_number=8,
        )
    ]


def test_normalize_trace_watch_filters_rejects_empty_strings_and_empty_mappings() -> None:
    try:
        normalize_trace_watch_filters(["   "])
    except ValueError as exc:
        assert "must not be empty strings" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected empty watch strings to be rejected")

    try:
        normalize_trace_watch_filters([{}])
    except ValueError as exc:
        assert "include at least one selector" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected empty watch mappings to be rejected")


def test_normalize_trace_watch_filters_rejects_invalid_scope_types() -> None:
    try:
        normalize_trace_watch_filters([{"name": "data", "scope_id": "one"}])
    except TypeError as exc:
        assert "scope_id must be an integer" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected invalid scope_id types to be rejected")


def test_expression_watch_preserves_nested_focus_path() -> None:
    event = VariableTraceEvent(
        variable="data",
        value={"users": [{"id": 1}, {"id": 2, "tags": ["z", "d"]}]},
        line_number=8,
        scope_id=0,
        execution_id=2,
        var_id=3,
        access_path="data['users'][1]['tags'][0]",
        order=4,
        access_paths=("data['users'][1]['tags'][0]",),
    )

    projected = _project_expression_watch_events(
        [event],
        [
            WatchFilter(
                name="data", access_path='data["users"]', trace_name='data["users"]'
            )
        ],
    )

    assert len(projected) == 1
    assert projected[0].variable == 'data["users"]'
    assert projected[0].value == [{"id": 1}, {"id": 2, "tags": ["z", "d"]}]
    assert projected[0].access_path == "data['users'][1]['tags'][0]"
    assert projected[0].access_paths == ("data['users'][1]['tags'][0]",)


def test_focus_path_prefers_specific_access_path() -> None:
    assert (
        _focus_path_from_frame_meta(
            {
                "access_path": "data",
                "access_paths": ["data", "data['users'][1]['tags'][0]"],
            }
        )
        == "data['users'][1]['tags'][0]"
    )


def test_root_and_expression_watches_both_keep_nested_updates() -> None:
    source = """\
data = {"users": [{"tags": ["a"]}, {"tags": ["b"]}]}
data["users"][1]["tags"][0] = "z"
"""

    events = trace_algorithm(source, ["data", 'data["users"]'])
    data_paths = [event.access_path for event in events if event.variable == "data"]
    users_paths = [
        event.access_path for event in events if event.variable == 'data["users"]'
    ]

    assert "data['users'][1]['tags'][0]" in data_paths
    assert "data['users'][1]['tags'][0]" in users_paths
