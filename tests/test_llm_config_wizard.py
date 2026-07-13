from __future__ import annotations

from pathlib import Path

from material_ai_workbench.llm_adapter import (
    LlmChatConfig,
    llm_config_from_env,
    save_llm_config,
    test_llm_connection as run_llm_connection_test,
)
from material_ai_workbench.nl_tasks import task_from_dict, task_to_workbench_config


def test_save_and_load_llm_config_env_file(tmp_path) -> None:
    env_path = tmp_path / ".env"
    config = LlmChatConfig(
        provider_name="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        require_api_key=True,
    )

    save_llm_config(config, api_key_value="unit-secret", env_path=env_path)
    loaded = llm_config_from_env(env_path)

    assert loaded.provider_name == "deepseek"
    assert loaded.base_url == "https://api.deepseek.com/v1"
    assert loaded.model == "deepseek-chat"
    assert loaded.api_key_env == "DEEPSEEK_API_KEY"
    assert loaded.api_key == "unit-secret"


def test_test_llm_connection_validates_task_json(monkeypatch) -> None:
    monkeypatch.setenv("UNIT_TEST_LLM_KEY", "secret")

    def fake_transport(_url, _headers, _payload, _timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"task_type":"material_training","material":{"material_type":"j2","name":"ping","youngs_modulus":200000,"poisson_ratio":0.3,"yield_strength":60,"hill_ratios":[1,1,1,1,1,1]},"ml":{"model":"svc","c_value":1,"gamma":1,"n_load_cases":8,"n_sequence":2,"test_size":20,"plot_mesh":20,"calculate_curves":false},"abaqus":{"run_check":false,"max_load_cases":1,"timeout_seconds":1200},"missing":[],"warnings":[]}'
                    }
                }
            ]
        }

    result = run_llm_connection_test(
        LlmChatConfig(
            base_url="http://localhost:9999/v1",
            model="unit-model",
            api_key_env="UNIT_TEST_LLM_KEY",
        ),
        transport=fake_transport,
    )

    assert result.ok is True
    assert result.task_payload is not None
    assert result.task_payload["task_type"] == "material_training"


def test_barlat_llm_payload_reaches_workbench_config() -> None:
    task = task_from_dict(
        {
            "material": {
                "material_type": "barlat",
                "name": "llm_barlat",
                "youngs_modulus": 70000,
                "poisson_ratio": 0.33,
                "yield_strength": 180,
                "barlat_alphas": [0.9, 1.05, 0.85, 1.0, 1.0, 1.0, 0.95, 1.1],
                "barlat_exponent": 8,
            },
            "ml": {"n_load_cases": 16, "n_sequence": 2, "test_size": 30},
            "abaqus": {"run_check": False},
        },
        source_text="barlat",
    )
    output_dir = Path(".")
    config = task_to_workbench_config(task, output_dir)

    assert config.material_type == "barlat"
    assert config.barlat_alphas == (0.9, 1.05, 0.85, 1.0, 1.0, 1.0, 0.95, 1.1)
    assert config.barlat_exponent == 8
    assert config.output_dir == output_dir
