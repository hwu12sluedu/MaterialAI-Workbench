"""LLM-assisted parameter recommendation for MaterialAI Workbench."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from material_ai_workbench.llm_adapter import LlmChatConfig, _chat_completion, _llm_available
from material_ai_workbench.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class ParamRecommendation:
    material_type: str
    parameters: dict[str, Any]
    rationale: str
    caveats: str
    references: list[str]


def recommend_parameters(
    material_description: str,
    *,
    config: LlmChatConfig | None = None,
) -> ParamRecommendation | None:
    """Recommend starter parameters from a natural-language material description."""

    cfg = config or LlmChatConfig()
    if not _llm_available(cfg):
        return None
    system_prompt = """You are a materials engineer specializing in metal forming and FEA.
Return JSON only with these fields:
material_type: j2, hill, or barlat
youngs_modulus: MPa
poisson_ratio
yield_strength: MPa
hill_ratios: list of 6 positive numbers or null
c_value
gamma
n_load_cases
n_sequence
rationale: Chinese explanation
caveats: Chinese caveats
references: list of standards, datasheets, or textbook topics.
Default to j2 for isotropic bulk metals, hill for rolled sheet anisotropy, and barlat for aluminum sheet forming when anisotropy matters.
"""
    raw = _chat_completion(system_prompt, material_description, config=cfg, json_response=True)
    try:
        data = json.loads(raw)
        return ParamRecommendation(
            material_type=str(data["material_type"]).lower(),
            parameters={
                "youngs_modulus": float(data["youngs_modulus"]),
                "poisson_ratio": float(data["poisson_ratio"]),
                "yield_strength": float(data["yield_strength"]),
                "hill_ratios": data.get("hill_ratios"),
                "c_value": float(data["c_value"]),
                "gamma": float(data["gamma"]),
                "n_load_cases": int(data["n_load_cases"]),
                "n_sequence": int(data["n_sequence"]),
            },
            rationale=str(data.get("rationale", "")),
            caveats=str(data.get("caveats", "")),
            references=[str(item) for item in data.get("references", [])],
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to parse parameter recommendation: %s", exc)
        return None
