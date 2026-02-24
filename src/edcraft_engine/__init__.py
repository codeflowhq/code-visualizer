"""Namespace package for the EdCraft code visualizer."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("code-visualizer")
except PackageNotFoundError:  # pragma: no cover - package not installed
    __version__ = "0.0.0"

__all__ = ["code_visualizer"]
