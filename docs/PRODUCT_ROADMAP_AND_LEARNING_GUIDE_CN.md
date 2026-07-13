# MaterialAI Workbench 终局产品路线图与中文学习总纲

## 1. 我们最终要发布的产品是什么

`MaterialAI Workbench` 最终不是一个单纯的 pyLabFEA 示例，也不是一个只会调用 Abaqus 的脚本集合，而是一个面向机械工程师的本地 CAE + AI 工作台。

最终用户画像就是现在的你：

- 会做 Abaqus 仿真。
- 懂材料、结构、载荷、边界、后处理。
- 想把每天做过的仿真案例沉淀成资产。
- 想用机器学习/神经网络提升仿真效率。
- 想用自然语言减少重复建模、提交 Job、读 ODB、写报告的手工工作。

产品最终闭环：

```text
日常 Abaqus 案例
-> 案例库归档
-> INP/ODB/CSV/日志/云图/报告特征提取
-> 材料本构训练与代理模型训练
-> Abaqus 真实模型验证
-> 自然语言生成可审查任务 JSON
-> 用户确认后批量运行 Abaqus
-> 自动后处理、报告、回写案例库
```

这个产品的核心价值不是“AI 替你点按钮”，而是：

1. 把仿真知识结构化。
2. 把仿真结果数据化。
3. 把重复流程自动化。
4. 把历史案例变成训练样本。
5. 把 AI 放进工程可验证闭环里。

## 2. 当前已经完成了什么

### 2.1 pyLabFEA 学习与复现基础

- 已拉取并配置 `pyLabFEA`。
- 已解决本地导入、测试和 Matplotlib 兼容问题。
- 已明确使用 `conda run -n pylabfea ...` 运行，避免直接调用 env python 导致 native 崩溃。
- 已理解项目核心方向：材料、屈服准则、机器学习流动法则、UMAT/Abaqus 验证。

### 2.2 材料 AI 训练 MVP

- 已新增 `material_ai_workbench` 原创项目骨架。
- 已支持 J2 各向同性参考材料。
- 已支持 Hill 各向异性参考材料。
- 已使用 SVC/SVM 思路训练屈服模型。
- 已输出屈服面图、应力-应变曲线图、模型参数 CSV、meta JSON 和 Markdown 报告。
- 已接入材料模板库，可保存/加载材料参数。

当前必须明确：现阶段 demo 只有 `J2 isotropic` 和 `Hill anisotropic` 两条材料入口。它们是最小 MVP，不代表最终产品只支持这两类材料。后续需要继续扩展 Tresca、Barlat、多线性塑性、实验曲线驱动塑性、超弹性、黏塑性、损伤模型和复合材料均匀化模型。

### 2.3 Abaqus UMAT 单元级验算

- 已封装 `abaqus_bridge.py`。
- 已能从训练 run 准备 Abaqus 验算目录。
- 已复制 UMAT、INP、计算脚本和模型参数。
- 已能调用 Abaqus/Standard 做单元 sanity check。
- 已能读取 Abaqus 结果 CSV/ODB，生成曲线和验算报告。

### 2.4 Streamlit 本地 App 原型

当前 App 已有十个页面：

- `AI 任务`
- `材料训练`
- `数据导入`
- `案例库`
- `Abaqus MCP`
- `Abaqus 验算`
- `批量仿真`
- `结果浏览`
- `代理模型`
- `模型管理`

已经实现：

- 材料训练表单。
- 自然语言规则解析 v0。
- 可选 LLM API 增强解析 v0，默认不联网，支持 OpenAI-compatible 接口生成任务 JSON。
- 材料模板管理。
- 训练历史浏览。
- Abaqus 验算入口。
- 批量仿真计划创建和状态浏览入口。
- 结果图、CSV、报告浏览。
- 案例库、MCP 工作台和代理模型入口。

### 2.5 数据导入 v0

- 已支持实验曲线 CSV 导入。
- 已支持 Abaqus 结果 CSV 导入。
- 已能识别应力/应变候选列。
- 已能输出标准化曲线。
- 已能生成导入报告和预览图。

### 2.6 Abaqus MCP 实时连接工作台

- 已接入本机 Abaqus MCP socket bridge。
- 已支持连接检查。
- 已支持读取模型、Job、工作目录、ODB 元数据。
- 已支持监控 Job 的 `.sta/.msg`。
- 已支持显式确认后提交已有 Job。
- 已支持抓取 Abaqus viewport。
- 已支持生成 MCP 会话快照。
- 已修复本机 Abaqus MCP 插件到 `v5.0.3`，当前已打开的 Abaqus 需要重新加载插件后才能使用新版内存代码。

### 2.7 案例库 v0

- 已能录入 Abaqus 案例文件夹。
- 已能录入单个 `.inp` 文件。
- 已能自动分类模型、结果、数据、图片、报告、脚本。
- 已能从 `.inp` 提取节点数、单元数、材料、Step、单元类型、载荷、边界、接触、输出请求。
- 已能从 CSV/日志提取结果行数、Mises、PEEQ、位移、反力、warning、error。
- 已生成 `case_summary.json` 和 `case_report.md`。

### 2.8 ODB 深度后处理

- 已支持 MCP 读取 ODB 最后一帧场变量。
- 已支持 SMAPython 批处理提取 ODB 逐帧曲线，并可选按 named set 输出局部曲线。
- 已支持 Abaqus `SMAPython.exe` 批处理读取 ODB。
- 已支持字段：`S/PEEQ/U/RF/CPRESS/COPEN`。
- 已输出 `odb_field_summary.json`、`odb_field_summary.csv`、`odb_field_report.md`。
- 已真实提取 `femBlock.odb`，得到 Max Mises 和最大位移。

### 2.9 ODB 帧曲线和训练数据集

- 已支持逐帧提取 `S/PEEQ/U/RF` 等字段的 min/max/mean/max_abs。
- 已输出 `odb_frame_series.json`、`odb_frame_series.csv`、`odb_frame_series_report.md`。
- 已真实提取 `femBlock.odb` 的 101 帧、2 个字段、202 行曲线。
- 已支持导出：
  - `case_dataset.csv`
  - `frame_series_index.csv`
  - `dataset_manifest.json`
  - `dataset_report.md`
- 这已经是神经网络代理模型的训练样本索引入口。

### 2.10 代理模型 v0

- 已新增 `surrogate_model.py`。
- 已支持从 `case_dataset.csv` 读取案例特征和 Abaqus/ODB 目标值。
- 已支持 RandomForest baseline。
- 已支持小型 MLP baseline。
- 已输出 `features.csv`、`targets.csv`、`predictions.csv`、`surrogate_model.pkl`、`surrogate_metrics.json`、`prediction_vs_truth.png` 和 `surrogate_report.md`。
- 已接入 Streamlit `代理模型` 页面。
- 已用当前真实导出的案例库数据集跑通一次训练；当前真实样本只有 1 条，所以只证明产品闭环，不代表预测精度。

### 2.11 最小闭环报告 v0

- 已新增 `closed_loop_report.py`。
- 已能自动汇总最新材料训练 run、Abaqus 验算结果、案例库 case、dataset export 和 surrogate run。
- 已输出 `closed_loop_validation_report.md` 和 `closed_loop_manifest.json`。
- 已接入 Streamlit `代理模型` 页面，可一键生成最新闭环报告。
- 已用当前真实产物生成第一份闭环报告，状态为 `7/7 complete`。

### 2.12 批量仿真 v0

- 已新增 `batch_simulation.py`。
- 已支持创建材料参数扫描计划。
- 已支持串行执行材料训练样本。
- 已支持记录 `pending`、`running`、`material_completed`、`abaqus_completed`、`abaqus_failed`、`postprocessed` 和 `failed` 状态。
- 已输出 `batch_plan.json`、`batch_summary.csv` 和 `batch_report.md`。
- 已接入 Streamlit `批量仿真` 页面。
- 已真实跑通 5 个 J2 材料参数扫描样本，完成材料训练、Abaqus 验算、ODB 后处理、案例归档、数据集导出和代理模型训练。
- 数据集已包含 `yield_strength`、`youngs_modulus`、`poisson_ratio`、`n_load_cases` 等材料/仿真输入参数。

## 3. 距离最终产品还需要哪些阶段

下面按非常细的步骤拆分。每个阶段都要满足“能运行、能解释、能写进简历、能给别人复现”的标准。

## 4. 阶段 A：把当前 MVP 整理成稳定学习版

目标：你自己能看懂源码，能从头跑一遍，能讲清楚每个模块。

### A1. 项目结构清理

1. 梳理 `material_ai_workbench` 每个文件的职责。
2. 区分核心代码、实验数据、生成结果、文档。
3. 明确哪些文件进 GitHub，哪些文件放 `.gitignore`。
4. 清理临时日志和无效中间目录。
5. 保留小型 demo 数据，不上传大型 ODB/CAE。

### A2. 运行入口统一

1. 整理命令行运行入口。
2. 整理 Streamlit 启动入口。
3. 整理 Abaqus 验算入口。
4. 整理案例库扫描入口。
5. 整理数据集导出入口。
6. 每个入口给出一条可复制命令。

### A3. 测试基线

1. 保留材料训练非 Abaqus 单元测试。
2. 保留案例库 INP/CSV/日志解析测试。
3. 保留 ODB 后处理 mock 测试。
4. 保留 dataset export 测试。
5. 给 Abaqus 相关测试标注为可选集成测试。
6. 写清楚没有 Abaqus 时能跑哪些测试。

### A4. 学习版源码注释

1. 给 `pipeline.py` 加学习导读。
2. 给 `abaqus_bridge.py` 加流程注释。
3. 给 `case_library.py` 加数据结构说明。
4. 给 `odb_postprocess.py` 加 ODB 后处理说明。
5. 给 `dataset_export.py` 加训练集设计说明。
6. 注释要解释工程目的，不写废话。

## 5. 阶段 B：神经网络代理模型 v0

目标：先做一个小而真的代理模型，不追求高精度，先把数据闭环打通。

当前状态：B1-B4 已完成 v0；B5 教学文档按你的要求推迟到产品 launch 前统一整理。闭环报告 v0 和批量仿真 v0 均已完成第一版，当前已用 5 个真实 Abaqus 样本重新导出数据集，并训练 RandomForest 与 MLP baseline。

### B1. 定义代理模型任务

1. 选择第一个预测目标：`Max Mises`。
2. 选择第二个预测目标：`Max U`。
3. 明确输入特征：节点数、单元数、材料、Step、单元类型、CSV/ODB 特征等。
4. 明确哪些字段暂时不用，例如中文说明、路径、报告文本。
5. 明确数据量少时只做 demo，不吹成工业级模型。

### B2. 数据清洗

1. 读取 `case_dataset.csv`。
2. 删除没有目标值的样本。
3. 数值特征填充缺失值。
4. 类别特征编码。
5. 路径字段仅作为索引，不进入模型。
6. 输出清洗后的 `features.csv` 和 `targets.csv`。

### B3. Baseline 模型

1. 先做 `RandomForestRegressor` baseline。
2. 再做小型 `MLPRegressor` baseline。
3. 数据很少时使用留一法或简单 train/test split。
4. 输出 MAE、RMSE、相对误差。
5. 输出预测 vs 真实散点图。
6. 输出 `surrogate_report.md`。

### B4. App 接入

1. 增加 `代理模型` 页面。
2. 选择一个 dataset export。
3. 点击训练 baseline。
4. 显示训练结果指标。
5. 显示预测图。
6. 保存模型文件。

### B5. 教学文档

1. 解释什么是代理模型。
2. 解释为什么数据少时模型不可靠。
3. 解释特征、标签、训练、验证。
4. 解释和 Abaqus 真实求解的关系。
5. 给出从案例库到代理模型的完整流程。

## 6. 阶段 C：真实材料曲线与本构训练增强

目标：从演示材料走向真实材料数据。

### C1. 材料曲线导入增强

1. 支持工程应力-应变。
2. 支持真应力-真应变。
3. 支持塑性应变列。
4. 支持多温度曲线。
5. 支持多应变率曲线。
6. 支持曲线单位标注。
7. 支持异常点检查。
8. 支持曲线平滑和重采样。

### C2. 参数拟合

1. 拟合双线性塑性。
2. 拟合多线性塑性。
3. 拟合 Swift/Voce 等硬化模型。
4. 输出 Abaqus material card。
5. 输出拟合误差图。
6. 输出拟合报告。

### C3. 材料库增强

1. 增加材料来源字段。
2. 增加单位字段。
3. 增加适用温度/应变率。
4. 增加版本记录。
5. 增加材料对比视图。

## 7. 阶段 D：Abaqus 批量仿真与任务队列

目标：让系统能自动生产训练样本。

### D1. 批量参数表

1. 定义参数扫描 CSV。
2. 支持材料参数扫描。
3. 支持载荷参数扫描。
4. 支持边界条件参数扫描。
5. 支持 step 时间参数扫描。
6. 支持输出请求配置。

### D2. Job 生成

1. 从模板 INP 生成多个 INP。
2. 自动命名 Job。
3. 建立 run 目录。
4. 记录参数和文件路径映射。
5. 生成批处理计划 JSON。

### D3. Job 队列

1. 支持排队。
2. 支持运行中状态。
3. 支持完成/失败状态。
4. 支持日志尾部读取。
5. 支持失败重试。
6. 支持中断后恢复。

### D4. 批量后处理

1. 每个 Job 自动找 ODB。
2. 自动提取最后一帧特征。
3. 自动提取帧曲线。
4. 自动扫描日志 warning/error。
5. 自动生成批量汇总 CSV。
6. 自动生成批量报告。

## 8. 阶段 E：Abaqus MCP 实时建模与自然语言仿真

目标：让自然语言变成可审查的仿真任务，不让 AI 直接失控操作。

### E1. 标准任务 JSON

1. 定义材料训练任务 schema。
2. 定义 Abaqus 后处理任务 schema。
3. 定义 Job 提交任务 schema。
4. 定义案例检索任务 schema。
5. 定义批量仿真任务 schema。
6. 定义风险提示和用户确认字段。

### E2. LLM API 适配层

1. 统一 provider 接口。
2. 支持 OpenAI API。
3. 支持 DeepSeek API。
4. 支持通义千问 API。
5. 支持 Claude API。
6. 支持本地模型 API。
7. API Key 本地保存，不上传 GitHub。
8. 失败时有清晰错误提示。

### E3. Prompt 模板

1. 材料训练 prompt。
2. Abaqus 后处理 prompt。
3. 案例检索 prompt。
4. 批量仿真 prompt。
5. 报告生成 prompt。
6. 风险审查 prompt。

### E4. 用户确认机制

1. LLM 只输出任务 JSON。
2. App 显示任务 JSON。
3. 用户确认后才执行。
4. Job 提交必须二次确认。
5. 文件覆盖必须提示。
6. 长时间任务必须进队列。

### E5. MCP 工具扩展

1. 获取当前模型树。
2. 获取材料列表。
3. 获取 section 列表。
4. 获取 step 列表。
5. 获取 load/BC 列表。
6. 修改材料参数。
7. 修改输出请求。
8. 提交已有 Job。
9. 打开 ODB 云图。
10. 抓取 viewport。

## 9. 阶段 F：案例库智能化

目标：从文件管理变成工程经验检索系统。

### F1. 标签体系

1. 材料标签。
2. 工况标签。
3. 结构类型标签。
4. 成功/失败标签。
5. 收敛问题标签。
6. 后处理指标标签。

### F2. 相似案例检索

1. 基于标签检索。
2. 基于 INP 特征检索。
3. 基于结果指标检索。
4. 基于文本说明检索。
5. 后续接 embedding 检索。

### F3. 案例复用

1. 选择相似案例。
2. 对比参数差异。
3. 生成新任务 JSON。
4. 用户确认修改。
5. 执行新仿真。
6. 结果回写案例库。

## 10. 阶段 G：报告与可视化

目标：一键生成工程报告，而不是只生成数据文件。

### G1. 单案例报告

1. 模型信息。
2. 材料信息。
3. 载荷边界。
4. 求解状态。
5. 关键云图。
6. 关键曲线。
7. 结果指标。
8. 风险说明。
9. 结论和建议。

### G2. 批量报告

1. 批量参数表。
2. 成功/失败统计。
3. 最大值排行榜。
4. 趋势图。
5. 异常工况列表。
6. 代表性云图。

### G3. 导出格式

1. Markdown。
2. HTML。
3. PDF。
4. PPT。
5. CSV/Excel 附表。

## 11. 阶段 H：工程化后端与桌面客户端

目标：从 Streamlit 原型过渡到可发布客户端。

### H1. 后端 API 化

1. 把训练接口做成 API。
2. 把案例库接口做成 API。
3. 把 ODB 后处理接口做成 API。
4. 把任务队列接口做成 API。
5. 把 LLM 解析接口做成 API。

### H2. 桌面端选型

候选：

- PySide6：Python 生态一致，适合本地工程工具。
- Electron：前端生态强，包体大。
- Tauri：轻量，但需要 Rust/前端栈。

建议路线：

1. 先 FastAPI + Streamlit 稳定业务逻辑。
2. 再 PySide6 做本地客户端 v1。
3. 客户端只做界面和任务管理，核心计算仍走后端模块。

### H3. 桌面端功能

1. 项目管理。
2. 案例库浏览。
3. 材料库管理。
4. LLM Key 配置。
5. Abaqus MCP 状态。
6. Job 队列。
7. ODB 后处理。
8. 报告导出。
9. 运行日志。
10. 设置页面。

## 12. 阶段 I：GitHub 发布

目标：别人能看懂、能跑、能信任。

### I1. 仓库清理

1. 删除个人路径敏感信息。
2. 删除超大 ODB/CAE。
3. 保留小 demo。
4. 写 `.gitignore`。
5. 检查许可证。

### I2. 安装文档

1. Conda 环境。
2. pip 安装。
3. Streamlit 启动。
4. Abaqus 可选配置。
5. MCP 可选配置。

### I3. Demo 文档

1. 运行 J2 训练。
2. 运行 Hill 训练。
3. 导入 CSV。
4. 归档 INP 案例。
5. 提取 ODB 特征。
6. 导出训练数据集。
7. 训练代理模型。

### I4. 截图和示例

1. App 首页截图。
2. 材料训练截图。
3. 案例库截图。
4. ODB 后处理截图。
5. 报告截图。
6. 代理模型结果截图。

### I5. 简历材料

1. 简历项目描述。
2. STAR 面试讲稿。
3. 技术亮点。
4. 难点和解决方案。
5. 可量化成果。
6. 常见面试问题回答。

## 13. 必须输出的中文教学文档

为了让你真正学懂，最终建议输出三层中文文档。

### 第一层：源码教学

0. `docs/PYLABFEA_NOTEBOOK_STUDY_GUIDE_CN.md`
   - pyLabFEA 原始 notebook 中文学习总纲。
   - 明确 8 个 notebook 的学习顺序和每篇中文导读的输出格式。
   - 这是必须补的部分，因为 pyLabFEA notebook 代码很难自学，缺少中文注释。

1. `docs/notebook_study/01_Introduction_CN.md`
   - `pyLabFEA_Introduction.ipynb` 中文逐段导读。
   - 解释最小有限元流程、节点、单元、材料、边界和结果。

2. `docs/notebook_study/02_Equivalent_Stress_CN.md`
   - `pyLabFEA_Equiv-Stress.ipynb` 中文逐段导读。
   - 解释等效应力、屈服函数、应力张量标量化。

3. `docs/notebook_study/03_Plasticity_CN.md`
   - `pyLabFEA_Plasticity.ipynb` 中文逐段导读。
   - 解释弹塑性、非线性求解、应力-应变曲线。

4. `docs/notebook_study/04_ML_FlowRule_Training_CN.md`
   - `pyLabFEA_ML-FlowRule-Training.ipynb` 中文逐段导读。
   - 解释机器学习流动法则训练数据如何生成。

5. `docs/notebook_study/05_ML_FlowRule_Hill_CN.md`
   - `pyLabFEA_ML-FlowRule-Hill.ipynb` 中文逐段导读。
   - 解释 Hill 各向异性屈服与当前 Hill demo。

6. `docs/notebook_study/06_ML_FlowRule_Tresca_CN.md`
   - `pyLabFEA_ML-FlowRule-Tresca.ipynb` 中文逐段导读。
   - 解释 Tresca 屈服面和后续扩展价值。

7. `docs/notebook_study/07_Composites_CN.md`
   - `pyLabFEA_Composites.ipynb` 中文逐段导读。
   - 解释复合材料微观力学和 RVE。

8. `docs/notebook_study/08_Homogenization_CN.md`
   - `pyLabFEA_Homogenization.ipynb` 中文逐段导读。
   - 解释均匀化和未来仿真数据生成价值。

9. `docs/CODE_STUDY_00_PROJECT_MAP_CN.md`
   - 项目目录地图。
   - 每个文件负责什么。
   - 先读哪些文件，后读哪些文件。

10. `docs/CODE_STUDY_01_PIPELINE_CN.md`
   - 材料训练 pipeline。
   - J2/Hill 材料如何生成。
   - SVM 屈服模型如何训练。
   - 输出文件如何组织。

11. `docs/CODE_STUDY_02_ABAQUS_BRIDGE_CN.md`
   - Abaqus UMAT 验算流程。
   - 如何准备 INP/UMAT/参数文件。
   - 如何调用 Abaqus。
   - 如何读取结果。

12. `docs/CODE_STUDY_03_CASE_LIBRARY_CN.md`
   - 案例库数据结构。
   - INP 解析逻辑。
   - CSV/日志/ODB 索引逻辑。
   - case_summary 和 case_report。

13. `docs/CODE_STUDY_04_ODB_POSTPROCESS_CN.md`
   - ODB 是什么。
   - FieldOutput/Frame/Step 是什么。
   - 最后一帧统计怎么提取。
   - 帧曲线怎么提取。

14. `docs/CODE_STUDY_05_DATASET_AND_SURROGATE_CN.md`
   - 训练数据集如何导出。
   - 特征和标签是什么。
   - 代理模型怎么训练。
   - 为什么要验证误差。

15. `docs/CODE_STUDY_06_STREAMLIT_APP_CN.md`
   - App 页面结构。
   - 每个页面调用哪些后端函数。
   - session_state 怎么用。
   - 如何从原型走向客户端。

### 第二层：产品应用教学

1. `docs/USER_GUIDE_01_QUICK_START_CN.md`
   - 小白启动流程。
   - 训练 J2 示例。
   - 查看结果。

2. `docs/USER_GUIDE_02_MATERIAL_TRAINING_CN.md`
   - 材料参数含义。
   - J2/Hill 怎么选。
   - 训练参数怎么调。

3. `docs/USER_GUIDE_03_ABAQUS_VALIDATION_CN.md`
   - 如何跑 Abaqus 验算。
   - 需要哪些本机环境。
   - 如何看验算报告。

4. `docs/USER_GUIDE_04_CASE_LIBRARY_CN.md`
   - 如何归档每天的 Abaqus 案例。
   - 如何记录经验。
   - 如何提取 ODB。

5. `docs/USER_GUIDE_05_DATASET_EXPORT_CN.md`
   - 如何导出训练数据集。
   - CSV 每列是什么意思。
   - 后续如何训练代理模型。

6. `docs/USER_GUIDE_06_NL2ABAQUS_CN.md`
   - 自然语言任务怎么写。
   - 什么需要确认。
   - 什么不能让 AI 直接执行。

### 第三层：发布和求职文档

1. `docs/TECHNICAL_ARCHITECTURE_CN.md`
   - 架构图。
   - 模块关系。
   - 工程设计取舍。

2. `docs/PRODUCT_REQUIREMENTS_CN.md`
   - 产品需求文档。
   - 用户故事。
   - 功能优先级。

3. `docs/RELEASE_GUIDE_CN.md`
   - 如何发布 GitHub。
   - 如何清理数据。
   - 如何打 tag。

4. `docs/RESUME_PROJECT_CN.md`
   - 简历描述。
   - 项目亮点。
   - 面试讲解稿。
   - 常见问题回答。

5. `docs/DEMO_SCRIPT_CN.md`
   - 5 分钟演示脚本。
   - 15 分钟面试演示脚本。
   - 从材料训练到 Abaqus 验算到案例库的完整演示。

## 14. 你自己怎么学懂

建议学习顺序：

1. 先学 `pipeline.py`：理解材料训练闭环。
2. 再学 `abaqus_bridge.py`：理解怎么把模型接到 Abaqus。
3. 再学 `case_library.py`：理解仿真案例怎么变成结构化数据。
4. 再学 `odb_postprocess.py` 和 `abaqus_batch_client.py`：理解 ODB 结果怎么提取。
5. 再学 `dataset_export.py`：理解训练样本怎么组织。
6. 再学 `streamlit_app.py`：理解产品界面怎么调用后端能力。
7. 最后学 LLM/API/客户端：这时你已经知道 AI 应该控制什么、不该控制什么。

每学一个模块，都要能回答：

- 它输入什么？
- 它输出什么？
- 它解决哪个工程问题？
- 它依赖 Abaqus 吗？
- 它产生哪些文件？
- 这些文件后续被谁使用？
- 失败时怎么排查？

## 15. 当前最推荐的下一步

下一步建议做：

```text
批量样本扩充与任务队列 v0
```

非常细的执行顺序：

1. 设计一张最小参数扫描表。
2. 支持从参数表生成多个 Abaqus job 输入。
3. 支持 job 队列状态记录。
4. 支持失败/完成状态汇总。
5. 自动扫描每个 job 的 ODB。
6. 自动提取最后一帧结果和帧曲线。
7. 自动写入案例库或批量结果库。
8. 重新导出训练数据集。
9. 重新训练代理模型。
10. 用多样本评估代理模型误差。

代理模型 v0 已经完成后，我们现在真正拥有：

```text
Abaqus 案例 -> 特征提取 -> 数据集 -> 神经网络/代理模型 -> 误差报告
```

这就是有限元 + AI 项目最关键的一条主线。

最小闭环验证案例已经形成 v0，案例主题仍然保留为后续公开 demo：

```text
薄板单轴拉伸材料本构代理模型闭环验证
```

详细设计见：

```text
docs/MINIMUM_CLOSED_LOOP_CASE_CN.md
```

这个案例要证明：

```text
材料输入
-> 模型训练
-> Abaqus 验算
-> ODB 后处理
-> 案例库归档
-> 数据集导出
-> 代理模型训练
-> 闭环报告
```
