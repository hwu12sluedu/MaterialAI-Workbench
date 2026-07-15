# MaterialAI Workbench API 使用说明

本文件按业务流程组织 API，而不是按文件名罗列。

## 1. 材料训练

入口：

- CLI：`material_ai_workbench.run_workbench`
- Python：`material_ai_workbench.pipeline`

命令：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name api_j2 --with-curves
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material hill --name api_hill --sy 50 --C 2 --gamma 1 --with-curves
```

主要输出：

```text
runs/<run_name>/summary.json
runs/<run_name>/reports/material_model_report.md
runs/<run_name>/figures/yield_locus.png
runs/<run_name>/figures/stress_strain_curves.png
runs/<run_name>/models/abq_<name>-svm.csv
runs/<run_name>/models/abq_<name>-svm_meta.json
```

生产化要求：

- 任何训练都必须输出机器可读 `summary.json`。
- 任何训练都必须输出人可读报告。
- Abaqus 可用模型文件必须带 meta JSON。

## 2. 自然语言任务解析

入口：

- `material_ai_workbench.nl_tasks`
- `material_ai_workbench.llm_adapter`

当前模式：

1. 规则解析器默认可用，不需要 API Key。
2. LLM API 是可选增强，只输出任务 JSON。
3. 用户确认前不能执行 Abaqus 或覆盖文件。

环境变量：

```text
MATERIALAI_LLM_BASE_URL
MATERIALAI_LLM_MODEL
MATERIALAI_LLM_API_KEY
```

后续要升级为 JSON Schema 强校验。

## 3. Abaqus UMAT 验证

入口：

- `material_ai_workbench.abaqus_bridge`

准备目录：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<run_name>
```

运行 Abaqus：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<run_name> --max-load-cases 1 --run
```

输出：

```text
abaqus_verification/bridge_summary.json
abaqus_verification/abaqus_verification_report.md
abaqus_verification/results/*.csv
abaqus_verification/results/*.png
```

注意：

- Abaqus ODB 读取必须走 SMAPython 或 Abaqus MCP。
- 普通 Python 不能导入 `odbAccess`。

## 4. Abaqus MCP 实时交互

入口：

- `material_ai_workbench.abaqus_mcp_client`

使用前：

```text
Abaqus/CAE -> Plug-ins -> Abaqus MCP -> Start Socket Bridge
```

默认：

```text
127.0.0.1:48152
```

已支持：

- 连接检查。
- 读取模型、Job、工作目录。
- 设置工作目录。
- 监控 `.sta/.msg`。
- 用户确认后提交已有 Job。
- 读取 ODB 元数据。
- 提取 ODB 场变量统计。
- 抓取 viewport。
- 生成 MCP 会话快照。

## 5. 案例库

入口：

- `material_ai_workbench.case_library`

输入：

- Abaqus 工程文件夹。
- 单个 `.inp` 文件。

输出：

```text
cases/<case_id>/case_summary.json
cases/<case_id>/case_report.md
```

提取能力：

- INP 材料、step、单元类型、载荷、边界、输出请求。
- CSV/日志中的 Mises、PEEQ、U、RF、warning、error。
- ODB 后处理记录。
- 图片、报告、脚本索引。

## 6. ODB 后处理

入口：

- `material_ai_workbench.odb_postprocess`
- `material_ai_workbench.abaqus_batch_client`

输出：

```text
odb_field_summary.json
odb_field_summary.csv
odb_field_report.md
odb_frame_series.json
odb_frame_series.csv
odb_frame_series_report.md
```

后续生产要求：

- 所有后处理配置必须可保存。
- 所有结果必须能回写案例库。
- 每次提取都要记录 ODB 路径、字段、step、frame、region。

## 7. 数据集导出

入口：

- `material_ai_workbench.dataset_export`

输出：

```text
datasets/<dataset_name>/case_dataset.csv
datasets/<dataset_name>/frame_series_index.csv
datasets/<dataset_name>/dataset_manifest.json
datasets/<dataset_name>/dataset_report.md
```

原则：

- `case_dataset.csv` 用于表格代理模型。
- `frame_series_index.csv` 用于时间序列模型。
- manifest 必须记录数据来源，保证可追溯。

## 8. 代理模型

入口：

- `material_ai_workbench.surrogate_model`

当前支持：

- RandomForest。
- MLP。
- 预测图。
- 指标 JSON。
- 报告 Markdown。
- 模型 `.pkl`。

输出：

```text
surrogates/<run_name>/features.csv
surrogates/<run_name>/targets.csv
surrogates/<run_name>/predictions.csv
surrogates/<run_name>/surrogate_metrics.json
surrogates/<run_name>/prediction_vs_truth.png
surrogates/<run_name>/surrogate_report.md
```

工程解释：

- RandomForest 是稳健 baseline。
- MLP 是神经网络路线的最小起点。
- 样本量少时必须在报告中说明“只验证流程，不代表预测精度”。

## 9. 闭环报告

入口：

- `material_ai_workbench.closed_loop_report`

命令：

```powershell
conda run -n pylabfea python -m material_ai_workbench.closed_loop_report
```

输出：

```text
closed_loop_reports/<time>/closed_loop_manifest.json
closed_loop_reports/<time>/closed_loop_validation_report.md
```

用途：

- 给自己复盘。
- 给 GitHub 展示。
- 给简历/面试提供证据。
- 给后续模型迭代提供验收基线。

## 10. Abaqus 环境诊断

入口：

- Python：`material_ai_workbench.abaqus_diagnostics`
- CLI：`materialai-diagnostics`

```python
from material_ai_workbench.abaqus_diagnostics import (
    AbaqusDiagnosticConfig,
    run_abaqus_diagnostics,
)

report = run_abaqus_diagnostics(
    AbaqusDiagnosticConfig(probe_commands=True)
)
print(report.overall_status, report.batch_ready, report.mcp_ready)
```

输出遵循 `schemas/diagnostics.schema.json`。`batch_ready` 与 `mcp_ready` 独立判断，MCP 未连接不应阻止可用的 Abaqus 批处理流程。

## 11. 三维带孔板验收

入口：

- Python：`material_ai_workbench.plate_hole_acceptance`
- CLI：`materialai-plate-hole`

```python
from material_ai_workbench.plate_hole_acceptance import (
    PlateHoleAcceptanceConfig,
    run_plate_hole_acceptance,
)

prepared = run_plate_hole_acceptance(
    PlateHoleAcceptanceConfig(name="review_case"),
    execute=False,
)

solved = run_plate_hole_acceptance(
    PlateHoleAcceptanceConfig(
        name="verified_case",
        submit_job=True,
        archive_case=True,
    ),
    execute=True,
)
```

恢复已有运行：

```python
from material_ai_workbench.plate_hole_acceptance import resume_plate_hole_acceptance

result = resume_plate_hole_acceptance(
    "<acceptance_run_dir>",
    execute=True,
    submit_job=True,
)
```

状态和证据遵循 `schemas/acceptance_manifest.schema.json`。只有真实 ODB 和求解证据存在时，`solve` 阶段才会通过。
