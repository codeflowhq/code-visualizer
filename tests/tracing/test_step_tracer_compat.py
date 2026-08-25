from code_visualizer.tracing.step_tracer_compat import patch_step_tracer_models


def test_patch_step_tracer_models_adds_reset_args_to_statement_execution() -> None:
    from step_tracer.models import BranchExecution, LoopIteration

    patch_step_tracer_models()

    branch = BranchExecution(
        execution_id=1,
        scope_id=0,
        line_number=1,
        condition_str="x > 0",
        condition_result=True,
    )
    loop_iteration = LoopIteration(
        execution_id=2,
        scope_id=0,
        line_number=2,
        iteration_num=0,
        loop_execution_id=1,
    )

    assert branch.reset_args() is None
    assert branch.add_arg("x", 1) is None
    assert branch.set_func_def_line_num(12) is None
    assert branch.set_return_value("ok") is None
    assert loop_iteration.reset_args() is None
