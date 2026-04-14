from code_visualizer import default_visualizer_config
from code_visualizer.browser_api import build_browser_manifest_payload
from code_visualizer.builders.view_resolution import resolve_recursion_depth


def test_build_browser_manifest_payload_exposes_step_identity() -> None:
    config = default_visualizer_config()
    config.show_titles = False
    payload = build_browser_manifest_payload(
        "data = {'score': 1}\ndata['score'] = 2\n",
        watch_variables=["data"],
        config=config,
    )
    assert payload["manifest"]
    step = payload["manifest"][0]["steps"][0]
    assert step["step_id"] == "step 1"
    assert step["timeline_key"] == "0:1"
    assert step["title"] is None


def test_resolve_recursion_depth_prefers_variable_override_but_clamps_to_global_max() -> None:
    config = default_visualizer_config()
    config.recursion_depth_default = 1
    config.max_depth = 2
    config.recursion_depth_map["data"] = 5
    assert resolve_recursion_depth("data", [[1]], config) == 2
