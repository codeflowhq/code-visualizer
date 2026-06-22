from code_visualizer.pipeline.resolver import resolve_recursion_depth
from code_visualizer.shared import default_visualizer_config
from code_visualizer.tracing.pipeline import visualize_algorithm


def test_visualize_algorithm_manifest_payload_exposes_step_identity() -> None:
    config = default_visualizer_config()
    config.show_titles = False
    payload = visualize_algorithm(
        "data = {'score': 1}\ndata['score'] = 2\n",
        watch_variables=["data"],
        config=config,
        output="manifest",
        payload=True,
    )
    assert payload["manifest"]
    step = payload["manifest"][0]["steps"][0]
    assert step["step_id"] == "step 1"
    assert step["timeline_key"] == "0:1"
    assert step["title"] is None


def test_resolve_recursion_depth_prefers_variable_override_but_clamps_to_global_max() -> (
    None
):
    config = default_visualizer_config()
    config.recursion_depth_default = 1
    config.max_depth = 2
    config.recursion_depth_map["data"] = 5
    assert resolve_recursion_depth("data", [[1]], config) == 2


def test_visualize_algorithm_rejects_unknown_output_mode() -> None:
    try:
        visualize_algorithm("data = [1]\n", output="unknown")  # type: ignore[arg-type]
    except ValueError as exc:
        assert "Unsupported trace output mode" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("visualize_algorithm should reject unknown output modes")


def test_visualize_algorithm_clamps_negative_max_steps_at_request_boundary() -> None:
    payload = visualize_algorithm(
        "data = [1]\ndata.append(2)\n",
        watch_variables=["data"],
        max_steps=-10,
        output="manifest",
        payload=True,
    )
    assert payload["manifest"] == []


def test_visualize_algorithm_rejects_payload_requests_for_frame_output() -> None:
    try:
        visualize_algorithm("data = [1]\n", output="frames", payload=True)
    except ValueError as exc:
        assert "payload=True requires output='manifest'" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("payload=True should be rejected for frame output")


def test_visualize_algorithm_surfaces_empty_watch_target_errors_at_api_boundary() -> None:
    try:
        visualize_algorithm("data = [1]\n", watch_variables=["   "])
    except ValueError as exc:
        assert "must not be empty strings" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Empty watch targets should be rejected")


def test_visualize_algorithm_accepts_mapping_watch_targets_with_access_paths() -> None:
    payload = visualize_algorithm(
        "data = {'meta': {'level': 1}}\ndata['meta']['level'] = 2\n",
        watch_variables=[{"access_path": 'data["meta"]'}],
        output="manifest",
        payload=True,
    )

    assert payload["manifest"]
    assert payload["manifest"][0]["variable"] == "data['meta']"


def test_visualize_algorithm_accepts_missing_and_empty_watch_lists() -> None:
    payload_without_watch = visualize_algorithm(
        "data = [1]\n",
        watch_variables=None,
        output="manifest",
        payload=True,
    )
    payload_with_empty_watch = visualize_algorithm(
        "data = [1]\n",
        watch_variables=[],
        output="manifest",
        payload=True,
    )

    assert payload_without_watch["manifest"]
    assert payload_with_empty_watch["manifest"]
    assert payload_without_watch["manifest"][0]["variable"] == "data"
    assert payload_with_empty_watch["manifest"][0]["variable"] == "data"


def test_visualize_algorithm_treats_zero_max_steps_as_empty_output() -> None:
    payload = visualize_algorithm(
        "data = [1]\ndata.append(2)\n",
        watch_variables=["data"],
        max_steps=0,
        output="manifest",
        payload=True,
    )

    assert payload["manifest"] == []
