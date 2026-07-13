# Workspace Example

Runtime data should live outside source code. A production checkout should create a local workspace like:

```text
workspace/material_ai_workbench/
  runs/
  batches/
  cases/
  datasets/
  surrogates/
  imports/
  logs/
  reports/
```

Only small, curated demo data should be copied into the public repository. Real Abaqus `.odb`, `.cae`, logs, model weights, customer files, and private reports should stay in the local workspace or be distributed as explicit release assets.
