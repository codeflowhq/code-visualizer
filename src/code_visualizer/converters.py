"""Value converter utilities for handling heterogeneous data inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence, Tuple

try:  # pragma: no cover - optional dependency
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - numpy optional
    _np = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import pandas as _pd  # type: ignore
except Exception:  # pragma: no cover - pandas optional
    _pd = None  # type: ignore


ConverterResult = Tuple[bool, Any]
ValueConverter = Callable[[Any], ConverterResult]


@dataclass(frozen=True, slots=True)
class ConverterPipeline:
    """Composable one-shot converter pipeline that runs per recursion layer."""

    converters: tuple[ValueConverter, ...]

    def coerce(self, value: Any) -> tuple[Any, bool]:
        for converter in self.converters:
            handled, converted = converter(value)
            if handled:
                return converted, True
        return value, False

    def with_converters(self, *extra: ValueConverter, prepend: bool = False) -> ConverterPipeline:
        if not extra:
            return self
        if prepend:
            return ConverterPipeline(tuple(extra) + self.converters)
        return ConverterPipeline(self.converters + tuple(extra))

    def extend(self, converters: Iterable[ValueConverter], *, prepend: bool = False) -> ConverterPipeline:
        additions = tuple(converters)
        if not additions:
            return self
        if prepend:
            return ConverterPipeline(additions + self.converters)
        return ConverterPipeline(self.converters + additions)


def numpy_array_converter(value: Any) -> ConverterResult:
    if _np is not None and isinstance(value, _np.ndarray):  # type: ignore[has-type]
        return True, value.tolist()
    return False, value


def pandas_converter(value: Any) -> ConverterResult:
    if _pd is None:
        return False, value
    if isinstance(value, _pd.DataFrame):  # type: ignore[has-type]
        return True, value.to_dict(orient="list")
    if isinstance(value, _pd.Series):  # type: ignore[has-type]
        return True, value.to_dict()
    return False, value


def deque_converter(value: Any) -> ConverterResult:
    if isinstance(value, _deque):
        return True, list(value)
    return False, value


def identity_converter(value: Any) -> ConverterResult:
    return False, value


def apply_converter_pipeline(
    value: Any,
    converters: Sequence[ValueConverter],
) -> tuple[Any, bool]:
    """Legacy helper retained for backwards compatibility."""

    pipeline = ConverterPipeline(tuple(converters))
    return pipeline.coerce(value)


DEFAULT_CONVERTERS: tuple[ValueConverter, ...] = (
    numpy_array_converter,
    pandas_converter,
    identity_converter,
)


def default_converter_pipeline() -> ConverterPipeline:
    return ConverterPipeline(DEFAULT_CONVERTERS)


__all__ = [
    "ConverterPipeline",
    "ConverterResult",
    "ValueConverter",
    "apply_converter_pipeline",
    "default_converter_pipeline",
    "DEFAULT_CONVERTERS",
    "numpy_array_converter",
    "pandas_converter",
]
