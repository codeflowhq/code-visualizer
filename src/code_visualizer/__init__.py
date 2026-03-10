"""Primary public API surface for code_visualizer."""

from .config import VisualizerConfig, default_visualizer_config
from .graph_builder import visualize
from .step_tracing import (
    StepTracerUnavailableError,
    VariableTraceEvent,
    build_traces,
    trace_algorithm,
    visualize_trace,
    visualize_traces,
)
from .view_types import ViewKind

__all__ = [
    "VisualizerConfig",
    "ViewKind",
    "StepTracerUnavailableError",
    "VariableTraceEvent",
    "build_traces",
    "default_visualizer_config",
    "trace_algorithm",
    "visualize",
    "visualize_trace",
    "visualize_traces",
]
