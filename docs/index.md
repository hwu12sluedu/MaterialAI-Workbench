# MaterialAI Workbench 中文文档

MaterialAI Workbench 是面向材料与仿真工程师的本地工作台。它由两层组成：

1. `pyLabFEA`：材料模型、轻量有限元、等效应力、机器学习屈服函数与均匀化教学内核。
2. `material_ai_workbench`：Windows 客户端、Abaqus 工作流、案例库、数据导入、后处理和代理模型。

当前 Alpha 版本新增案例包 v2、训练质量门、可解释相似案例、历史案例约束的自然语言计划，以及 3D 带孔板批量 Abaqus/代理模型流水线。参见 [v0.4 案例智能与批量仿真](V04_CASE_INTELLIGENCE_CN.md)。

![MaterialAI Workbench 客户端](assets/materialai-workbench-app.png)

## 按使用目的进入

### 直接使用客户端

- [Windows 客户端使用与排错](DESKTOP_CLIENT_CN.md)
- [功能边界与验收说明](CAPABILITY_BOUNDARIES_CN.md)
- [Abaqus MCP 使用指南](ABAQUS_MCP_WORKBENCH_CN.md)
- [案例库使用指南](CASE_LIBRARY_USER_GUIDE_CN.md)
- [v0.4 案例智能与批量仿真](V04_CASE_INTELLIGENCE_CN.md)

### 理解材料与仿真流程

- [产品与复合材料闭环](PRODUCT_COMPOSITE_ML_WORKBENCH_CN.md)
- [技术架构](TECHNICAL_ARCHITECTURE_CN.md)
- [最小闭环案例](MINIMUM_CLOSED_LOOP_CASE_CN.md)
- [pyLabFEA 学习总览](PYLABFEA_NOTEBOOK_STUDY_GUIDE_CN.md)

### 学源码和 API

- [教学入口](learning/README_CN.md)
- [pyLabFEA Notebook 与源码精读](learning/PYLABFEA_NOTEBOOK_SOURCE_WALKTHROUGH_CN.md)
- [从 pyLabFEA 到有限元深度学习](learning/PYLABFEA_TO_FE_DEEP_LEARNING_TUTORIAL_CN.md)
- [API 入口](api/README_CN.md)
- [源码开发与 Windows 打包](DEVELOPMENT_CN.md)

## 文档原则

- 区分已实现代码、需要本机 Abaqus 验证的功能和研究路线。
- 不把生成脚本写成真实求解结果。
- 不把小样本模型指标写成工业泛化精度。
- 教学文档保留 pyLabFEA notebook 和底层代码解释，用户文档只说明可直接操作的流程。

本地预览：

```powershell
conda run -n pylabfea mkdocs serve
```
