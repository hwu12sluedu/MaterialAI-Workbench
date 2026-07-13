from __future__ import annotations

from material_ai_workbench.nl_tasks import parse_natural_language_task
from material_ai_workbench.task_schema import build_executable_plan, infer_steps


def test_composite_surrogate_prompt_infers_full_execution_plan() -> None:
    task = parse_natural_language_task(
        "做一个 Vf=0.6 的碳纤维复合材料带孔板仿真，跑 Abaqus，然后训练代理模型预测应力并生成报告"
    )
    payload = task.to_dict()
    plan = build_executable_plan(payload)
    actions = [step.action for step in plan.steps]

    assert task.task_type == "composite_plate_hole"
    assert actions[:3] == ["generate_rve", "run_pbc", "solve_plate"]
    assert "train_models" in actions
    assert "generate_report" in actions
    assert any(step.requires_abaqus for step in plan.steps)


def test_explicit_llm_steps_are_preserved() -> None:
    payload = {
        "task_type": "surrogate_training",
        "steps": [{"action": "export_dataset"}, {"action": "train_models"}, {"action": "compare"}],
        "surrogate": {"dataset_dir": "demo", "target_column": "max_mises", "models": ["random_forest", "gbr"]},
    }

    assert [step["action"] for step in infer_steps(payload)] == ["export_dataset", "train_models", "compare"]
