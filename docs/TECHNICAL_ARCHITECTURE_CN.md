# MaterialAI Workbench 技术架构说明

## 1. 当前架构

当前项目采用本地 Python 原型架构：

```text
Streamlit App
-> 自然语言任务解析层
-> 数据导入与标准化层
-> 案例库与仿真数据资产层
-> 材料训练 pipeline
-> Abaqus UMAT 验算桥接
-> Abaqus MCP 实时连接层
-> 结果文件/报告/材料库
```

核心目标是先把工程闭环跑通，而不是先做漂亮客户端。

## 2. 模块分工

### `material_ai_workbench/pipeline.py`

负责材料 AI 训练闭环：

- 创建 J2 / Hill 参考材料
- 生成训练数据
- 训练 SVC 屈服模型
- 输出训练指标
- 生成屈服面图
- 导出 Abaqus UMAT 可读取的 SVM CSV/JSON
- 生成 Markdown 报告

### `material_ai_workbench/abaqus_bridge.py`

负责把训练结果接到 Abaqus：

- 读取某个 run 的 `summary.json`
- 找到 `models/abq_<material>-svm.csv/json`
- 准备 Abaqus 验算目录
- 复制 `ml_umat.f`、`femBlock.inp`、`calc_properties.py`
- 调用 Abaqus/Standard
- 读取 ODB
- 输出 CSV、曲线图和验算报告

### `material_ai_workbench/abaqus_mcp_client.py`

负责 Streamlit App 和已打开的 Abaqus/CAE 之间的实时连接：

- 直接连接 Abaqus MCP socket bridge，默认 `127.0.0.1:48152`
- 检查 bridge 连接状态
- 在 Abaqus kernel 中执行小段受控 Python
- 设置 Abaqus 工作目录
- 读取模型、材料、部件、step、load、BC、interaction、Job、viewport
- 监控 Job `.sta` / `.msg` 诊断
- 在用户显式确认后提交已有 Job
- 读取 ODB 元数据
- 提取 ODB 最后一帧场变量统计
- 抓取 Abaqus viewport 图片
- 生成 MCP 会话快照和 Markdown 报告

### `material_ai_workbench/material_library.py`

负责材料模板管理：

- 从 `library/materials.json` 读取材料模板
- 保存当前训练参数为模板
- 删除模板
- 把模板加载回训练表单

### `material_ai_workbench/nl_tasks.py`

负责自然语言任务解析 v0：

- 输入自然语言
- 解析材料类型、E、nu、屈服强度、Hill r1-r6
- 解析 SVC 参数
- 判断是否需要 Abaqus 验算
- 输出标准任务 JSON
- 转换为 `WorkbenchConfig`

当前保留规则版解析器，保证无 API Key 时也能运行；同时提供 `task_from_dict`，可以把 LLM 输出的任务 JSON 复用到同一套训练/Abaqus 执行链路。

### `material_ai_workbench/llm_adapter.py`

负责可选 LLM API 接入 v0：

- 支持 OpenAI-compatible `/v1/chat/completions` 风格接口
- 从环境变量或 App 表单读取 `base_url`、`model` 和 API Key 环境变量名
- 不把 API Key 写入项目文件
- 要求 LLM 输出可解析 JSON
- 将自然语言仿真需求转换为 MaterialAI Workbench 任务 JSON
- 默认不联网，只有用户在 App 中显式允许后才调用

### `material_ai_workbench/data_import.py`

负责真实材料曲线和 Abaqus 结果 CSV 的导入：

- 读取实验曲线 CSV
- 读取 Abaqus 批量结果 CSV
- 自动识别应力列和应变列
- 输出标准化曲线 `normalized_curve.csv`
- 生成曲线预览图和导入报告
- 作为后续神经网络代理模型的数据入口

### `material_ai_workbench/case_library.py`

负责把用户每天做的 Abaqus 案例沉淀为可复用资产：

- 选择本地 Abaqus 案例文件夹，或直接录入单个 `.inp` 文件
- 自动识别 `.cae`、`.inp`、`.odb`、`.sta`、`.msg`、`.csv`、`.png`、`.pdf`
- 对 `.inp` 提取节点/单元数量估算、材料、Step、单元类型、载荷、边界、接触和输出关键字
- 对 `.odb` 索引路径元数据，对 `.csv` / 日志提取第一版结果特征
- 保存案例标题、标签、说明、成功经验、失败原因
- 生成 `case_summary.json` 和 `case_report.md`
- 通过 Abaqus MCP 从 ODB 中提取场变量统计和云图截图
- 后续继续补关键节点/单元集曲线
- 支撑相似案例检索、自然语言仿真和神经网络代理模型训练

### `material_ai_workbench/streamlit_app.py`

负责本地可视化 App：

- `AI 任务`
- `材料训练`
- `数据导入`
- `Abaqus MCP`
- `Abaqus 验算`
- `结果浏览`
- `模型管理`
- `案例库`

## 3. 为什么先做任务 JSON

自然语言不能直接控制 Abaqus。正确方式是：

```text
用户自然语言
-> 任务 JSON
-> 用户确认
-> 后端工具函数执行
-> 输出结果和报告
```

这样可以避免 LLM 误操作文件、误提交长时间 job、误改材料参数。

## 4. 后续 LLM API 接入方式

后续建议新增：

```text
material_ai_workbench/llm/
  providers.py
  prompt_templates.py
  task_parser.py
  schemas.py
```

统一接口：

```text
输入：用户自然语言 + 当前材料库摘要 + run 历史摘要
输出：标准任务 JSON + 缺失参数 + 风险提示
```

LLM 只负责解析和规划，不直接执行 Abaqus。实际执行仍然走：

- `run_material_workbench`
- `prepare_abaqus_verification`
- `run_abaqus_verification`

## 4.1 Abaqus MCP 作为后续客户端连通层

后续 AI Abaqus 客户端与 Abaqus/CAE 的实时连通，采用现有 Abaqus MCP，而不是在客户端里重新实现一套直接控制 Abaqus 的桥。

当前按新版 Abaqus MCP 的直连模式设计：客户端通过本地 socket bridge 直接连接已打开的 Abaqus/CAE，不走旧的命令文件轮询队列；短脚本状态检查、模型读取和 viewport 抓取应保持低延迟，并避免 Abaqus 窗口长时间冻结。

目标分层：

```text
桌面客户端 / 本地 Web App
-> 任务编排与用户确认
-> Abaqus MCP 工具层
-> Abaqus/CAE kernel
-> Job / ODB / Viewport / 报告
```

Abaqus MCP 负责：

- 检查 Abaqus/CAE 连接状态
- 在 Abaqus kernel 中执行小段受控 Python
- 设置工作目录
- 提交已有 job
- 查询 job 列表
- 捕获 viewport 图片
- 读取 ODB 元数据
- 生成当前会话快照
- 后续扩展模型、材料、section、step、load、BC、ODB 后处理工具

客户端负责：

- LLM API 配置
- 自然语言任务解析
- 任务 JSON 展示和确认
- 项目、材料、模型、Job 和报告管理
- 调用 MCP，而不是绕开 MCP 直接硬控 Abaqus

当前 MCP 检查方式：

```text
Abaqus/CAE -> Plug-ins -> Abaqus MCP -> Start Socket Bridge
```

如果 Abaqus/CAE 端 socket bridge 未启动，客户端应显示“未连接 Abaqus MCP”，而不是报业务错误。

## 5. 当前已完成与未完成

已完成：

- Streamlit App 原型
- J2 / Hill 材料训练
- SVC 屈服模型
- Abaqus UMAT 单元级验算桥接
- Abaqus MCP 实时连接页面
- MCP 连接检查、工作目录设置、模型/Job 读取、Job 监控、受控 Job 提交、ODB 元数据读取、ODB 场变量统计、viewport 截图和会话快照
- ODB 读取、CSV 输出和曲线图生成
- 材料模板库
- 模型历史管理
- 规则版自然语言任务解析
- CSV 数据导入与标准化预览
- 案例库 v0：扫描 Abaqus 案例文件夹或单个 `.inp`，生成 `case_summary.json` 和 `case_report.md`，并展示 INP 特征摘要、结果特征摘要和 ODB 深度后处理记录

未完成：

- 更完整的真实材料曲线清洗和参数拟合
- 更完整的 Abaqus 批量仿真数据入库
- 关键节点/单元集曲线提取和相似案例检索
- 任务队列
- 神经网络代理模型
- 多 LLM API 接入
- 桌面客户端
- 更完整的 MCP 操作日志和任务队列
- GitHub 发布级文档和测试完善

## 6. 下一阶段建议

下一阶段建议做真实数据入口：

```text
实验曲线 CSV / Abaqus 批量结果 CSV
-> 数据清洗
-> 特征提取
-> 训练/验证材料模型
-> 与 Abaqus 验算结果对比
```

原因是神经网络代理模型需要数据。没有真实或批量仿真数据，直接做神经网络只会变成玩具 demo。
