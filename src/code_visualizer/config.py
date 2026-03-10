"""Configuration helpers for the visualization pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from .converters import ConverterPipeline, ValueConverter, default_converter_pipeline
from .view_types import ViewKind, ViewOverrideMap, ensure_view_kind


def _default_nested_depth_map() -> dict[str | type[Any], int]:
    return {list: 4, tuple: 4, dict: 4}


def _default_allowed_formats() -> set[str]:
    return {"svg", "png", "jpg"}


@dataclass(slots=True)
class VisualizerConfig:
    """Runtime configuration bundle for all visualization helpers."""

    view_map: dict[str | type[Any], ViewKind] = field(default_factory=dict)
    view_name_map: dict[str, ViewKind] = field(default_factory=dict)
    view_type_map: dict[str, ViewKind] = field(default_factory=dict)
    nested_depth_default: int = -1
    nested_depth_map: dict[str | type[Any], int] = field(default_factory=_default_nested_depth_map)
    auto_nested_depth_cap: int = 6
    output_format: str = "png"
    allowed_output_formats: set[str] = field(default_factory=_default_allowed_formats)
    converter_pipeline: ConverterPipeline = field(default_factory=default_converter_pipeline)

    def ensure_output_format(self, fmt: str | None) -> str:
        """Clamp requested output formats to the allowed list."""

        if not fmt:
            return self.output_format
        normalized = fmt.lower()
        if normalized == "jpeg":
            normalized = "jpg"
        if normalized not in self.allowed_output_formats:
            return self.output_format
        return normalized

    def with_converters(
        self,
        *extra: ValueConverter,
        prepend: bool = False,
    ) -> VisualizerConfig:
        """Return a cloned config with an updated converter pipeline."""

        if not extra:
            return self
        updated = self.converter_pipeline.with_converters(*extra, prepend=prepend)
        return replace(self, converter_pipeline=updated)

    def copy(self) -> VisualizerConfig:
        """Explicit shallow copy helper."""

        return replace(
            self,
            view_map=dict(self.view_map),
            view_name_map=dict(self.view_name_map),
            view_type_map=dict(self.view_type_map),
            nested_depth_map=dict(self.nested_depth_map),
            allowed_output_formats=set(self.allowed_output_formats),
            converter_pipeline=ConverterPipeline(self.converter_pipeline.converters),
        )


def default_visualizer_config() -> VisualizerConfig:
    """Factory for baseline configuration – callers can mutate their copy."""

    return VisualizerConfig()


def merge_override_map(
    base: Mapping[str | type[Any], ViewKind],
    updates: Mapping[str | type[Any], ViewKind] | None,
) -> dict[str | type[Any], ViewKind]:
    """Merge override maps while normalizing ViewKind entries."""

    merged: dict[str | type[Any], ViewKind] = dict(base)
    if not updates:
        return merged
    for key, view in updates.items():
        merged[key] = ensure_view_kind(view)
    return merged


__all__ = [
    "VisualizerConfig",
    "default_visualizer_config",
    "merge_override_map",
]
