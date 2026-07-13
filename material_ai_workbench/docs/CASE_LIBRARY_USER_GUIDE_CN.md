# 案例库使用指南

## 概述

案例库是 MaterialAI Workbench 的仿真资产管理系统。它索引你每天的 Abaqus 仿真文件夹，提取结构特征、结果信号和 ODB 后处理数据，但不复制大型 `.cae` 或 `.odb` 文件。每个案例沉淀为一个小型、可追溯的结构化资产。

## 添加案例

### 从文件夹添加
1. 打开 Streamlit App → `案例库` 标签页
2. 在"添加案例"区域输入：
   - **来源文件夹路径**：Abaqus 仿真文件夹的完整路径
   - **标题**：案例名称（可选，默认使用文件夹名）
   - **标签**：逗号分隔的标签，如 `J2, 单元验算, 2024Q1`
3. 点击"扫描并归档案例"

### 从单个 INP 文件添加
- 在来源路径中输入完整的 `.inp` 文件路径
- 系统会自动将其作为独立案例索引

## 提取的内容

### INP 结构特征
- 节点数估算、单元数估算
- 材料名称列表
- Step 名称和类型
- 单元类型
- 载荷、边界条件、接触/约束关键字
- 输出请求关键字

### 结果文件特征
- **CSV 结果文件**：自动识别列名，提取 Mises/PEEQ/位移/反力候选最大值
- **日志文件**（`.sta`/`.msg`/`.dat`）：提取 warning/error 计数，检测完成/中止状态
- **ODB 文件**：索引路径、大小和时间戳，不复制文件

### 文件自动分类
| 类别 | 扩展名 |
|------|--------|
| 模型 | `.cae`, `.inp`, `.step`, `.stp` |
| 结果 | `.odb`, `.sta`, `.msg`, `.dat` |
| 数据 | `.csv`, `.xlsx`, `.json` |
| 图片 | `.png`, `.jpg`, `.bmp` |
| 报告 | `.pdf`, `.docx`, `.md` |
| 脚本 | `.py`, `.ps1`, `.bat`, `.f` |

## ODB 深度后处理

### 场变量提取
1. 在案例详情中展开"提取 ODB 场变量"
2. 选择要提取的 ODB（从案例文件列表中自动识别）
3. 选择提取方式：
   - **MCP 实时**：需要 Abaqus/CAE 运行中且 Bridge 已启动，可同时抓取云图
   - **批处理**：使用 `SMAPython.exe` 离线读取，不需要 GUI
   - **自动**：优先尝试 MCP，失败则回退到批处理
4. 设置要提取的字段（默认 S/PEEQ/U/RF/CPRESS/COPEN）
5. 点击"提取当前 ODB"或"批量提取全部 ODB"

输出文件：
- `odb_field_summary.json` — 完整的字段统计数据
- `odb_field_summary.csv` — 表格格式的字段统计
- `odb_field_report.md` — 人可读的报告

### 帧曲线提取
1. 展开"提取 ODB 帧曲线"
2. 选择 ODB、字段和可选 named set
3. 可选的 named set 用于提取关键节点/单元集的局部响应曲线
4. 点击提取

输出包含每帧的 min/max/mean/max_abs 聚合曲线，可用于：
- 结果趋势检查
- 批量案例对比
- 神经网络代理模型的训练标签

## 导出训练数据集

1. 在案例库主页面点击"导出案例库训练数据集"
2. 选择合适的案例范围
3. 系统生成：
   - `case_dataset.csv` — 每行一个案例，包含 42 个输入特征
   - `frame_series_index.csv` — 帧曲线索引，指向每个案例的 ODB 曲线 CSV
   - `dataset_manifest.json` + `dataset_report.md`

导出后可以在"代理模型"页面训练 RandomForest 或 MLP 预测模型。

## 文件结构

```
cases/
└── <case_id>/
    ├── case_summary.json      # 机器可读的完整案例元数据
    ├── case_report.md         # 人可读的报告
    ├── odb_extractions/       # ODB 场变量提取结果
    │   └── <timestamp>_<odb_name>/
    │       ├── odb_field_summary.json
    │       ├── odb_field_summary.csv
    │       └── odb_field_report.md
    └── odb_frame_series/      # ODB 帧曲线提取结果
        └── <timestamp>_<odb_name>/
            ├── odb_frame_series.json
            ├── odb_frame_series.csv
            └── odb_frame_series_report.md
```

## 注意事项

- 案例库**不复制**大型二进制文件（`.odb`/`.cae`），只索引元数据
- 删除案例仅删除索引文件，不影响原始仿真数据
- ODB 提取需要 `SMAPython.exe` 或 MCP Bridge 正常运行
- 帧曲线提取时，大型 ODB 的单帧提取可能需要数分钟
