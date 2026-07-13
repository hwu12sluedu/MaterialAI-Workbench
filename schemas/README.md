# Task Schema Directory

This directory is reserved for production JSON Schemas that will define auditable tasks before any AI-generated plan can execute.

Planned schemas:

- `material_training.schema.json`
- `abaqus_job.schema.json`
- `odb_postprocess.schema.json`
- `batch_simulation.schema.json`
- `case_query.schema.json`
- `report_generation.schema.json`

Rule: natural-language or LLM output must be converted into one of these schemas, validated, displayed to the user, and confirmed before execution.
