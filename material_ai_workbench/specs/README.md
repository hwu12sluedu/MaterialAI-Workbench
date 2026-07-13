# MaterialAI Workbench — Implementation Specs

Master task index. Each file is self-contained and can be fed directly to an AI coding agent.

## File Index

| File | Phase | Content | Est. Effort |
|------|-------|---------|-------------|
| [BUGFIX_AND_UI_POLISH.md](BUGFIX_AND_UI_POLISH.md) | **HOTFIX** | Fix 28 bugs + 22 UI issues found in audit (execute FIRST) | 2-3 days |
| [PHASE_0_ENGINEERING_BASICS.md](PHASE_0_ENGINEERING_BASICS.md) | 0 — Engineering Basics | Git init, dependency files, config.py, tests, docs | 2-3 days |
| [PHASE_1_QUALITY_HARDENING.md](PHASE_1_QUALITY_HARDENING.md) | 1 — Quality Hardening | K-fold CV, logging, data validation, stderr capture, retry logic | 3-5 days |
| [PHASE_2_MATERIAL_MODELS.md](PHASE_2_MATERIAL_MODELS.md) | 2 — Material Models | Barlat Yld2000-2D, experimental curve plasticity, hyperelastic entry | 5-7 days |
| [PHASE_3_ABAQUS_INTEGRATION.md](PHASE_3_ABAQUS_INTEGRATION.md) | 3 — Abaqus Integration | Job queue, async ODB extraction, similar case search | 4-6 days |
| [PHASE_4_SURROGATE_UPGRADE.md](PHASE_4_SURROGATE_UPGRADE.md) | 4 — Surrogate Upgrade | Uncertainty quantification, multi-fidelity, time-series surrogate | 5-8 days |
| [PHASE_5_LLM_INTEGRATION.md](PHASE_5_LLM_INTEGRATION.md) | 5 — LLM Integration | Report interpretation, parameter recommendation, batch summary | 3-5 days |
| [PHASE_6_PACKAGING.md](PHASE_6_PACKAGING.md) | 6 — Packaging & DevOps | pyproject.toml, Docker, CI/CD, UI polish | 2-4 days |

## Execution Order

```
BUGFIX ──> Phase 0 ──> Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 4 ──> Phase 5 ──> Phase 6
                     (1.2)       (2.2 needs 1.3)  (3.2 needs 3.1)  (4.3 needs 3.2)
```
Note: BUGFIX Task B1 (eliminate hardcoded paths) is the same work as Phase 0 Task 0.3.
Execute them together.

Tasks within a phase can be parallelized unless noted in the file's dependency section.

## How to Use

Feed a single spec file to an AI coding agent with a prompt like:

```
Read D:\githubproject\pyLabFEA\material_ai_workbench\specs\PHASE_0_ENGINEERING_BASICS.md
and implement every task in order. Run the acceptance criteria to verify each task
before moving to the next one.
```

Each spec file contains:
- Exact file paths to create or modify
- Code snippets with the expected implementation
- Verifiable acceptance criteria for each task
- Dependency ordering within the phase

## Session Context

These specs were generated from a full project audit on 2026-07-03 covering:
- 88 `.py` source files (21 core modules)
- 941 total project files
- 7-stage closed-loop pipeline (all stages operational)
- 11-tab Streamlit UI
- Metal plasticity (J2/Hill) + Composite micro-to-macro workflows
