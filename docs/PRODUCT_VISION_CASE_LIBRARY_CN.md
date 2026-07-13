# MaterialAI Workbench 产品愿景：案例库与仿真数据飞轮

## 1. 最终产品定位

MaterialAI Workbench 的长期目标不是单个材料训练 demo，而是一个面向机械工程师的本地 CAE+AI 工作台：

```text
日常 Abaqus 案例
-> 案例库沉淀
-> 材料本构/仿真数据抽取
-> 神经网络代理模型训练
-> 真实 Abaqus 模型验证
-> 自然语言复用相似案例并自动仿真
```

它要解决的问题是：工程师每天做了很多有价值的 Abaqus 案例，但这些案例通常散落在文件夹、ODB、截图、Excel、PPT 和个人经验里。项目的目标是把这些案例变成可检索、可训练、可复用的工程资产。

## 2. 核心能力闭环

### 材料本构训练

- 支持不同材料本构模型：J2、Hill、Barlat、实验曲线驱动塑性、超弹性、黏塑性、损伤模型等。
- 从实验曲线、Abaqus 批量结果、手动材料参数中生成训练数据。
- 训练传统 ML 模型和神经网络模型。
- 输出可用于 Abaqus 验证的材料参数、UMAT/VUMAT 输入或替代材料模型。

### Abaqus 真实模型验证

- 把训练出的材料模型映射到 Abaqus 真实模型。
- 自动生成或修改材料、section、step、load、BC、output request。
- 批量提交 Abaqus Job。
- 读取 ODB、CSV 和日志。
- 输出云图、曲线、关键指标和报告。

### 批量仿真与数据生产

- 批量改变几何、材料、载荷、边界、接触、网格和工况参数。
- 自动运行多个 Abaqus Job。
- 自动提取每个 Job 的结果特征。
- 形成机器学习训练样本。

### 后处理与特征提取

典型特征包括：

- 最大 Mises 应力
- 最大主应力/最小主应力
- 最大位移
- 接触压力峰值
- 塑性应变 PEEQ
- 反力/刚度/能量
- 疲劳寿命或损伤指标
- 指定路径、指定节点集、指定单元集上的曲线
- 云图截图和报告图

### 案例库管理

每天做过的 Abaqus 案例都可以被收集进案例库：

- 项目背景
- 几何/模型文件
- 材料参数
- 分析步
- 载荷和边界条件
- 接触/约束
- 网格策略
- Job 状态
- ODB/CSV/截图/报告
- 成功经验、失败原因和修复记录
- 适用场景标签

### 自然语言复用

未来用户输入：

```text
帮我做一个类似上次薄板冲压回弹的仿真，但材料换成 6061-T6，厚度 1.5mm。
```

系统应当：

1. 检索相似案例。
2. 生成任务 JSON。
3. 展示材料、几何、载荷、边界、step 和输出请求差异。
4. 经用户确认后调用 Abaqus MCP 执行。
5. 自动后处理、提取特征、生成报告。
6. 把本次结果再次沉淀回案例库。

## 3. 数据飞轮

项目的核心飞轮：

```text
做案例
-> 归档案例
-> 提取特征
-> 训练模型
-> 辅助新仿真
-> 产生更多高质量案例
```

工程价值不只在“AI 能回答问题”，而在于每次真实仿真都会让系统变得更懂你的工作流、更懂你的材料、更懂你的公司常见结构和边界条件。

## 4. 建议数据对象

### Case

一个完整仿真案例。

字段：

- case_id
- title
- description
- tags
- source_project
- created_at
- software
- model_files
- result_files
- report_files
- status
- lessons_learned

### SimulationModel

模型层信息。

- geometry_type
- part_count
- element_type
- mesh_size
- material_names
- contact_pairs
- steps
- loads
- boundary_conditions

### SimulationRun

一次求解运行。

- job_name
- input_file
- odb_file
- status
- wall_time
- warnings
- errors
- solver
- cpu_count

### FeatureSet

从结果中提取出来的机器学习特征。

- scalar_features
- curve_features
- field_features
- image_features
- extraction_script
- extraction_version

### MaterialModel

材料模型资产。

- material_name
- constitutive_type
- elastic_params
- plastic_params
- curve_data
- trained_model_path
- abaqus_mapping
- validation_runs

## 5. 开发路线

### 阶段 A：案例库 v0

- 手动录入案例标题、标签、说明。
- 选择本地 Abaqus 文件夹，或者直接录入单个 `.inp` 文件。
- 自动识别 `.cae`、`.inp`、`.odb`、`.sta`、`.msg`、`.csv`、`.png`、`.pdf`。
- 从 `.inp` 提取节点/单元数量估算、材料、Step、单元类型、载荷、边界、接触和输出关键字。
- 从 `.odb` 索引路径元数据，从 CSV/日志提取第一版结果特征。
- 通过 Abaqus MCP 提取 ODB 场变量统计，并把深度后处理记录回写案例库。
- 生成 `case_summary.json` 和案例报告。

### 阶段 B：Abaqus MCP 后处理

- 从打开的 Abaqus/CAE 中读取模型和 Job。
- 捕获 viewport。
- 读取 ODB 元数据。
- 对指定变量生成云图截图。
- 提取常用标量结果。
- 下一步扩展 named set 曲线和批量 ODB 队列。

### 阶段 C：批量仿真

- 定义参数扫描表。
- 自动生成多个 Job。
- 队列化提交。
- 汇总所有结果。

### 阶段 D：神经网络代理模型

- 从案例库和批量仿真结果生成训练集。
- 训练应力/位移/失效指标预测模型。
- 和真实 Abaqus 结果对比误差。
- 给出可视化误差报告。

### 阶段 E：自然语言仿真

- 检索相似案例。
- 自动生成任务 JSON。
- 用户确认后执行。
- 结果回写案例库。

## 6. 简历表达

可以表达为：

> 构建面向机械工程师的 Abaqus AI 仿真工作台，设计案例库与仿真数据飞轮，将日常 Abaqus 案例自动归档为可检索、可训练、可复用的数据资产；实现材料本构训练、Abaqus 真实模型验证、批量仿真、ODB 后处理、特征提取和自然语言相似案例复用的产品化闭环。
