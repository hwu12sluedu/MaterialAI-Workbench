# Contributing

Contributions should keep engineering claims traceable and distinguish generated assets from solved Abaqus evidence.

## Local checks

```powershell
conda env create -f environment.yml
conda activate pylabfea
python -m pip install -e ".[app,dev]"
python -m pytest tests material_ai_workbench/tests -q -m "not slow"
python -m build
```

Add focused tests for behavior changes. Do not commit `.env`, API keys, ODB/CAE files, model weights, local workspaces or executed notebooks. Keep Abaqus execution behind an explicit user action.

Please open an issue before broad architecture changes. The bundled pyLabFEA source remains attributable to its upstream authors and GPL obligations apply to derivative work.
