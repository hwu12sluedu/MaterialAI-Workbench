from __future__ import annotations

import pytest

from material_ai_workbench.llm_adapter import (
    LlmChatConfig,
    LlmConfigError,
    plan_task_with_llm,
)
from material_ai_workbench.nl_tasks import task_from_dict


def test_plan_task_with_llm_parses_openai_compatible_response(monkeypatch) -> None:
    monkeypatch.setenv("UNIT_TEST_LLM_KEY", "secret")

    def fake_transport(url, headers, payload, timeout):
        assert url == "http://localhost:9999/v1/chat/completions"
        assert headers["Authorization"] == "Bearer secret"
        assert payload["model"] == "unit-model"
        return {"choices": [{"message": {"content": """
                        {
                          "task_type": "material_training_with_abaqus_check",
                          "material": {
                            "material_type": "hill",
                            "name": "llm_hill",
                            "youngs_modulus": 210000,
                            "poisson_ratio": 0.28,
                            "yield_strength": 72,
                            "hill_ratios": [1.1, 1.0, 0.9, 1.0, 1.0, 1.0]
                          },
                          "ml": {
                            "model": "svc",
                            "c_value": 1.5,
                            "gamma": 0.8,
                            "n_load_cases": 32,
                            "n_sequence": 3,
                            "test_size": 80,
                            "plot_mesh": 40,
                            "calculate_curves": true
                          },
                          "abaqus": {
                            "run_check": true,
                            "max_load_cases": 2,
                            "timeout_seconds": 900
                          },
                          "missing": [],
                          "warnings": []
                        }
                        """}}]}

    plan = plan_task_with_llm(
        "用 Hill 材料训练并做 Abaqus 验算",
        LlmChatConfig(
            base_url="http://localhost:9999/v1",
            model="unit-model",
            api_key_env="UNIT_TEST_LLM_KEY",
        ),
        transport=fake_transport,
    )
    task = task_from_dict(plan.task_payload, source_text="unit")

    assert task.material.material_type == "hill"
    assert task.material.name == "llm_hill"
    assert task.material.yield_strength == 72
    assert task.ml.calculate_curves is True
    assert task.abaqus.run_check is True
    assert task.abaqus.max_load_cases == 2


def test_llm_config_requires_key_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_LLM_KEY", raising=False)
    config = LlmChatConfig(
        base_url="http://localhost:9999/v1",
        model="unit-model",
        api_key_env="MISSING_LLM_KEY",
    )

    with pytest.raises(LlmConfigError):
        config.validate()


def test_task_from_dict_falls_back_for_invalid_values() -> None:
    task = task_from_dict(
        {
            "material": {
                "material_type": "unknown",
                "youngs_modulus": -1,
                "poisson_ratio": 0.9,
                "yield_strength": 0,
                "hill_ratios": [1, -1],
            },
            "ml": {"n_load_cases": 1, "n_sequence": 1, "test_size": 1},
            "abaqus": {"timeout_seconds": 1},
        },
        source_text="E=200000 nu=0.3 sy=60",
    )

    assert task.material.material_type == "j2"
    assert task.material.youngs_modulus == 200000
    assert task.material.poisson_ratio == 0.3
    assert task.material.yield_strength == 60
    assert task.ml.n_load_cases == 8
    assert task.ml.n_sequence == 2
    assert task.ml.test_size == 20
    assert task.abaqus.timeout_seconds == 60


def test_llm_case_grounding_filters_paths_ids_and_submission(monkeypatch) -> None:
    monkeypatch.setenv("UNIT_TEST_LLM_KEY", "secret")
    context = {
        "schema_version": "1.0",
        "grounding_id": "ground-1",
        "retrieval_method": "unit-test",
        "retrieved_case_ids": ["case_hill_plate"],
        "sensitive_path": "D:/private/do-not-send",
        "cases": [
            {
                "case_id": "case_hill_plate",
                "title": "Hill plate hole",
                "units": {"system": "mm-N-s-MPa"},
                "geometry": {"hole_radius": 5.0},
                "case_dir": "D:/private/do-not-send",
            }
        ],
    }

    def fake_transport(url, headers, payload, timeout):
        user_prompt = payload["messages"][1]["content"]
        assert "case_hill_plate" in user_prompt
        assert "D:/private/do-not-send" not in user_prompt
        return {"choices": [{"message": {"content": """
                        {
                          "task_type": "case_based_simulation",
                          "steps": [
                            {"action": "retrieve_case"},
                            {"action": "prepare_job"},
                            {"action": "submit_job"}
                          ],
                          "case_plan": {
                            "objective": "change hole radius",
                            "reference_case_ids": ["invented_case"],
                            "changes": [
                              {"parameter": "hole_radius", "from": 5, "to": 6, "unit": "mm"}
                            ],
                            "unit_system": "mm-N-s-MPa",
                            "submit_job": true
                          },
                          "missing": [],
                          "warnings": []
                        }
                        """}}]}

    plan = plan_task_with_llm(
        "参考历史带孔板案例，把孔径改成 6 mm",
        LlmChatConfig(
            base_url="http://localhost:9999/v1",
            model="unit-model",
            api_key_env="UNIT_TEST_LLM_KEY",
        ),
        transport=fake_transport,
        case_context=context,
    )

    assert plan.task_payload["case_plan"]["reference_case_ids"] == ["case_hill_plate"]
    assert plan.task_payload["case_plan"]["submit_job"] is False
    assert plan.task_payload["grounding"]["grounding_id"] == "ground-1"
    assert plan.task_payload["execution_policy"]["abaqus_submission_allowed"] is False
    assert any("invented_case" in warning for warning in plan.warnings)


def test_llm_grounding_keeps_non_case_task_behind_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("UNIT_TEST_LLM_KEY", "secret")
    context = {
        "schema_version": "1.0",
        "grounding_id": "ground-batch",
        "retrieval_method": "unit-test",
        "retrieved_case_ids": [],
        "cases": [],
    }

    def fake_transport(url, headers, payload, timeout):
        return {"choices": [{"message": {"content": """
                        {
                          "task_type": "batch_parameter_sweep",
                          "steps": [{"action": "create_sweep"}],
                          "batch": {
                            "name": "grounded_sweep",
                            "material_type": "j2",
                            "yield_strengths": [50, 60, 70]
                          },
                          "missing": [],
                          "warnings": []
                        }
                        """}}]}

    plan = plan_task_with_llm(
        "创建屈服强度扫描计划",
        LlmChatConfig(
            base_url="http://localhost:9999/v1",
            model="unit-model",
            api_key_env="UNIT_TEST_LLM_KEY",
        ),
        transport=fake_transport,
        case_context=context,
    )

    assert plan.task_payload["execution_policy"] == {
        "mode": "requires_user_confirmation",
        "abaqus_submission_allowed": False,
        "requires_user_confirmation": True,
    }
