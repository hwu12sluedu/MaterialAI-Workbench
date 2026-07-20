# Changelog

## Unreleased

### Added

- Governed ingestion for the public 62-sample CFRP experimental benchmark, including explicit source-license acceptance, official metadata checks, SHA-256 verification and immutable workspace storage.
- Stable normalized columns, target-specific missing-value handling, duplicate reporting and leave-one-material-type-out split manifests.
- `materialai-cfrp-data` CLI plus Chinese data-governance tutorial, data card and API documentation.
- Leakage-resistant CFRP Mean/Ridge/Random Forest/SVR baselines with fixed material-type folds, nested group-residual intervals, OOF evidence tables, model cards and a Chinese report.
- `materialai-cfrp-baseline` CLI and a documented `baseline_completed` benchmark status that does not overstate paper reproduction.
- Validation-protocol audit comparing material-group holdout and row LOOCV on raw and exactly deduplicated CFRP views, with per-sample duplicate-leakage evidence.
- `materialai-cfrp-validation-audit` CLI, protocol-sensitivity figures, Chinese report and learning/API documentation.

### Changed

- Composite benchmark provenance now records the dataset DOI, version, license, expected filename and source hash without claiming that Workbench models have already reproduced the paper metrics.

## 0.4.0-alpha.1 - 2026-07-17

### Added

- Versioned `case_package.json` v2 with bounded file fingerprints, provenance, units, solver evidence and machine-readable quality gates.
- Explainable similar-case retrieval across material, geometry, loading, mesh, units, results and text evidence.
- Local case grounding for OpenAI-compatible planners; unknown case IDs, local paths and automatic Abaqus submission are rejected.
- Read-only case reuse workspaces containing copied editable inputs, parameter-difference reviews and non-submitted execution manifests.
- Resumable 3D plate-hole batch plans over hole radius, yield strength and displacement, with governed dataset export and RF/MLP/GBR comparison.
- `materialai-case` and `materialai-plate-hole-batch` command-line tools plus dedicated desktop pages.

### Changed

- Training dataset export can include only cases that pass solver, unit, material, mesh and numeric-target quality gates.
- Surrogate training filters explicit quality failures, rejects mixed unit systems and excludes governance metadata from model features.
- Plate-hole acceptance archives canonical geometry/loading/material parameters and the explicit `mm-N-s-MPa` unit system.

### Fixed

- Abaqus convergence text such as `residual error estimate` is no longer treated as a fatal solver error.
- LLM task types outside material training no longer need to rely on ungrounded historical-case assumptions.

### Release boundaries

- This is an alpha release. Case-based planning copies inputs and writes a review plan; it does not automatically edit arbitrary INP geometry.
- Batch samples are training truth only after real Abaqus completion, ODB extraction, case archival and quality-gate approval.
- Neural-network surrogate metrics require adequate samples and independent Abaqus validation before engineering use.

## 0.3.0 - 2026-07-15

### Added

- Read-only Abaqus environment diagnostics with separate batch-runtime and MCP readiness evidence.
- Resumable 3D plate-with-hole acceptance workflow covering CAE/INP generation, real Job submission, ODB feature extraction, engineering sanity checks and case-library indexing.
- Desktop pages for system diagnostics and the plate-with-hole acceptance workflow.
- Machine-readable diagnostic and acceptance-manifest schemas plus a black-box functional test handoff.
- Independent release verification through the public `MaterialAI-Workbench-QA` repository.

### Fixed

- Align direct MCP client defaults with the documented `MATERIALAI_ABAQUS_MCP_*` environment variables.
- Store MCP session snapshots in the writable user workspace instead of the installed package directory.
- Treat the local SMAPython `_ctypes` error during `odb.close()` as a recorded close warning after successful extraction.
- Keep diagnostic CLI JSON safe when `conda run` relays output through a Windows GBK parent console.
- Reject stale or failed PyInstaller output, prefer the selected Python runtime DLLs, bound frozen-app smoke time and delete failed portable archives.
- Remove upstream PyArrow and scikit-learn test fixtures before creating the public Windows ZIP.

## 0.2.0 - 2026-07-14

Windows desktop release and public-repository cleanup.

### Added

- Native Windows launcher backed by pywebview and a private Streamlit process.
- Automatic loopback-port selection, startup health check, single-instance guard and clean backend shutdown.
- Per-user workspace, configuration and rotating logs under `%LOCALAPPDATA%\MaterialAIWorkbench`.
- PyInstaller one-folder build, portable ZIP, SHA256 checksum and frozen-application smoke test.
- Windows client, troubleshooting, capability-boundary and source-build documentation.

### Changed

- Reworked the README around direct Windows download, engineering workflows and explicit limitations.
- Moved optional language-model configuration out of the primary workflow and renamed the UI entry to `仿真任务`.
- Removed internal agent task lists, dated audits, status reports, duplicate documentation and unused YAML configuration examples from the public package.
- GitHub Release automation now publishes Python distributions and the Windows x64 portable client together.

## 0.1.1 - 2026-07-13

Patch release for clean-install and CI compatibility.

### Fixed

- Fall back to bundled pyLabFEA `4.4.2` metadata when the standalone `pylabfea` distribution is not installed.
- Add a regression test for bundled-version metadata export.
- Scope CI to `main` and pull requests so release tags do not duplicate the full test matrix.
- Update official GitHub actions to their current Node 24-compatible major versions.

## 0.1.0 - 2026-07-13

First public engineering MVP.

### Added

- Streamlit workbench for material training, data import, case management, Abaqus MCP, batch jobs, surrogate models and result browsing.
- J2, Hill and Barlat ML yield-model experiments plus Neo-Hookean and Mooney-Rivlin material workflows.
- OpenAI-compatible natural-language planning with explicit review before execution.
- Abaqus job preparation, live MCP inspection, ODB/CSV extraction and case-library indexing.
- Random Forest, MLP, time-series and multi-fidelity surrogate-model baselines.
- Oriented Fiber/Interface/Matrix RVE generation, consistent phase maps, six homogenization load-case files and a 3D plate-with-hole validation workflow.
- Chinese product, source-learning and API documentation.

### Release boundaries

- Abaqus is optional and must be installed and licensed separately.
- The no-Abaqus closed loop generates auditable engineering assets; it does not claim solved Abaqus results.
- Current RVE load cases use a kinematic homogenization MVP. Strict periodic wrapping and full periodic boundary equations remain future validation work.
- Surrogate metrics from small demo datasets prove the pipeline only and are not industrial accuracy claims.
