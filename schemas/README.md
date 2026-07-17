# Schema Directory

Machine-readable contracts shared by the product, documentation and the future black-box QA repository.

Current schemas:

- `diagnostics.schema.json`: Abaqus batch/MCP diagnostic report.
- `acceptance_manifest.schema.json`: resumable 3D plate-hole acceptance state and evidence.
- `case_package.schema.json`: versioned Abaqus case metadata, provenance and ML quality gates.

Planned schemas:

- `material_training.schema.json`
- `abaqus_job.schema.json`
- `odb_postprocess.schema.json`
- `batch_simulation.schema.json`
- `case_query.schema.json`
- `report_generation.schema.json`

Rule: natural-language or LLM output must be converted into one of these schemas, validated, displayed to the user, and confirmed before execution.
