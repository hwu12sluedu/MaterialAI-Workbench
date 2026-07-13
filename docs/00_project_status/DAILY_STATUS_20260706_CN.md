# 2026-07-06 项目状态与今日 5 个任务

## 当前真实状态

MaterialAI Workbench 现在已经不是单纯 pyLabFEA 学习 demo，而是一个围绕“材料本构训练 + Abaqus 验证 + 案例库 + 代理模型 + 自然语言任务”的本地工程工具雏形。

已经具备：

- J2 / Hill / Barlat 金属塑性材料训练与 Abaqus UMAT 参数导出。
- Neo-Hookean / Mooney-Rivlin 超弹性材料曲线和 Abaqus material card 导出。
- Streamlit App 原型，包含 AI 任务、材料训练、数据导入、案例库、Abaqus MCP、批量仿真、代理模型、模型管理等页面。
- 复合材料微观 RVE、三相 phase map、6 个 PBC 均匀化载荷工况 INP、3D 带孔板 Abaqus 建模脚本和数据集行生成。
- 案例库、ODB/CSV 后处理、代理模型训练和闭环报告的最小产品链路。

仍未完成：

- 默认路径下还没有强制跑完 6 个 Abaqus PBC 均匀化工况；当前产品 smoke 默认只生成 PBC 作业文件。
- 自然语言任务已经能生成结构化计划，但只有部分任务类型具备一键执行。
- 真实 Abaqus 大批量求解、云图导出、复杂案例复用和模型管理还需要继续产品化。

## 今天定的 5 个任务

1. 审查仓库真实状态，确认 specs、README、代码和测试是否一致。
2. 修复发布前测试/CI 健康问题，避免慢测试拖垮 GitHub 反馈。
3. 补强自然语言和 LLM 配置，把任务 JSON 升级为可读执行计划。
4. 补强复合材料轻量闭环，让无 Abaqus 环境也能跑出可发布 smoke 案例。
5. 更新文档和状态记录，形成今天可追溯交付。

## 今天已完成

- 修复 `material_ai_workbench/streamlit_app.py` 中导致 App 无法启动的中文弯引号语法错误。
- 新增 `tests/test_streamlit_app_compile.py`，防止 Streamlit 入口再次出现语法级断裂。
- 将官方 pyLabFEA 重训练测试 `tests/test_ml.py` 标记为 `slow`，CI 默认执行 `-m "not slow"` 快速测试集。
- 在 `pyproject.toml` 中登记 pytest slow 标记，并在 CI 中切换到快速测试。
- 新增 `task_schema.build_executable_plan()`，把自然语言/LLM JSON 变成包含步骤、动作、是否需要 Abaqus 的执行计划。
- Streamlit `AI 任务` 页面新增执行计划表，规则解析和 LLM 解析都能显示。
- 新增 `run_product_closed_loop.py` 和命令入口 `materialai-product-closed-loop`。
- 修复复合材料 RVE 体积分数校准算法，改为基于体素中心距离选择最接近目标 Vf 的半径，避免离散跳变导致 Vf 严重偏离。
- 新增复合材料回归测试，覆盖 `Vf=0.55, 9 fibers, 12x12 voxels` 这类之前失败的组合。
- 更新 `material_ai_workbench/README_CN.md`，加入产品级 smoke 命令和功能说明。

## 今日验证结果

快速测试集：

```powershell
conda run -n pylabfea python -m pytest tests material_ai_workbench/tests -q -m "not slow" --disable-warnings
```

结果：

```text
79 passed, 5 skipped, 5 deselected, 1 warning
```

LLM/自然语言计划专项测试：

```powershell
conda run -n pylabfea python -m pytest tests/test_task_schema_plan.py tests/test_llm_adapter.py tests/test_llm_config_wizard.py -q --disable-warnings
```

结果：

```text
8 passed
```

复合材料闭环专项测试：

```powershell
conda run -n pylabfea python -m pytest tests/test_composite_workflow.py tests/test_product_closed_loop.py -q --disable-warnings
```

结果：

```text
3 passed
```

产品 smoke 命令：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_product_closed_loop --name product_smoke_20260706 --vf 0.55 --micro-fiber-count 9 --micro-nx 3 --micro-ny 12 --micro-nz 12
```

结果：

```text
Actual Vf: 0.5416666666666666
Vf within +/-3%: True
PBC job files: 6
Abaqus plate solve: generated
```

最新产品 smoke 目录：

```text
material_ai_workbench/composite_runs/20260706_003657_product_smoke_20260706
```

## 下一步建议

1. 把 Streamlit App 启动起来做浏览器截图检查，确认 AI 任务计划表和产品 smoke 说明在 UI 中可见。
2. 给 `materialai-product-closed-loop` 增加可选的案例入库和代理模型训练步骤，形成真正的“RVE -> 板孔 -> 数据资产 -> 代理模型”无 Abaqus 演示闭环。
3. 在 Abaqus 已打开且 MCP 正常时，跑一次 `--run-abaqus --submit-job` 的小规模真实求解，更新产品报告中的 `abaqus_plate_solve` 为真实完成状态。
4. 清理或归档仓库内生成数据，制定 GitHub 发布前保留/忽略规则，避免把大量 run 输出提交到仓库。
5. 继续完善中文教学文档，但放在产品功能稳定后统一整理，避免文档追着代码反复改。
