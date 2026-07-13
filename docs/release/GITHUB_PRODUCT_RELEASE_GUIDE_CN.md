# GitHub 发布指南：MaterialAI Workbench

## 1. 发布前定位

仓库发布名称建议：

```text
MaterialAI Workbench
```

一句话说明：

```text
基于 pyLabFEA、Abaqus 与机器学习的本地 CAE+AI 工作台，支持材料本构学习、复合材料微观 RVE、Abaqus 带孔板验证、案例管理、ODB/CSV 特征提取和代理模型训练。
```

## 2. 发布前必须通过的检查

在 `D:\githubproject\pyLabFEA` 下运行：

```powershell
conda run -n pylabfea python -m py_compile material_ai_workbench/composite_workflow.py material_ai_workbench/run_composite_workflow.py material_ai_workbench/streamlit_app.py
conda run -n pylabfea python -m material_ai_workbench.run_composite_workflow --name release_smoke_composite --micro-nx 4 --micro-ny 10 --micro-nz 10
conda run -n pylabfea python -m material_ai_workbench.run_composite_batch create --name release_sweep --sample-count 3 --micro-nx 2 --micro-ny 8 --micro-nz 8
conda run -n pylabfea python -m pytest tests/test_composite_workflow.py -q
conda run -n pylabfea python -m pytest tests/test_composite_dataset.py -q
conda run -n pylabfea python -m pytest tests -q
```

启动 App：

```powershell
conda run -n pylabfea streamlit run material_ai_workbench/streamlit_app.py --server.port 8501
```

浏览器打开：

```text
http://localhost:8501/
```

进入 `复合材料RVE` 页面，生成一个案例，确认能看到：

- 三相微观 RVE 预览图。
- 3D 带孔板预览图。
- `phase_map.csv`。
- `micro_rve_voxel.inp`。
- `pylabfea_material_summary.json`。
- `build_plate_with_hole.py`。
- `composite_plate_report.md`。

## 3. 仓库必须保留的内容

必须进入 Git：

- `src/pylabfea/`
- `material_ai_workbench/`
- `tests/`
- `docs/`
- `configs/`
- `schemas/`
- `examples/`
- `README.md`
- `pyproject.toml`
- `environment.yml`
- `LICENSE`

不进入 Git：

- `material_ai_workbench/runs/`
- `material_ai_workbench/batches/`
- `material_ai_workbench/cases/`
- `material_ai_workbench/datasets/`
- `material_ai_workbench/surrogates/`
- `material_ai_workbench/composite_runs/`
- `material_ai_workbench/composite_batches/`
- `material_ai_workbench/composite_surrogates/`
- `.odb`、`.cae`、`.lck`、`.sta`、`.msg` 等大型 Abaqus 运行文件。

## 4. 推荐 GitHub README 结构

1. 项目一句话。
2. 为什么做这个项目。
3. 当前功能截图或流程图。
4. 快速开始。
5. 复合材料 RVE 示例。
6. Abaqus 连接方式。
7. 机器学习数据闭环。
8. 文档入口。
9. 路线图。
10. License 和上游 pyLabFEA 致谢。

## 5. Git 提交建议

首次公开发布建议拆成 4 个提交：

```text
1. Add MaterialAI Workbench product layer
2. Add composite RVE to Abaqus plate-hole workflow
3. Add Streamlit composite workflow UI and tests
4. Add Chinese product docs and GitHub release guide
```

## 6. 简历表达建议

项目名称：

```text
MaterialAI Workbench：面向材料本构与复合材料多尺度仿真的 CAE+AI 工作台
```

简历要点：

- 基于 pyLabFEA 与 Abaqus 构建本地材料 AI 工作台，实现材料模型训练、复合材料微观 RVE、宏观带孔板验证和机器学习数据集导出。
- 设计 Fiber/Interface/Matrix 三相体素 RVE 生成流程，输出 Abaqus `.inp`、phase map 和 pyLabFEA 材料摘要，为 3D CNN/多模态代理模型提供结构化输入。
- 构建 Abaqus 仿真案例库与 ODB/CSV 特征提取流程，将日常有限元仿真沉淀为可训练样本，用于代理模型、迁移学习和自然语言仿真客户端。
- 开发 Streamlit 可视化原型和命令行工具，支持复合材料参数化建模、报告生成、数据追踪和后续桌面客户端封装。
