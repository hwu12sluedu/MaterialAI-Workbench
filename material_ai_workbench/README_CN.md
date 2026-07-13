# MaterialAI Workbench v0.1

这是在 pyLabFEA 之上构建的首个公开工程 MVP。它的目标不是替代 Abaqus，而是打通一个可复用、可追溯的材料 AI 闭环：

```text
参考材料
-> 训练 ML 屈服模型
-> 生成应力-应变曲线和屈服面
-> 导出 Abaqus UMAT 可读取的 SVM 参数
-> 生成可追溯报告
```

## 当前支持

- `j2`：各向同性 J2 塑性参考材料
- `hill`：Hill 型各向异性塑性参考材料
- SVC 屈服函数训练
- 支持向量和训练指标汇总
- 屈服面图、应力-应变曲线图
- Abaqus UMAT 参数 CSV 和 meta JSON
- Markdown 报告
- 材料模板库和训练/Abaqus run 历史管理
- 规则版自然语言任务解析，把仿真需求转换为任务 JSON
- 实验曲线/Abaqus 结果 CSV 导入和标准化预览
- Abaqus 案例库 v0：索引日常仿真案例文件夹或单个 `.inp` 文件，生成案例摘要和报告，并提取 INP 结构特征、ODB/CSV/日志结果特征和 ODB 深度后处理记录
- ODB 深度后处理双通道：实时 MCP 可抓取云图；Abaqus `SMAPython.exe` 批处理可在 MCP 未重新加载时继续提取场变量统计
- ODB 帧曲线提取：按每一帧导出 `S/PEEQ/U/RF` 等字段的 min/max/mean/max_abs 曲线
- 案例库训练数据集导出：把 INP 输入特征、结果特征、ODB 后处理和帧曲线索引合成为 CSV 数据资产
- 代理模型 v0：从案例库训练数据集训练 RandomForest/MLP baseline，预测 Max Mises、Max U、PEEQ、反力等结果指标，并输出模型、误差表、预测图和报告
- 闭环报告 v0：汇总材料训练、Abaqus 验算、ODB 后处理、案例库、数据集和代理模型产物，生成端到端验证报告
- 批量仿真 v0：创建材料参数扫描计划，串行运行材料训练、Abaqus 验算、ODB 后处理和案例归档，记录 pending/running/completed/failed/postprocessed 状态，并输出 batch plan、summary CSV 和报告
- 小样本代理模型闭环：已用 5 个 J2 参数扫描样本导出包含材料输入参数的数据集，并训练 RandomForest 与 MLP baseline
- Abaqus MCP 实时连接工作台：连接检查、模型/Job 读取、工作目录设置、ODB 元数据读取、ODB 场变量提取、视口截图和会话快照

当前支持 J2、Hill、Barlat 各向异性屈服、Neo-Hookean 和 Mooney-Rivlin 超弹性。可创建复合材料微观 RVE 模型并生成 Abaqus 带孔板验证模型。

产品级 smoke 验证可先不调用 Abaqus，适合作为 GitHub 发布和演示入口：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_product_closed_loop --vf 0.55
```

该命令会生成微观 RVE、6 个 PBC 均匀化载荷工况 INP、3D 带孔板 Abaqus 建模脚本、数据集行和产品报告。需要真实求解时再显式增加 `--run-abaqus --submit-job`。

## 安装与运行

```bash
# 1. 创建 conda 环境
conda create -n pylabfea python=3.12
conda activate pylabfea

# 2. 安装 MaterialAI Workbench
cd MaterialAI-Workbench
pip install -e ".[app]"

# 3. 启动 Web 工作台
materialai-streamlit

# 4. 或使用命令行
materialai-workbench --material j2 --name demo
```

浏览器打开 `http://localhost:8501` 即可使用。所有命令：

| 命令 | 功能 |
|------|------|
| `materialai-streamlit` | 启动 Web 工作台 |
| `materialai-workbench --material j2` | 训练 J2 材料模型 |
| `materialai-composite` | 生成复合材料 RVE + 板孔模型 |
| `materialai-composite-closed-loop` | 复合材料完整闭环（含 Abaqus） |
| `materialai-metal-closed-loop` | 金属材料批量参数扫描闭环 |
| `materialai-composite-batch` | 复合材料批量数据生成 |
| `materialai-product-closed-loop` | 产品级轻量闭环：RVE + PBC 作业文件 + 带孔板脚本 + 数据行 + 报告 |

App 当前包含以下工作区：

- `AI 任务`：输入自然语言，解析为结构化任务 JSON，确认后执行材料训练，可选 Abaqus 验算。
- `材料训练`：输入材料与 SVC 参数，一键训练并生成报告。
- `数据导入`：导入实验曲线 CSV 或 Abaqus 结果 CSV，生成标准化曲线、预览图和导入报告。
- `案例库`：录入每天完成的 Abaqus 案例文件夹或单个 `.inp` 文件，自动识别模型、ODB、日志、数据、图片、报告和脚本，并展示 INP 特征摘要、ODB 路径元数据、CSV 关键结果、日志 warning/error 计数、ODB 深度后处理记录和 ODB 帧曲线记录；支持导出训练数据集。
- `Abaqus MCP`：连接当前打开的 Abaqus/CAE，检查 bridge 状态，读取模型/Job/ODB，提取 ODB 场变量，抓取 viewport，并生成会话快照。
- `Abaqus 验算`：选择已有 run，准备或运行 Abaqus UMAT 单元验算。
- `批量仿真`：创建材料参数扫描计划，运行材料训练或显式确认后运行 Abaqus，并查看批量状态表和报告。
- `结果浏览`：查看训练指标、屈服面、Abaqus 曲线、CSV 预览和报告。
- `代理模型`：选择案例库导出的训练数据集，训练 RandomForest 或 MLP baseline，并查看 MAE、RMSE、预测图、预测明细和报告；也可以生成最新闭环报告。
- `模型管理`：查看材料模板库、训练历史、Abaqus 验算状态和当前 run 的关键结果。

材料训练页里的 `材料库` 折叠区可以把当前参数保存成模板，也可以把已有模板加载回训练表单。材料模板存放在：

```text
material_ai_workbench/library/materials.json
```

当前内置两个演示模板：

- `Demo_J2_60MPa`：J2 各向同性塑性材料快速验证模板
- `Demo_Hill_sheet`：Hill 各向异性板材风格模板

如果要同时计算 pyLabFEA 内部小有限元应力-应变曲线，添加：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name demo_j2_curves --with-curves
```

Hill 材料示例：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material hill --name demo_hill --sy 50 --C 2 --gamma 1
```

输出默认写入：

```text
workspace/runs/<时间戳>_<名称>/
```

每次运行会生成：

- `summary.json`：机器可读的结果摘要
- `reports/material_model_report.md`：人可读的首轮报告
- `figures/yield_locus.png`：屈服面图
- `figures/stress_strain_curves.png`：应力-应变曲线图或跳过说明
- `data/stress_strain_curves.csv`：曲线数据或跳过说明
- `models/abq_<材料名>-svm.csv`：Abaqus UMAT 参数
- `models/abq_<材料名>-svm_meta.json`：Abaqus UMAT 参数元数据

## 和 Abaqus 的关系

当前版本已经可以把导出的 UMAT 参数接到 Abaqus 单元级验算。桥接脚本会自动准备独立工作目录，复制：

- `examples/UMAT/ml_umat.f`
- `examples/UMAT/femBlock.inp`
- `examples/UMAT/calc_properties.py`

并把当前 run 里的 `models/abq_<材料名>-svm.csv/json` 放到 Abaqus 脚本要求的位置。

准备 Abaqus 验算目录：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<run_name>
```

运行 Abaqus sanity check，默认建议先只跑 1 个载荷工况：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<run_name> --max-load-cases 1 --run
```

完整载荷工况可使用：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<run_name> --max-load-cases 0 --run
```

Abaqus 验算输出在：

```text
workspace/runs/<run_name>/abaqus_verification/
```

包含：

- `bridge_summary.json`
- `abaqus_verification_report.md`
- `logs/abaqus_python.log`
- `results/abq_<材料名>-res.csv`
- `results/abq_<材料名>-res_meta.json`
- `results/abaqus_stress_strain_check.png`

已验证示例：`smoke_j2_fast` 的 1 个载荷工况 Abaqus sanity check 已完成，UMAT 编译、Abaqus/Standard 求解、ODB 读取和结果曲线生成均成功。

## LLM API 可选接入

`AI 任务` 页面默认使用规则解析器，不会联网，也不会读取 API Key。如果需要接入外部或本地大模型，可在页面中展开 `LLM API（可选）`，勾选“允许本次调用外部 LLM API”后再调用。

默认读取这些环境变量：

```text
MATERIALAI_LLM_BASE_URL
MATERIALAI_LLM_MODEL
MATERIALAI_LLM_API_KEY
```

当前适配的是 OpenAI-compatible `/v1/chat/completions` 协议，适合先接入 OpenAI-compatible 网关、本地模型服务或企业内部模型代理。LLM 只负责生成任务 JSON；真正执行材料训练或提交 Abaqus 前，仍由 App 的按钮和显式确认控制。

## Abaqus MCP 实时连接

如果要使用 `Abaqus MCP` 页面，需要先打开 Abaqus/CAE，并在 Abaqus 中执行：

```text
Plug-ins > Abaqus MCP > Start Socket Bridge
```

默认连接地址：

```text
127.0.0.1:48152
```

新版 Abaqus MCP 的设计目标是直接连接正在运行的 Abaqus/CAE，不再走旧的命令文件轮询队列；短脚本状态读取应保持低延迟，并且不应让 Abaqus 窗口长时间冻结。

当前页面支持：

- 检查 Abaqus MCP 连接状态
- 读取当前模型和 Job 列表
- 设置 Abaqus 当前工作目录
- 监控 Job 的 `.sta` / `.msg` 尾部诊断
- 在显式确认后提交已有 Job
- 读取本地 ODB 元数据
- 提取 ODB 最后一帧场变量统计
- 抓取 Abaqus 当前 viewport 图片
- 生成会话快照和 Markdown 报告

详细说明见：

```text
docs/ABAQUS_MCP_WORKBENCH_CN.md
```

## 案例库

`案例库` 页面用于沉淀你每天做过的 Abaqus 案例。第一版只索引文件路径和元数据，不复制大型 `.cae` / `.odb` 文件。对于 `.inp` 文件，系统会额外提取节点数估算、单元数估算、材料、Step、单元类型、载荷、边界和输出关键字。对于结果文件，系统会索引 ODB 路径元数据，并从 CSV/日志中提取行数、Mises/PEEQ/位移/反力候选最大值、warning/error 计数。对于有 ODB 的案例，可以在案例详情中提取场变量统计、逐帧曲线，以及可选 named set 的局部曲线，并保存报告。

每个案例会生成：

```text
workspace/cases/<case_id>/
  case_summary.json
  case_report.md
```

当前可自动分类：

- 模型文件：`.cae`、`.inp`、`.step` 等
- 结果文件：`.odb`、`.sta`、`.msg`、`.dat` 等
- 数据文件：`.csv`、`.xlsx`、`.json` 等
- 图片/报告/脚本

如果你只有一个 `.inp`，也可以直接录入单个文件路径。它会成为一个独立案例，适合后续批量收集真实模型样本。

当前 ODB 深度后处理已接入双通道：实时 MCP 可提取最后一帧的 `S/PEEQ/U/RF/CPRESS/COPEN` 等字段统计并抓取当前 Abaqus 视口云图；Abaqus `SMAPython.exe` 批处理可在 MCP 未连接或当前 Abaqus 窗口尚未重新加载新版插件时继续读取 ODB 结果。案例库支持单个 ODB 提取和“批量提取全部 ODB”，输出包括 `odb_field_summary.json`、`odb_field_summary.csv`、`odb_field_report.md`。逐帧曲线提取已支持可选 named set，CSV 会记录 `Region` / `RegionKind`，用于后续关键节点、关键单元集和局部响应代理模型训练。

案例库还支持 ODB 帧曲线提取：按每一帧导出 `S/PEEQ/U/RF` 等字段的 min/max/mean/max_abs，输出 `odb_frame_series.json`、`odb_frame_series.csv` 和 `odb_frame_series_report.md`。这些帧曲线会进入 `frame_series_index.csv`，作为后续神经网络代理模型的时间序列训练入口。

训练数据集导出会生成：

- `case_dataset.csv`
- `frame_series_index.csv`
- `dataset_manifest.json`
- `dataset_report.md`

它把日常案例沉淀成“可训练样本索引”。当前已经在此基础上接入代理模型 v0，可训练 RandomForest/MLP baseline；样本量很少时只用于验证产品闭环，不代表工业预测精度。

详细说明见：

```text
docs/CASE_LIBRARY_USER_GUIDE_CN.md
```

## 后续扩展

当前四条规划状态：

1. `把本流程接入 Streamlit，形成可视化 App 原型`：已开始并基本跑通。
2. `增加 Abaqus job 提交与 ODB/CSV 读取`：已完成单元级 UMAT 验算桥接，并新增 Abaqus MCP 页面；支持实时读取模型/Job/ODB、ODB 场变量统计、抓视口和受控提交已有 Job，完整任务队列和复杂模型管理还没做。
3. `加入真实材料曲线或 Abaqus 批量仿真数据导入`：已开始，当前支持 CSV 导入、列识别、标准化曲线和预览报告。
4. `在 SVM 屈服模型之外，增加神经网络代理模型实验`：v0 已开始并跑通，当前支持 RandomForest 和 MLP baseline，从 `case_dataset.csv` 预测 `latest_odb_max_mises` 等结果指标。

后续建议顺序：

1. 强化案例库，继续补关键节点/单元集曲线、批量 ODB 队列和相似案例检索。
2. 强化真实材料曲线或 Abaqus 批量仿真数据导入，增加更多列映射和数据清洗规则。
3. 增加任务队列，避免长时间 Abaqus job 阻塞界面。
4. 扩充代理模型训练样本，把单样本流程验证升级为多案例 holdout/交叉验证。
5. 接入真实 LLM API 配置，并让后续客户端通过现有 Abaqus MCP 与 Abaqus/CAE 实时连通。
