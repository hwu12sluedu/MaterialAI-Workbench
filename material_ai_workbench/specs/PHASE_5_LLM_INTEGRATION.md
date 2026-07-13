# Phase 5: LLM Deep Integration

## Objective
Go beyond simple task JSON generation. Let LLM interpret reports, recommend parameters, and explain engineering significance.

## Prerequisites
- Phase 0 (config.py) required
- Phase 1.2 (logging) recommended
- Existing `llm_adapter.py` and `nl_tasks.py` functional

---

## Task 5.1: LLM-Assisted Report Interpretation

### Context
Current reports (material_model_report.md, surrogate_report.md, closed_loop_report.md) are factual but terse. An LLM can add engineering interpretation: "The low F1 score suggests the yield surface has sharp corners that SVC struggles to fit. Consider increasing gamma or using more load directions."

### File to modify
`D:\githubproject\pyLabFEA\material_ai_workbench\llm_adapter.py`

### Changes

#### a) Add `interpret_report()` function
```python
def interpret_report(report_text: str, report_type: str = "material_model") -> str | None:
    """Ask the LLM to interpret a MaterialAI Workbench report.

    Args:
        report_text: The full markdown report content.
        report_type: "material_model", "surrogate", "closed_loop", or "batch".

    Returns:
        LLM-generated interpretation text, or None if LLM is not configured.
    """
    if not _llm_available():
        return None

    prompts = {
        "material_model": (
            "你是一位材料力学专家。请阅读以下材料模型训练报告，"
            "用2-3段中文解释：(1) 模型质量如何，(2) 屈服面拟合是否合理，"
            "(3) 下一步改进建议。用工程师能理解的语言，不要罗列数据。\n\n"
        ),
        "surrogate": (
            "你是一位机器学习与有限元仿真交叉领域的专家。请阅读以下代理模型训练报告，"
            "用2-3段中文解释：(1) 模型预测精度是否可接受，"
            "(2) 当前样本量是否足够，(3) 改进建议。"
        ),
        "closed_loop": (
            "你是一位仿真验证工程师。请阅读以下闭环验证报告，"
            "用2-3段中文总结：(1) 管线完整性，(2) 关键断点在哪里，"
            "(3) 是否可以进入下一阶段。"
        ),
        "batch": (
            "你是一位实验设计专家。请阅读以下批量参数扫描报告，"
            "用2-3段中文总结：(1) 参数趋势是否合理，(2) 是否有异常点，"
            "(3) 建议的下一步扫描范围。"
        ),
    }

    system_prompt = prompts.get(report_type, prompts["material_model"])
    user_prompt = f"以下是报告原文：\n\n{report_text[:3000]}"  # Truncate for token limits

    response = _chat_completion(system_prompt, user_prompt)
    return response
```

#### b) Add `_chat_completion()` helper
Refactor the existing `plan_task_with_llm()` to share a common `_chat_completion()` function that sends a prompt and returns the response text.

#### c) Integrate into `streamlit_app.py`

In the Results Browser tab, add an "AI Interpretation" expander below each report view. When expanded:
1. Shows a "Generate Interpretation" button
2. On click, reads the report file, calls `interpret_report()`
3. Shows the LLM response in a styled info box
4. Caches the interpretation so it doesn't re-call the API

Example UI in `_show_run_summary()`:
```python
with st.expander("AI Interpretation"):
    if st.button("Generate Interpretation"):
        with st.spinner("LLM analyzing report..."):
            report_text = Path(result.report_path).read_text()
            interpretation = interpret_report(report_text, "material_model")
            if interpretation:
                st.info(interpretation)
            else:
                st.warning("LLM not configured. Set MATERIALAI_LLM_API_KEY.")
```

### Acceptance Criteria
- Click "Generate Interpretation" on a material report → 2-3 paragraph Chinese analysis appears
- LLM not configured → clear message with env var names
- Interpretation varies based on actual report content (not a template)
- Interpretation is cached per report (re-clicking doesn't re-call API)

---

## Task 5.2: Conversational Parameter Recommendation

### Context
New users don't know what C, gamma, or n_load_cases to use. An LLM can recommend parameters based on natural language: "我想模拟一个铝合金5182-O的冲压成形" → recommended parameters with rationale.

### File to modify: create `param_recommender.py`

```python
"""LLM-based parameter recommendation for material simulation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from material_ai_workbench.llm_adapter import _chat_completion, _llm_available
from material_ai_workbench.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ParamRecommendation:
    material_type: str
    parameters: dict[str, Any]
    rationale: str
    caveats: str
    references: list[str]


def recommend_parameters(material_description: str) -> ParamRecommendation | None:
    """Recommend simulation parameters based on a natural language description.

    Example input: "铝合金6061-T6板材，厚度1.5mm，冲压成形仿真"
    """
    if not _llm_available():
        return None

    system_prompt = """You are a materials engineer specializing in metal forming simulation.
Given a description of a material and simulation scenario, recommend parameters for
the pyLabFEA MaterialAI Workbench.

Output as JSON with these fields:
- material_type: "j2", "hill", or "barlat"
- youngs_modulus: in MPa
- poisson_ratio: dimensionless
- yield_strength: in MPa
- hill_ratios: [r1, r2, r3, r4, r5, r6] (only for hill, otherwise null)
- c_value: SVC regularization (0.5-5.0)
- gamma: SVC kernel width (0.1-5.0)
- n_load_cases: number of load directions (20-100)
- n_sequence: elastic-plastic sampling levels (2-8)
- rationale: 2-3 sentence explanation in Chinese
- caveats: any limitations or assumptions in Chinese
- references: list of relevant standards or references

Base recommendations on known material properties for the described material.
Default to J2 for isotropic materials, Hill for rolled sheet, Barlat for aluminum.
"""

    response = _chat_completion(system_prompt, material_description)

    try:
        data = json.loads(response)
        return ParamRecommendation(
            material_type=data["material_type"],
            parameters={
                "youngs_modulus": data["youngs_modulus"],
                "poisson_ratio": data["poisson_ratio"],
                "yield_strength": data["yield_strength"],
                "hill_ratios": data.get("hill_ratios"),
                "c_value": data["c_value"],
                "gamma": data["gamma"],
                "n_load_cases": data["n_load_cases"],
                "n_sequence": data["n_sequence"],
            },
            rationale=data["rationale"],
            caveats=data.get("caveats", ""),
            references=data.get("references", []),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse LLM recommendation: %s", e)
        return None
```

#### b) Integrate into `streamlit_app.py` `_ai_task_panel()`

Add a "Get Recommendations" section:
1. Text input: "Describe your material and simulation goal"
2. Button: "Recommend Parameters"
3. Shows recommended parameters in a card layout
4. "Apply These Parameters" button that fills the training form

### Acceptance Criteria
- Input "6061-T6 aluminum sheet, 2mm thick, stamping simulation" → recommended E ≈ 69GPa, sy ≈ 276MPa, material_type = hill or barlat
- Input "mild steel Q235, isotropic" → material_type = j2, sy ≈ 235MPa
- Rationale is in Chinese, explains why these values were chosen
- "Apply" button correctly fills the training form
- LLM not available → warning message

---

## Task 5.3: Batch Report Summary with LLM

### Context
Batch simulations produce 5-20 individual reports. The engineer wants a single-page summary. LLM is perfect for this.

### File to modify
`D:\githubproject\pyLabFEA\material_ai_workbench\batch_simulation.py`

### Changes

In `run_batch_plan()`, after the `batch_report.md` is generated, add a final optional step:
```python
def summarize_batch_with_llm(batch_dir: Path) -> str | None:
    """Generate an LLM executive summary of a batch simulation."""
    from material_ai_workbench.llm_adapter import _chat_completion, _llm_available

    if not _llm_available():
        return None

    # Collect key results from all samples
    summary_csv = batch_dir / "batch_summary.csv"
    if not summary_csv.exists():
        return None

    import csv
    rows = []
    with open(summary_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    # Build a condensed summary
    lines = ["Sample, Yield Strength (MPa), Max Mises (MPa), Status"]
    for r in rows:
        lines.append(f"{r.get('sample_id','?')}, {r.get('yield_strength','?')}, "
                     f"{r.get('latest_odb_max_mises','?')}, {r.get('status','?')}")

    data_text = "\n".join(lines[:30])  # Cap for token limit

    prompt = (
        "以下是批量材料参数扫描结果。用2-3段中文总结：\n"
        "(1) 屈服强度与最大Mises应力的关系是否合理\n"
        "(2) 是否有异常样本\n"
        "(3) 建议的下一步参数范围\n\n" + data_text
    )

    return _chat_completion(
        "你是一位仿真验证工程师。请简洁总结批量仿真结果。",
        prompt,
    )
```

In `streamlit_app.py` `_batch_panel()`, add LLM summary section to the batch detail view.

### Acceptance Criteria
- Run a 5-sample batch → "Summarize with AI" button visible
- Click → 2-3 paragraph Chinese summary appears
- Summary correctly identifies trends (e.g., "yield strength increases → max Mises increases")
- Summary flags anomalous samples if any exist

---

## Dependencies

```
5.1 (report interpretation) ── refactors llm_adapter.py, implement first
5.2 (param recommendation) ── depends on 5.1's _chat_completion refactor
5.3 (batch summary) ── depends on 5.1's _chat_completion refactor
```

Recommended order: Refactor `_chat_completion()` → 5.1 → 5.2 and 5.3 in parallel.
