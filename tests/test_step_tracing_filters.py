from code_visualizer.step_tracing import (
    _access_path_matches,
    _normalize_access_path,
    _normalize_watch_filters,
)


def test_normalize_access_path_normalizes_quotes() -> None:
    assert _normalize_access_path('data["meta"]["level"]') == "data['meta']['level']"


def test_access_path_matches_descendants() -> None:
    assert _access_path_matches('data["meta"]', "data['meta']['level']")
    assert _access_path_matches("data['meta']", "data['meta']")
    assert not _access_path_matches("data['meta']", "data['other']")


def test_normalize_watch_filters_keeps_trace_name_for_expressions() -> None:
    filters = _normalize_watch_filters(["data", 'data["meta"]'])
    assert filters[0].trace_name == 'data["meta"]'
    assert filters[0].access_path == 'data["meta"]'
    assert filters[0].name == "data"
    assert filters[1].name == "data"
