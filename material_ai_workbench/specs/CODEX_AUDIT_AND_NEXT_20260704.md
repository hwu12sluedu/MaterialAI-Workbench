# Codex Audit and Next Production Tasks - 2026-07-04

## Product North Star

MaterialAI Workbench should become a local AI + Abaqus engineering workbench, not only a Streamlit demo. The product loop is:

1. Collect material curves, INP files, ODB/CSV results, reports, and daily simulation cases.
2. Build trustworthy case-library metadata: geometry, material model, mesh, load, solver status, post-processing features, and lessons learned.
3. Train material constitutive models and surrogate models with leakage checks and validation.
4. Generate Abaqus jobs from structured parameters or natural language, then run and post-process them through Abaqus/MCP.
5. Feed verified Abaqus results back into the case library so the product improves with daily use.

## Audit Findings

- DeepSeek's direction is useful: the app now has a broader UI, LLM configuration scaffolding, job queue pieces, case-library export, composite workflow, and RF/MLP/GBR surrogate hooks.
- The remaining weakness is still product closure: several features had UI or schema surfaces before the data path was fully trustworthy.
- The most important issue found in this pass was data integrity. RVE fiber volume fraction and case-library structured fields must be numerically correct, because these fields become machine-learning training features.
- LLM API integration should not be treated as done until natural language can produce a validated simulation plan, optionally run it, and write the result back to the case library.
- Abaqus integration should be judged by generated INP/job execution/ODB or CSV extraction evidence, not by a button or config panel alone.

## Fixes Completed By Codex In This Pass

- Calibrated composite RVE generation so voxel-level actual fiber volume fraction follows the requested target.
- Propagated case-library structured fields into saved cases and ML dataset exports:
  - material type
  - case type
  - geometry
  - loading
  - mesh statistics
  - Abaqus result fields
  - ODB/log summary features
- Prevented obvious surrogate feature leakage by treating Abaqus result aliases as target/result fields rather than normal input features.
- Added CV R2 metrics for surrogate training, plus tested RF/MLP/GBR comparison on the same dataset.
- Fixed the Streamlit time-series surrogate default path for `frame_series_index.csv`.
- Confirmed no real API key was found in tracked project files; the only `sk-` match was the word `disk-backed`.
- Verified:
  - targeted tests: `12 passed`
  - full local test suite: `79 passed, 5 skipped, 1 warning`
  - Streamlit health check: `http://localhost:8501/` returned HTTP 200

## Next 10 Production Tasks

1. **Real Abaqus MCP Closed Loop**
   - Goal: generate one plate-with-hole INP, submit it through the current Abaqus/MCP bridge, read ODB or CSV, and save evidence to the case library.
   - Acceptance: one command/button produces a run folder containing INP, status JSON, extracted result CSV/JSON, thumbnail/report, and case-library entry.

2. **Natural Language Simulation Planner**
   - Goal: turn Chinese engineering intent into a validated structured simulation plan.
   - Acceptance: LLM output must pass a schema validator and support dry-run before execution. No direct free-form code execution.

3. **LLM Provider Configuration Wizard**
   - Goal: make DeepSeek/OpenAI/compatible APIs configurable without hardcoding secrets.
   - Acceptance: `.env` persistence, connection test, selected model display, and clear failure messages.

4. **Microscale Composite RVE Modeling**
   - Goal: keep the composite module focused on actual microscale geometry generation, not only equivalent-property placeholders.
   - Acceptance: RVE phase map, fiber/matrix/interphase metrics, PBC job deck, and 3D visualization are generated and recorded.

5. **Microstructure-To-Abaqus Mapping**
   - Goal: map microstructure-derived descriptors and material parameters into the 3D plate-with-hole verification model.
   - Acceptance: dataset row links the RVE manifest, Abaqus verification run, and extracted target metrics.

6. **Daily Case Library Ingestion**
   - Goal: import user-provided INP/ODB/CSV/report folders with duplicate detection and metadata extraction.
   - Acceptance: batch import wizard, tags/status/material filters, similar-case retrieval, and selected-case dataset export.

7. **Dataset Governance**
   - Goal: make ML datasets reproducible and safe from leakage.
   - Acceptance: train/validation split manifest, feature/target classification, skipped-row reasons, lineage to source case IDs.

8. **Surrogate Model Bench**
   - Goal: compare RF/GBR/MLP and later neural operators/time-series models for Abaqus result prediction.
   - Acceptance: metrics table, prediction plot, feature importance where available, uncertainty, and recommended next Abaqus samples.

9. **Engineering Report Generator**
   - Goal: produce a Chinese engineering report from each closed loop.
   - Acceptance: includes model assumptions, material data, Abaqus job status, result figures/CSV, warnings, and next validation actions.

10. **Release Hardening**
    - Goal: make the repository publishable on GitHub.
    - Acceptance: clean package layout, no temp files or secrets, small sample dataset, CI, quickstart, architecture docs, and Chinese learning guide.

## Immediate Priority

The next coding milestone should be Task 1 + Task 2 together: natural language should first create a safe simulation plan, then the same plan should run through the Abaqus/MCP closed loop and return a case-library entry. That is the first feature that will feel like the final product rather than a collection of tools.
