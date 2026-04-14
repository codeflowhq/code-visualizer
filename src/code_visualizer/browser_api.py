from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import VisualizerConfig, default_visualizer_config
from .models import ArtifactKind
from .tracing.common import RenderedTraceFrame, WatchTarget
from .tracing.pipeline import visualize_algorithm


@dataclass(frozen=True, slots=True)
class BrowserManifestStep:
    step_id: str
    timeline_key: str
    index: int
    execution_id: int | None
    order: int | None
    title: str | None
    meta: dict[str, Any]
    kind: str
    dot: str | None = None
    svg: str | None = None


@dataclass(frozen=True, slots=True)
class BrowserManifestEntry:
    variable: str
    kind: str
    steps: list[BrowserManifestStep]


@dataclass(frozen=True, slots=True)
class BrowserManifest:
    manifest: list[BrowserManifestEntry]


def _step_payload(frame: RenderedTraceFrame) -> BrowserManifestStep:
    meta = dict(frame.meta)
    execution_id = meta.get("execution_id")
    order = meta.get("order")
    timeline_key = f"{execution_id if execution_id is not None else frame.step}:{order if order is not None else 0}"
    step_id = f"step {order if order is not None else frame.step}"
    kind = "dot" if frame.artifact.kind == ArtifactKind.GRAPHVIZ else "svg"
    return BrowserManifestStep(
        step_id=step_id,
        timeline_key=timeline_key,
        index=frame.step,
        execution_id=execution_id,
        order=order,
        title=frame.artifact.title,
        meta=meta,
        kind=kind,
        dot=frame.artifact.content if kind == "dot" else None,
        svg=frame.artifact.content if kind == "svg" else None,
    )


def build_browser_manifest(
    source_code: str,
    *,
    watch_variables: list[WatchTarget] | None = None,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
) -> BrowserManifest:
    cfg = config.copy() if config is not None else default_visualizer_config()
    rendered = visualize_algorithm(
        source_code,
        watch_variables=watch_variables,
        config=cfg,
        max_steps=max_steps,
    )
    manifest: list[BrowserManifestEntry] = []
    for variable, frames in rendered.items():
        steps = [_step_payload(frame) for frame in frames]
        kind = steps[0].kind if steps else "dot"
        manifest.append(BrowserManifestEntry(variable=variable, kind=kind, steps=steps))
    return BrowserManifest(manifest=manifest)


def build_browser_manifest_payload(
    source_code: str,
    *,
    watch_variables: list[WatchTarget] | None = None,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    manifest = build_browser_manifest(
        source_code,
        watch_variables=watch_variables,
        config=config,
        max_steps=max_steps,
    )
    return {"manifest": [asdict(entry) for entry in manifest.manifest]}


def visualize_algorithm_manifest(
    source_code: str,
    *,
    watch_variables: list[WatchTarget] | None = None,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
) -> BrowserManifest:
    return build_browser_manifest(
        source_code,
        watch_variables=watch_variables,
        config=config,
        max_steps=max_steps,
    )


def visualize_algorithm_manifest_payload(
    source_code: str,
    *,
    watch_variables: list[WatchTarget] | None = None,
    config: VisualizerConfig | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    return build_browser_manifest_payload(
        source_code,
        watch_variables=watch_variables,
        config=config,
        max_steps=max_steps,
    )


__all__ = [
    "BrowserManifest",
    "BrowserManifestEntry",
    "BrowserManifestStep",
    "build_browser_manifest",
    "build_browser_manifest_payload",
    "visualize_algorithm_manifest",
    "visualize_algorithm_manifest_payload",
]
