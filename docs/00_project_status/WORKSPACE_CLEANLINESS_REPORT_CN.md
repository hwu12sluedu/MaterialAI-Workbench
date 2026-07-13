# 工作区整洁度报告

审查日期：2026-07-03  
审查目录：`D:\githubproject\pyLabFEA`

## 结论

当前项目已经跑通了“材料训练 -> Abaqus 验证 -> 案例归档 -> 数据集导出 -> 代理模型 -> 闭环报告”的最小闭环，但还不是可直接公开发布的仓库形态。主要问题不是功能缺失，而是源码、文档、运行产物、缓存、Sphinx 生成站点和大文件还混在同一层级。

发布前必须先完成目录边界重组，否则后续功能越多，越容易变成难以维护的堆叠式项目。

## 当前结构

| 区域 | 当前状态 | 判断 |
|---|---|---|
| `src/pylabfea` | 原始 pyLabFEA 核心源码，包含 FE、材料、数据、训练、GUI 模块 | 应作为上游学习与底层能力保留 |
| `notebooks` | 8 个教学 notebook，覆盖有限元、塑性、等效应力、ML flow rule、复合材料、均匀化 | 必须进入中文教学体系 |
| `examples` | 包含 UMAT、纹理、CPFEM、训练脚本 | 有价值，但需区分可发布 demo 和研究数据 |
| `material_ai_workbench` | 我们新增的材料 AI + Abaqus 工作台 | 当前原创产品主线 |
| `tests` | 已覆盖材料训练、MCP、Abaqus 桥接、案例库、ODB、数据集、代理模型、闭环报告 | 生产化基础已经具备 |
| `docs` | 同时存在 Sphinx HTML、中文 Markdown、新增文档 | 需要拆分源文档和生成站点 |
| `build`、`.pytest_cache`、`__pycache__`、`.ipynb_checkpoints` | 生成/缓存目录 | 发布前清理 |
| `material_ai_workbench/runs|batches|cases|datasets|surrogates` | 真实运行数据和 ODB 结果 | 不应直接进入 Git 主仓库 |

## 已完成里程碑

1. pyLabFEA 本地环境与基础测试通过。
2. J2 isotropic 与 Hill anisotropic 两类材料训练入口已接入。
3. SVC/SVM 屈服模型训练、屈服面图、应力应变曲线、UMAT CSV/JSON 导出已完成。
4. Streamlit App 已形成十个工作区：AI 任务、材料训练、数据导入、案例库、Abaqus MCP、Abaqus 验算、批量仿真、结果浏览、代理模型、模型管理。
5. Abaqus 单元级 UMAT 验算链路已跑通。
6. Abaqus MCP 实时连接页已接入，支持模型/Job/ODB/viewport 等基本交互。
7. 案例库 v0 已能索引 `.inp`、ODB、CSV、日志、图片和报告，并生成 `case_summary.json` 与 `case_report.md`。
8. ODB 后处理已支持最后一帧场变量统计、逐帧曲线、named set 局部曲线入口。
9. 批量仿真 v0 已跑通 5 个 J2 样本，并归档为训练数据集。
10. RandomForest 与 MLP 代理模型 baseline 已接入，能输出指标、预测图、模型和报告。
11. 闭环报告 v0 已完成 8/8 步验证。

## 主要问题

| 严重度 | 问题 | 影响 | 处理策略 |
|---|---|---|---|
| 高 | 当前目录不是 Git 工作树 | 无法可靠区分新增、修改、删除，也无法安全发布 | 发布前复制到干净仓库或恢复 `.git` |
| 高 | 运行产物与源码混放 | ODB、模型、日志、临时批量结果会污染代码包 | 建立 `workspace/` 数据根目录并默认忽略 |
| 高 | `docs` 同时保存源文档和 HTML 生成物 | 文档维护边界混乱 | `docs/` 只放源 Markdown，生成站点放 `site/` |
| 中 | `material_ai_workbench/streamlit_app.py` 单文件过大 | 后续客户端化会变难 | 拆出页面、服务层、视图模型 |
| 中 | LLM 接入仍是 OpenAI-compatible v0 | 多供应商、重试、成本、审计不足 | 建立 provider 层、schema 校验和调用日志 |
| 中 | 代理模型样本量极少 | 只能证明闭环，不代表预测精度 | 引入真实案例库和参数化批量数据 |
| 中 | 复合材料/RVE 还未产品化 | 与最终“复合材料多尺度建模”目标有差距 | 进入下一阶段任务池 |
| 低 | 控制台读取部分中文文档时显示乱码 | 影响命令行阅读体验 | 统一 UTF-8，文档生成时显式指定编码 |

## 发布前保留/迁移建议

保留进 Git：

- `src/pylabfea`
- `material_ai_workbench/*.py`
- `tests/*.py`
- `notebooks/*.ipynb`
- `examples/UMAT` 中的小型模板文件
- `docs/**/*.md`
- `tools/*.py`
- `pyproject.toml`、`environment.yml`、`README.md`、`LICENSE`

迁移或忽略：

- `material_ai_workbench/runs`
- `material_ai_workbench/batches`
- `material_ai_workbench/cases`
- `material_ai_workbench/datasets`
- `material_ai_workbench/surrogates`
- `material_ai_workbench/imports`
- `material_ai_workbench/logs`
- `material_ai_workbench/closed_loop_reports`
- `*.odb`、`*.cae`、`*.pkl`、`*.log`、`__pycache__`、`.pytest_cache`

## 已新增自动审计

运行：

```powershell
conda run -n pylabfea python tools/release_audit.py
```

输出：

```text
docs/00_project_status/WORKSPACE_AUDIT_AUTOGEN_CN.md
```

该脚本只生成报告，不删除任何文件。
