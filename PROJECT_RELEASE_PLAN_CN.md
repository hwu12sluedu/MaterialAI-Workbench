# MaterialAI Workbench 项目总纲与发布计划

## 1. 项目一句话

MaterialAI Workbench 是一个面向机械工程师的本地仿真 AI 工具原型。它基于 pyLabFEA 学习和训练材料本构/屈服模型，导出 Abaqus UMAT 参数，调用 Abaqus 做材料力学行为验算，并逐步扩展到自然语言仿真任务、模型管理、结果报告和 GitHub 项目发布。

## 2. 项目要解决什么问题

传统 Abaqus 仿真依赖大量手工操作：建模、材料定义、Job 管理、结果提取、报告整理都比较分散。机器学习和有限元结合时，又常见两个断点：

1. AI 模型训练出来以后，难以和真实 CAE 求解流程闭环验证。
2. 普通工程师很难把材料数据、仿真任务、模型版本、结果报告统一管理。

本项目的目标是把这些环节串起来：

```text
材料参数/仿真数据
-> 机器学习材料模型
-> Abaqus UMAT 验算
-> 结果曲线/云图/指标
-> 可追溯报告
-> 材料模型资产管理
-> 案例库和仿真数据飞轮
-> 自然语言辅助仿真
```

短期先做材料本构闭环，长期再扩展为有限元 AI Workbench。

长期产品愿景见：

```text
docs/PRODUCT_VISION_CASE_LIBRARY_CN.md
```

核心方向是把每天做过的 Abaqus 案例沉淀成可检索、可训练、可复用的案例库，再用这些真实案例支撑材料本构训练、神经网络代理模型、批量仿真和自然语言相似案例复用。

## 3. 当前已经完成

当前项目已经具备一个可运行的 MVP：

1. 复现 pyLabFEA，并跑通核心 notebook 和测试。
2. 封装材料 AI 训练流程，支持 J2 和 Hill 参考材料。
3. 使用 SVC 训练机器学习屈服模型。
4. 自动输出屈服面图、训练指标、UMAT 参数 CSV/JSON 和 Markdown 报告。
5. 接入 Abaqus UMAT 单元级验算，已完成一次 Abaqus sanity check。
6. 做出 Streamlit App，包含 AI 任务、材料训练、数据导入、案例库、Abaqus MCP、Abaqus 验算、批量仿真、结果浏览、代理模型、模型管理十个页面。
7. 加入材料模板库和 run 历史管理。
8. 加入规则版自然语言任务解析层，可把材料训练/Abaqus 验算需求解析为任务 JSON，并在 App 中执行材料训练。
9. 加入 CSV 数据导入 v0，可导入实验应力-应变曲线或 Abaqus 结果 CSV，输出标准化曲线、预览图和导入报告。
10. 加入 Abaqus MCP 实时连接工作台，可连接当前打开的 Abaqus/CAE，读取模型/Job/ODB，设置工作目录，抓取 viewport，并生成会话快照。
11. 加入案例库 v0，可索引日常 Abaqus 案例文件夹或单个 `.inp` 文件，识别模型、结果、数据、图片、报告和脚本文件，生成 `case_summary.json` 和 `case_report.md`。
12. 加入 INP 特征提取 v0，可从 `.inp` 中提取节点/单元数量估算、材料、Step、单元类型、载荷、边界、接触和输出关键字。
13. 加入结果特征提取 v0，可索引 ODB 路径元数据，并从 CSV/日志中提取行数、关键结果候选最大值、warning/error 计数和状态提示。
14. 加入 ODB 深度后处理 v0，可通过 Abaqus MCP 提取 ODB 最后一帧场变量统计并抓取 Abaqus viewport 云图；同时加入 Abaqus `SMAPython.exe` 批处理后端，在 MCP 未重新加载或不可用时仍可提取 ODB 场变量统计，输出 JSON/CSV/Markdown。
15. 加入 ODB 帧曲线提取 v0，可按每一帧导出 `S/PEEQ/U/RF` 等字段的 min/max/mean/max_abs 曲线；已支持可选 named set 局部曲线，输出 `Region` / `RegionKind`，用于训练样本、结果趋势检查和代理模型标签构建。
16. 加入案例库训练数据集导出 v0，可生成 `case_dataset.csv`、`frame_series_index.csv`、`dataset_manifest.json` 和 `dataset_report.md`，把日常 Abaqus 案例转为可训练样本索引。
17. 加入代理模型 v0，可从案例库训练数据集训练 RandomForest/MLP baseline，输出 `surrogate_model.pkl`、`surrogate_metrics.json`、`predictions.csv`、`prediction_vs_truth.png` 和 `surrogate_report.md`。
18. 加入闭环报告 v0，可汇总材料训练、Abaqus 验算、ODB 后处理、案例库、数据集和代理模型产物，输出 `closed_loop_validation_report.md` 和 `closed_loop_manifest.json`。
19. 加入批量仿真 v0，可创建材料参数扫描计划，串行执行材料训练、Abaqus 验算、ODB 后处理和案例归档，记录任务状态，并输出 `batch_plan.json`、`batch_summary.csv` 和 `batch_report.md`；当前已真实跑通 5 个 J2 材料参数扫描样本。
20. 加入 LLM API 可选适配层 v0，支持 OpenAI-compatible `/v1/chat/completions` 风格接口，把自然语言需求转为任务 JSON；默认不联网、不保存 API Key，执行训练和提交 Abaqus 仍需 App 显式按钮确认。

## 3.1 四条原规划的真实进度

| 规划项 | 当前状态 | 说明 |
|---|---|---|
| 把本流程接入 Streamlit，形成可视化 App 原型 | 已开始，已可运行 | 已有十个页面，能完成材料训练、数据导入、案例库、Abaqus MCP 连接、Abaqus 验算、批量仿真、结果浏览、代理模型、模型管理和 AI 任务解析；AI 任务页已支持规则解析和可选 LLM API 增强解析。 |
| 增加 Abaqus job 提交与 ODB/CSV 读取 | 部分完成 | 已完成 UMAT 单元级验算、Abaqus/Standard 调用、ODB 读取、CSV/曲线/报告输出；Abaqus MCP 页面已支持读取/监控/受控提交已有 Job、读取 ODB 元数据、提取 ODB 场变量统计和抓 viewport；案例库已能索引 ODB 路径、提取 CSV/日志结果特征，并支持 MCP / SMAPython 双通道 ODB 场变量统计；还没有做完整任务队列和复杂模型管理。 |
| 加入真实材料曲线或 Abaqus 批量仿真数据导入 | 已开始 | 当前支持 CSV 导入、列识别、标准化曲线、预览图和导入报告；案例库已支持 ODB 帧曲线提取和训练数据集导出；还需要更多数据清洗和批量管理。 |
| 在 SVM 屈服模型之外，增加神经网络代理模型实验 | v0 已开始 | 已加入 RandomForest/MLP baseline，可从包含材料输入参数的 `case_dataset.csv` 训练代理模型并预测 Max Mises/Max U/PEEQ/反力等指标；当前已有 5 条真实 Abaqus 样本，仍只能证明小样本闭环，不能代表工业预测精度。 |

## 4. 下一步不建议直接做完整客户端

下一步不要一上来就做 PySide6/Electron 桌面端。原因很简单：客户端只是外壳，真正值钱的是后端能力。

正确顺序应该是：

```text
任务结构化
-> LLM API 适配
-> 仿真任务执行器
-> 结果和报告标准化
-> 再封装桌面客户端
```

也就是说，先让自然语言能够稳定变成一个可审查、可执行、可追溯的仿真任务，再考虑更漂亮的客户端。

## 5. 最近一个阶段要做什么

最近阶段建议命名为：

`NL2Abaqus Task Layer`

目标不是让 AI 随便控制 Abaqus，而是让 AI 做三件可控的事：

1. 把自然语言需求解析成标准任务 JSON。
2. 在执行前展示给工程师确认。
3. 调用已有的训练、Abaqus 验算、报告生成能力。

最小示例：

```text
用户输入：
用 J2 材料，E=200000 MPa，nu=0.3，屈服 60 MPa，训练一个材料模型，并跑 1 个 Abaqus 单元验算。

系统解析为：
{
  "task_type": "material_training_with_abaqus_check",
  "material": {
    "type": "j2",
    "youngs_modulus": 200000,
    "poisson_ratio": 0.3,
    "yield_strength": 60
  },
  "ml": {
    "model": "svc",
    "C": 1.0,
    "gamma": 1.0
  },
  "abaqus": {
    "run_check": true,
    "max_load_cases": 1
  }
}
```

这个 JSON 先展示给用户确认，再执行。这样既有 AI 交互，又不会失控。

## 6. 多 LLM API 怎么接

多模型 API 不应该散落在业务代码里，建议单独做一个 LLM 适配层：

```text
llm/
  providers.py
  schema.py
  prompt_templates.py
  task_parser.py
```

第一版只需要定义统一接口：

```text
输入：用户自然语言 + 当前材料库/模型历史摘要
输出：结构化任务 JSON + 风险提示 + 缺失参数问题
```

后续再接不同服务商：

- OpenAI API
- DeepSeek API
- 通义千问 API
- Claude API
- 本地模型 API

关键原则：LLM 只负责“理解和规划”，真正执行 Abaqus、读写文件、生成报告必须走我们自己的受控工具函数。

## 7. 未来客户端形态

客户端可以分三层演进：

1. 当前阶段：Streamlit 本地 Web App
   - 速度最快，适合原型验证。
   - 已经能跑材料训练和 Abaqus 验算。

2. 工程化阶段：FastAPI 后端 + Streamlit 或简单前端
   - 把训练、Abaqus、报告、LLM 解析做成 API。
   - 为后续桌面端做准备。

3. 发布阶段：PySide6 / Electron / Tauri 桌面端
   - 做成真正客户端。
   - 支持项目管理、LLM Key 配置、任务队列、Abaqus Job 管理、结果浏览和报告导出。
   - 与 Abaqus/CAE 的实时连接使用现有 Abaqus MCP，而不是重新造一套直接控制 Abaqus 的桥。

## 7.1 客户端什么时候开始

客户端不等于现在不做，而是分阶段开始：

1. 当前已经开始的是“客户端原型”：Streamlit 本地 App，验证业务闭环和页面逻辑。
2. 下一步补齐数据导入、任务队列、MCP 连接状态面板和 LLM API 配置后，开始做“工程化后端 API”。
3. 当后端 API 和 Abaqus MCP 调用契约稳定后，再启动 PySide6/Electron/Tauri 桌面客户端。

启动桌面客户端的最低条件：

- 数据导入 v0 可用
- Abaqus MCP 连接状态可检测：已完成
- 至少有 3-5 个稳定 MCP 工具动作：连接检查、工作目录设置、job 列表、job 监控、job 提交、ODB 元数据、viewport 截图，已完成第一版
- 任务 JSON 和 run 历史结构稳定
- LLM API Key 配置方案明确

## 8. 全套中文文档要包括什么

最终 GitHub 项目至少需要这些中文文档：

1. `README_CN.md`
   - 项目是什么、能做什么、快速开始、运行截图。

2. `LEARNING_PLAN_CN.md`
   - pyLabFEA 学习路线、notebook 顺序、每部分学什么。

3. `PYLABFEA_APP_ROADMAP_CN.md`
   - 从 pyLabFEA 到 App 的技术拆解。

4. `PROJECT_RELEASE_PLAN_CN.md`
   - 项目目的、作用、发布路线、简历表达。

5. `docs/CODE_STUDY_CN.md`
   - 代码学习笔记：pipeline、Abaqus bridge、Streamlit、材料库、LLM 层。

6. `docs/USER_GUIDE_CN.md`
   - 面向普通用户的使用说明：如何训练、如何跑 Abaqus、如何看报告。

7. `docs/TECHNICAL_ARCHITECTURE_CN.md`
   - 面向面试官/技术评审的架构说明。

8. `docs/RESUME_PROJECT_CN.md`
   - 简历项目描述、面试讲解稿、项目亮点和常见问题回答。

9. `docs/ABAQUS_MCP_WORKBENCH_CN.md`
   - Abaqus MCP 连接、Job、ODB、viewport 和后续客户端路线说明。

10. `docs/PRODUCT_VISION_CASE_LIBRARY_CN.md`
   - 最终产品愿景：案例库、批量仿真、特征提取、神经网络代理模型和自然语言复用。

11. `docs/CASE_LIBRARY_USER_GUIDE_CN.md`
   - 案例库 v0 使用说明：如何录入日常 Abaqus 案例、识别哪些文件、后续如何用于训练。

## 9. GitHub 发布前检查清单

发布前需要完成：

1. 明确开源协议风险：pyLabFEA 是 GPLv3，公开发布时需要尊重其协议。
2. 清理无关缓存、临时运行文件、超大 Abaqus 结果文件。
3. 准备可复现 demo 数据，不依赖个人隐私路径。
4. 提供一键运行命令。
5. 提供截图和示例报告。
6. 写清楚 Abaqus 是可选依赖，且需要用户本机有 Abaqus/Fortran 环境。
7. 增加基础测试，至少覆盖材料库、pipeline、Abaqus bridge 的非求解逻辑。
8. 准备 release 版本说明。

## 10. 简历中怎么表达

建议项目名：

`MaterialAI Workbench: 有限元材料本构训练与 Abaqus 验算平台`

简历描述可以写：

- 基于 pyLabFEA 和 Abaqus 搭建材料 AI 闭环平台，实现从材料参数生成训练数据、训练机器学习屈服模型、导出 UMAT 参数到 Abaqus 单元级验算的自动化流程。
- 设计 Streamlit 本地应用，集成材料训练、Abaqus Job 验算、案例库、ODB 后处理、代理模型、结果浏览、材料模板库和模型历史管理，输出可追溯 Markdown/CSV/PNG 报告。
- 封装 Abaqus UMAT 验算桥接模块，自动准备输入文件、调用 Abaqus/Standard、读取 ODB 结果并生成应力-应变曲线和关键指标。
- 构建案例库训练数据集与代理模型 baseline，把日常 Abaqus 案例转成 `case_dataset.csv`，并用 RandomForest/MLP 预测 Max Mises、Max U 等结果指标，形成有限元数据飞轮雏形。
- 规划自然语言仿真任务层，将工程师自然语言需求解析为结构化仿真任务 JSON，为后续多 LLM API 接入和桌面端客户端化奠定基础。

面试时要讲清楚三件事：

1. 我不是简单调用 AI，而是把 AI 嵌入有限元工程闭环。
2. 我理解材料本构、屈服准则、UMAT 和 Abaqus 验算的工程意义。
3. 我能把仿真流程产品化：参数、任务、结果、报告、模型资产都能管理。

## 11. 当前下一步执行任务

当前已经完成：

`代理模型 v0`

已完成交付物：

1. `material_ai_workbench/surrogate_model.py`
   - 从 `case_dataset.csv` 读取案例库训练样本。
   - 过滤没有目标值的样本，构建数值/类别特征。
   - 支持 RandomForest 和 MLP baseline。
   - 输出模型、特征表、标签表、预测表、误差指标、预测图和报告。

2. Streamlit 新增 `代理模型` 页面
   - 选择案例库导出的 dataset。
   - 选择预测目标。
   - 选择 RandomForest 或 MLP。
   - 训练后查看 MAE、RMSE、预测图、预测明细和报告。

3. 已用真实导出的案例库数据集跑通
   - 当前真实数据集只有 1 条可用目标样本。
   - 本次只证明流程闭环，不代表预测精度。
   - 后续需要批量 Abaqus 样本扩充和 holdout/交叉验证。

当前最新阶段已经完成批量样本扩充和任务队列 v0 的第一轮真实闭环：已完成批量计划后端、Streamlit 批量仿真页面，并真实跑通 5 个 J2 材料参数扫描样本；这些样本已回写案例库、重新导出 5 行训练数据集，并训练 RandomForest 与 MLP 两个代理模型 baseline。

结合最终产品方向，`案例库 v0` 已完成第一版：

1. 手动录入案例标题、标签、说明。
2. 选择本地 Abaqus 案例文件夹，或者直接选择单个 `.inp` 文件。
3. 自动识别 `.cae`、`.inp`、`.odb`、`.sta`、`.msg`、`.csv`、`.png`、`.pdf`。
4. 对 `.inp` 提取节点/单元数量估算、材料、Step、单元类型、载荷、边界、接触和输出关键字。
5. 对 `.odb` 索引路径元数据，对 `.csv` / `.sta` / `.msg` / `.dat` / `.log` / `.rpt` 提取结果特征。
6. 对包含 ODB 的案例，可通过 Abaqus MCP 提取 ODB 场变量统计和云图截图，并追加回 `case_summary.json`。
7. 生成 `case_summary.json` 和 `case_report.md`。
8. 在 App 中增加 `案例库` 页面，用来查看成功做成的仿真例题、INP 特征摘要、结果特征摘要和 ODB 深度后处理记录。

下一步应继续完善 `关键节点/单元集曲线和批量队列`：当前已通过 Abaqus `SMAPython.exe` 批处理支持按 named set 提取逐帧局部曲线；后续要补批量队列、曲线质量检查、常用 named set 模板，以及 MCP 重载成功后的实时云图/局部结果联动。
