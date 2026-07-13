# GitHub 发布清单

## 1. 仓库准备

- [ ] 仓库是干净 Git 工作树。
- [ ] README 第一屏说明项目价值：材料本构训练 + Abaqus 验证 + 案例库 + 代理模型。
- [ ] LICENSE 清楚。
- [ ] `pyproject.toml` 能安装。
- [ ] `environment.yml` 能创建环境。
- [ ] `.gitignore` 覆盖运行数据和大文件。

## 2. 功能验收

- [ ] J2 训练能运行。
- [ ] Hill 训练能运行。
- [ ] CSV 导入能运行。
- [ ] 案例库能录入 `.inp`。
- [ ] ODB 后处理有可选集成测试说明。
- [ ] 数据集导出能运行。
- [ ] RandomForest 代理模型能运行。
- [ ] MLP 代理模型能运行。
- [ ] 闭环报告能生成。
- [ ] Streamlit App 能启动。

## 3. Abaqus 验收

- [ ] Abaqus 路径配置不写死在公开代码里。
- [ ] SMAPython 路径可配置。
- [ ] 没有 Abaqus 时，非 Abaqus 测试仍能通过。
- [ ] 有 Abaqus 时，最小 UMAT 验证能跑。
- [ ] MCP 未启动时，App 给出清晰提示。
- [ ] MCP 启动后，能读取模型/Job/ODB/viewport。

## 4. 文档验收

- [ ] `docs/learning` 能指导初学者从 notebook 学起。
- [ ] `docs/api/API_INVENTORY_AUTOGEN_CN.md` 已刷新。
- [ ] `docs/release` 说明如何重组和发布。
- [ ] `docs/00_project_status` 说明当前能力和边界。
- [ ] 每个核心流程都有可复制命令。
- [ ] 文档明确说明当前 J2/Hill 只是 MVP，不是材料范围上限。

## 5. 数据与隐私

- [ ] 不包含真实客户项目。
- [ ] 不包含公司内部文件。
- [ ] 不包含 API Key。
- [ ] 不包含个人绝对路径作为默认配置。
- [ ] 大型 ODB/CAE 不进入 Git。
- [ ] demo 数据体积可接受。

## 6. 发布包

- [ ] 打 tag：`v0.1.0-mvp`。
- [ ] Release notes 包含功能、已知限制、运行方式。
- [ ] 附上小型 demo 数据包。
- [ ] 附上截图。
- [ ] 附上 5 分钟演示脚本。

## 7. 简历材料

项目描述建议：

```text
MaterialAI Workbench：基于 pyLabFEA、Abaqus 与机器学习构建本地 CAE+AI 工作台，实现材料屈服模型训练、Abaqus UMAT 验证、仿真案例库、ODB/CSV 后处理、批量仿真数据集生成和有限元代理模型训练；已完成 J2/Hill 材料训练、Abaqus 闭环验证、5 样本批量仿真、RandomForest/MLP baseline，并规划复合材料 RVE、多尺度建模和自然语言 Abaqus 任务编排。
```

面试时要能讲清：

1. 为什么选择 pyLabFEA 作为学习和原型基础。
2. SVM 屈服模型和神经网络代理模型的区别。
3. 为什么必须用 Abaqus 做真实验证。
4. 案例库为什么能成为训练数据资产。
5. 当前模型精度为什么不能夸大。
6. 下一步如何从 J2/Hill 扩展到复合材料 RVE。
