# Changelog

## Unreleased

### Added

- Read-only Abaqus environment diagnostics with separate batch-runtime and MCP readiness evidence.
- Resumable 3D plate-with-hole acceptance workflow covering CAE/INP generation, real Job submission, ODB feature extraction, engineering sanity checks and case-library indexing.
- Desktop pages for system diagnostics and the plate-with-hole acceptance workflow.
- Machine-readable diagnostic and acceptance-manifest schemas plus a black-box functional test handoff.

### Fixed

- Align direct MCP client defaults with the documented `MATERIALAI_ABAQUS_MCP_*` environment variables.
- Store MCP session snapshots in the writable user workspace instead of the installed package directory.
- Treat the local SMAPython `_ctypes` error during `odb.close()` as a recorded close warning after successful extraction.
- Keep diagnostic CLI JSON safe when `conda run` relays output through a Windows GBK parent console.
- Reject stale or failed PyInstaller output, prefer the selected Python runtime DLLs, bound frozen-app smoke time and delete failed portable archives.

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
