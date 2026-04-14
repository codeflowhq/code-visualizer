from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..view_types import ViewKind
from .image_sources import _looks_like_image_candidate
from .structure_detection import _collect_linked_list_labels, _tree_children

_TYPE_PATTERN_SAMPLE = 8
_TYPE_PATTERN_CACHE: dict[str, "_TypePattern"] = {}


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _normalize_view_name(name: str) -> str:
    return "".join(ch for ch in name.strip() if not ch.isspace())


def _match_named_override(name: str, mapping: Mapping[str, ViewKind] | None) -> ViewKind | None:
    if not mapping:
        return None
    normalized = _normalize_view_name(name)
    for raw_key, view in mapping.items():
        if isinstance(raw_key, str) and _normalize_view_name(raw_key) == normalized:
            return view
    return None


@dataclass(frozen=True)
class _TypePattern:
    kind: str
    args: tuple["_TypePattern", ...] = ()


class _TypePatternParser:
    def __init__(self, text: str):
        self.text = text
        self.length = len(text)
        self.pos = 0

    def parse(self) -> _TypePattern:
        node = self._parse_pattern()
        self._skip_ws()
        if self.pos != self.length:
            raise ValueError(f"unexpected trailing characters at position {self.pos}")
        return node

    def _parse_pattern(self) -> _TypePattern:
        self._skip_ws()
        ident = self._parse_identifier()
        args: list[_TypePattern] = []
        self._skip_ws()
        if self._peek() == "[":
            self.pos += 1
            while True:
                self._skip_ws()
                if self._peek() == "]":
                    self.pos += 1
                    break
                args.append(self._parse_pattern())
                self._skip_ws()
                ch = self._peek()
                if ch == ",":
                    self.pos += 1
                    continue
                if ch == "]":
                    self.pos += 1
                    break
                raise ValueError(f"expected ',' or ']' at position {self.pos}")
        return _TypePattern(kind=ident, args=tuple(args))

    def _parse_identifier(self) -> str:
        self._skip_ws()
        start = self.pos
        while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in {"_", "."}):
            self.pos += 1
        if start == self.pos:
            raise ValueError(f"expected identifier at position {self.pos}")
        return self.text[start:self.pos].lower()

    def _skip_ws(self) -> None:
        while self.pos < self.length and self.text[self.pos].isspace():
            self.pos += 1

    def _peek(self) -> str | None:
        if self.pos >= self.length:
            return None
        return self.text[self.pos]


def _compile_type_pattern(spec: str) -> _TypePattern:
    key = spec.strip()
    if not key:
        raise ValueError("type pattern cannot be empty")
    cached = _TYPE_PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    pattern = _TypePatternParser(key).parse()
    _TYPE_PATTERN_CACHE[key] = pattern
    return pattern


def _sample_iterable(seq: Any, limit: int) -> list[Any]:
    if limit <= 0:
        return []
    if isinstance(seq, list):
        return seq[:limit]
    if isinstance(seq, tuple):
        return list(seq[:limit])
    sample: list[Any] = []
    for item in seq:
        sample.append(item)
        if len(sample) >= limit:
            break
    return sample


def _matches_type_pattern(value: Any, pattern: _TypePattern) -> bool:
    kind = pattern.kind
    if kind in {"any", "object"}:
        return True
    if kind == "none":
        return value is None
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return isinstance(value, float)
    if kind == "number":
        return _is_number(value)
    if kind == "str":
        return isinstance(value, str)
    if kind == "bytes":
        return isinstance(value, (bytes, bytearray))
    if kind == "path":
        return isinstance(value, Path)
    if kind == "list":
        if not isinstance(value, list):
            return False
        if not pattern.args:
            return True
        child = pattern.args[0]
        return all(_matches_type_pattern(item, child) for item in _sample_iterable(value, _TYPE_PATTERN_SAMPLE))
    if kind == "tuple":
        if not isinstance(value, tuple):
            return False
        if not pattern.args:
            return True
        if len(pattern.args) == len(value) and len(pattern.args) > 1:
            return all(_matches_type_pattern(item, sub) for item, sub in zip(value, pattern.args, strict=False))
        child = pattern.args[0]
        return all(_matches_type_pattern(item, child) for item in _sample_iterable(value, _TYPE_PATTERN_SAMPLE))
    if kind == "set":
        if not isinstance(value, set):
            return False
        if not pattern.args:
            return True
        child = pattern.args[0]
        return all(_matches_type_pattern(item, child) for item in _sample_iterable(value, _TYPE_PATTERN_SAMPLE))
    if kind == "frozenset":
        if not isinstance(value, frozenset):
            return False
        if not pattern.args:
            return True
        child = pattern.args[0]
        return all(_matches_type_pattern(item, child) for item in _sample_iterable(value, _TYPE_PATTERN_SAMPLE))
    if kind == "dict":
        if not isinstance(value, dict):
            return False
        if not pattern.args:
            return True
        sampled_items = _sample_iterable(value.items(), _TYPE_PATTERN_SAMPLE)
        if len(pattern.args) == 1:
            value_pattern = pattern.args[0]
            return all(_matches_type_pattern(item_value, value_pattern) for _, item_value in sampled_items)
        key_pattern, value_pattern = pattern.args[0], pattern.args[1]
        return all(_matches_type_pattern(k, key_pattern) and _matches_type_pattern(v, value_pattern) for k, v in sampled_items)
    if kind == "linked_list":
        return _collect_linked_list_labels(value, max_nodes=2) is not None
    if kind == "tree":
        return _tree_children(value) is not None
    return False


def _match_type_pattern_override(value: Any, mapping: Mapping[str, ViewKind] | None) -> ViewKind | None:
    if not mapping or _looks_like_image_candidate(value):
        return None
    for pattern_text, view in mapping.items():
        try:
            pattern = _compile_type_pattern(pattern_text)
        except ValueError as exc:
            raise ValueError(f"Invalid DEFAULT_VIEW_TYPE_MAP entry '{pattern_text}': {exc}") from exc
        if _matches_type_pattern(value, pattern):
            return view
    return None
