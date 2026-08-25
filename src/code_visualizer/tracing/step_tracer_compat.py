from __future__ import annotations

from typing import Any


def patch_step_tracer_models() -> None:
    """Patch missing no-op APIs expected by some step-tracer builds."""

    try:  # pragma: no cover - soft dependency
        from step_tracer.models import StatementExecution  # type: ignore
    except Exception:  # pragma: no cover - tracer optional
        return

    if hasattr(StatementExecution, "reset_args"):
        existing_methods = set(dir(StatementExecution))
    else:
        existing_methods = set()

    def reset_args(self: Any) -> None:
        return None

    def add_arg(self: Any, _name: str, _value: Any) -> None:
        return None

    def set_func_def_line_num(self: Any, _line_num: int) -> None:
        return None

    def set_return_value(self: Any, _return_value: Any) -> None:
        return None

    compatibility_methods = {
        "reset_args": reset_args,
        "add_arg": add_arg,
        "set_func_def_line_num": set_func_def_line_num,
        "set_return_value": set_return_value,
    }

    for name, method in compatibility_methods.items():
        if name in existing_methods:
            continue
        setattr(StatementExecution, name, method)
