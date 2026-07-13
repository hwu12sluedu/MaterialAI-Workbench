# Codex Round 3 — 打穿核心闭环（10 个任务）

**原则：不再做功能碎片和 UI 补丁。咬住产品方向：材料本构训练 + 微观复合材料建模 + Abaqus 自动验证 + 仿真案例库 + ML 代理模型 + 自然语言仿真客户端。**

---

## 当前问题诊断

| 问题 | 严重度 | 证据 |
|------|--------|------|
| 复合材料仍在"只生成不求解" | **致命** | `manifest.json`: `run_pbc_homogenization=false`, `abaqus_status=generated` |
| RVE 体积分数不一致 | **高** | 目标 Vf=0.55，实际 preview_vf=0.4536，体素 Vf=0.3951 |
| LLM 只支持 3 类硬编码任务 | **高** | `llm_adapter.py:467` — 不是可执行计划系统 |
| experiment_validation.py 孤立重复 | **中** | 与 data_import.py 功能重叠，两条路径 |
| Plotly 未声明依赖 | **中** | `pyproject.toml` 缺少 plotly |
| XSRF 保护关闭 | **中** | `.streamlit/config.toml` 不可发布 |

**测试：78 passed, 5 skipped** — 代码没坏，但产品闭环没到位。

---

## TASK 1：复合材料真实 Abaqus 闭环

**目标：** RVE → PBC 求解 → 带孔板建模 → 提交 Job → ODB 后处理 → 结果写回 manifest。

**要改的文件：** `composite_workflow.py`, `run_composite_closed_loop.py`

**具体步骤：**
1. 在 `composite_workflow.py` 中，`run_composite_plate_workflow()` 已生成所有脚本。需要新增一个 `run_composite_full_closed_loop()` 函数，按顺序执行：
   - RVE 生成（已有）
   - 跑 6 个 PBC Job：`run_pbc_jobs.ps1` → Abaqus 求解 → `extract_rve_effective_stiffness.py` 提取真实刚度
   - 用 Abaqus 均匀化结果更新 ENGINEERING CONSTANTS
   - 跑 `run_abaqus_plate.ps1` → 带孔板 Abaqus 求解
   - 跑 `extract_plate_results.py` → 提取 max Mises / max U / RF1
   - 写回 manifest，所有字段非空
2. 更新 `run_composite_closed_loop.py` 调用这个新函数

**验收：** 最新 manifest 中 `run_pbc_homogenization=true`, `run_abaqus=true`, `plate_results` 包含 max_mises/max_displacement/sum_rf1，`effective_properties` 来自 Abaqus 而非 rule-of-mixtures。

---

## TASK 2：修正 RVE 体积分数一致性

**目标：** 体素纤维体积分数 `actual_vf` 与目标 `target_vf` 误差 < 3%。

**要改的文件：** `composite_workflow.py` — `generate_fiber_layout()`, `write_micro_rve_inp()`

**具体步骤：**
1. 当前 `generate_fiber_layout()` 用 fiber_count 和 cell_area 估算半径，但 fiber_count 是输入参数而非从 Vf 反算。
2. 改为：从 target Vf 反算需要的纤维数：`n_fibers = ceil(Vf * nx * ny / (pi * r^2))`，然后迭代调整半径直到 actual_vf 在 target ±3% 内。
3. `write_micro_rve_inp()` 和 `write_microstructure_preview()` 中写入 actual_vf 到 phase_map 和 report。
4. `write_dataset_row()` 新增 `actual_vf` 和 `target_vf` 两列。

**验收：** 配置 Vf=0.55 → 生成后 actual_vf 在 0.534-0.567 范围内。manifest 和 dataset_row 中 actual_vf 字段准确。

---

## TASK 3：严格 PBC 均匀化 + 对比报告

**目标：** 不只是生成脚本，真正跑 6 个载荷工况，输出完整刚度矩阵，生成与 rule-of-mixtures 的对比报告。

**要改的文件：** `composite_workflow.py`, 新增 `pbc_homogenization.py`

**具体步骤：**
1. 在 `run_composite_full_closed_loop()` 中（Task 1 的一部分）：
   - 遍历 6 个 PBC Job（EXX/EYY/EZZ/GXY/GXZ/GYZ）
   - 每个 Job 提交 Abaqus，等待完成，检查 .odb 存在
2. 跑 `extract_rve_effective_stiffness.py`，输出 `rve_effective_stiffness.csv` + `.json`
3. 新增 `pbc_homogenization.py` — 对比函数：
   - 读取 Abaqus 结果（E1_abaqus, E2_abaqus, G12_abaqus...）
   - 计算 rule-of-mixtures 值
   - 生成对比报告 Markdown（差值百分比表）
4. 写回 manifest: `pbc_homogenization` 字段包含 `status`, `stiffness`, `comparison`

**验收：** E1/E2/E3/G12/G13/G23/nu12/nu13/nu23 全部来自 Abaqus，对比报告显示 Abaqus vs ROM 差值 < 15%。

---

## TASK 4：自然语言仿真 → 可执行计划系统

**目标：** LLM 输出结构化任务计划，App 显示执行步骤，用户确认后执行。

**要改的文件：** `llm_adapter.py`, `nl_tasks.py`, `streamlit_app.py`

**具体步骤：**
1. 扩展 `nl_tasks.py` 的任务类型从 3 种到至少 8 种：
   - 材料训练（已有）
   - 材料训练 + Abaqus 验算（已有）
   - 复合材料 RVE + 板孔（已有）
   - **新增：** 批量参数扫描
   - **新增：** 案例库检索
   - **新增：** 代理模型训练
   - **新增：** ODB 数据提取
   - **新增：** 闭环报告生成
2. `llm_adapter.py` 的 prompt 更新为生成完整的执行计划 JSON（含步骤列表、每步参数、依赖关系）
3. `streamlit_app.py` AI 任务面板改为：
   - 用户输入自然语言
   - LLM 返回结构化执行计划（步骤 1→2→3...）
   - UI 显示计划卡片（每步有 checkbox）
   - 用户确认后按序执行，实时显示进度

**验收：** 输入 "做一个 Vf=0.6 的碳纤维复合材料带孔板仿真，跑 Abaqus，然后训练代理模型预测应力" → LLM 返回 4-5 步计划 → UI 显示 → 一键执行。

---

## TASK 5：接入 Abaqus MCP 实时工作流

**目标：** 通过 MCP 实时控制 Abaqus/CAE，支持设置工作目录、提交 Job、查询状态、读取 ODB、导出云图。

**要改的文件：** `abaqus_mcp_client.py`, `streamlit_app.py`

**具体步骤：**
1. 确认 Abaqus MCP 插件在 `Plug-ins > Abaqus MCP > Start Socket Bridge` 后正常工作
2. 完善 `abaqus_mcp_client.py` 中的 Job 提交逻辑：当前 `submit_job()` 提交后等待完成，改为异步提交 + 轮询 + 进度回调
3. 新增 `export_odb_csv()` 方法：从当前 ODB 导出指定 step/frame 的场变量为 CSV
4. 新增 `export_odb_report()` 方法：一键生成含云图 + 数据表的 Markdown 报告
5. Streamlit 面板：显示 Job 队列（提交中/运行中/已完成/失败），每个 Job 可查看日志、终止、重新提交

**验收：** 在运行中的 Abaqus/CAE 上通过 MCP 提交 Job，Streamlit 面板实时显示状态变化，Job 完成后可导出 ODB 数据。

---

## TASK 6：合并实验验证逻辑

**目标：** 删除或整合 `experiment_validation.py`，统一到 `data_import.py` 的闭环验证流程。

**要改的文件：** `data_import.py`, `streamlit_app.py`；删除 `experiment_validation.py`

**具体步骤：**
1. 将 `experiment_validation.py` 中的 `validate_experiment_against_ml()` 函数合并到 `data_import.py`
2. `data_import.py` 中 `imported_curve_to_config()` 后可直接调用验证，生成对比报告
3. Streamlit 只保留 `data_import.py` 的导入→训练→验证入口
4. 删除 `experiment_validation.py`，更新所有 import 引用

**验收：** 代码库中无 `experiment_validation` 引用。数据导入面板的"实验曲线闭环验证"按钮调用的是 `data_import.py` 中的统一函数。

---

## TASK 7：修复发布依赖和配置

**目标：** `pip install -e ".[app]"` 在全新环境中能直接启动 App。

**要改的文件：** `pyproject.toml`, `requirements.txt`, `.streamlit/config.toml`

**具体步骤：**
1. `pyproject.toml` 的 `[project.optional-dependencies]` 中 `app` 增加 `plotly>=6.0`
2. `requirements.txt` 同步更新
3. `.streamlit/config.toml` 删除 `enableXsrfProtection = false`，用 `[server]` 的正确配置替代：
   ```toml
   [server]
   maxUploadSize = 200
   maxMessageSize = 200
   [browser]
   gatherUsageStats = false
   ```
4. 验证：在新 conda 环境中执行 `pip install -e ".[app]" && streamlit run material_ai_workbench/streamlit_app.py` 成功启动

**验收：** 新环境一键安装启动，XSRF 保护开启，所有依赖声明完整。

---

## TASK 8：案例库升级为训练数据资产库

**目标：** 每个案例包含完整结构化元数据，可用于相似案例检索和训练集导出。

**要改的文件：** `case_library.py`, `dataset_export.py`

**具体步骤：**
1. `CaseSummary` 增加字段：`material_type`, `geometry`（L/W/T/HoleR）, `loading`（strain/stress）, `mesh_stats`（nodes/elements）, `abaqus_results`（max_mises/max_u/rf1）, `odb_features`（field stats）, `tags`, `source_files`, `status`（success/failed/partial）
2. `scan_case_folder()` 自动提取这些字段（从 INP 解析几何和载荷，从 CSV/ODB 解析结果）
3. `dataset_export.py` 增加特征列：geometry + loading + mesh + abaqus_results → 至少 25 个数值特征
4. 相似案例检索用余弦距离 + 特征归一化

**验收：** 扫描一个 Abaqus 案例目录后，`case_summary.json` 包含所有新字段。从 5 个案例导出数据集有 25+ 特征列。

---

## TASK 9：代理模型升级

**目标：** 统一模型注册、多模型对比、置信区间、预测入口。

**要改的文件：** `surrogate_model.py`, `composite_dataset.py`, `streamlit_app.py`

**具体步骤：**
1. `surrogate_model.py` 增加 `GradientBoostingRegressor` 作为第三种模型选项
2. 统一 `train_surrogate_from_dataset()` 和 `train_composite_surrogate()` 的输出格式：相同的 metrics dict、predictions CSV 列、模型 pickle 结构
3. 新增 `compare_all_models()` 函数：对同一个数据集训练 RF + MLP + GBR，输出对比表（MAE/RMSE/R²/CV/训练时间）
4. Streamlit 代理模型面板增加"多模型对比"模式：选数据集 → 一键训练三种模型 → 对比表 + 柱状图
5. 统一不确定性输出：所有模型都输出 `prediction_lower`/`prediction_upper`/`prediction_std`

**验收：** 对一个数据集运行 compare_all_models()，输出 RF/MLP/GBR 三行对比表。Streamlit 面板有"多模型对比"按钮。

---

## TASK 10：最小但完整的产品级闭环案例

**目标：** 一条命令跑通复合材料微观 RVE → Abaqus PBC → 3D 板孔 → ODB → 入库 → 代理模型 → 自然语言复现。

**要改的文件：** 新增 `run_product_closed_loop.py`

**具体步骤：**
1. 创建端到端脚本，参数化关键输入（Vf, 材料属性, 几何, 网格）
2. 执行顺序：
   - 生成 RVE（保证 Vf 精度 ±3%）
   - 跑 PBC 6 工况 → Abaqus 均匀化
   - 生成 3D 板孔模型 → Abaqus 求解
   - ODB 后处理 → 提取应力/位移/反力
   - 案例入库 → 导出数据集
   - 训练代理模型（多模型对比）
   - 生成闭环报告（含 Abaqus vs ROM 对比、代理模型指标）
3. 最后一步：用自然语言查询 "复现 Vf=0.55 的碳纤维板孔仿真" → LLM 解析为配置 → 显示与原始运行的差异 → 可一键重新运行

**验收：** `python -m material_ai_workbench.run_product_closed_loop --vf 0.55` 跑完全流程。最后一条自然语言命令能复现相同配置。

---

## 执行顺序

```
TASK 7 (依赖修复) → 先跑通环境
  ↓
TASK 1 (Abaqus 闭环) + TASK 2 (Vf 精度) + TASK 3 (PBC 均匀化) → 并行，都改 composite_workflow.py
  ↓
TASK 5 (MCP 实时) → 依赖 TASK 1 的 Abaqus 基础设施
  ↓
TASK 4 (NL 计划系统) + TASK 6 (合并验证) + TASK 8 (案例库升级) → 并行
  ↓
TASK 9 (代理模型升级)
  ↓
TASK 10 (产品闭环案例) → 集成所有上述功能
```

**注意：Task 1-5 是核心，必须先打穿。Task 6-10 是完善和收尾。**
