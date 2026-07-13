# Changelog

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
