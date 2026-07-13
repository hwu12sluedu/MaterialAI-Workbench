# 下一阶段生产级开发任务池

原则：以下任务都以“可长期维护、可测试、可发布”为标准，不再按临时 demo 方式推进。

## P0：先把工程骨架稳住

### 1. 源码与运行数据分离

目标：把 `material_ai_workbench` 从“源码 + 工作目录混合”改成清晰分层。

交付：

- 新增 `material_ai_workbench/config.py`，统一读取工作目录。
- 默认运行数据写入 `workspace/material_ai_workbench/`。
- 旧目录兼容读取，但新运行不再写入源码目录。
- `.gitignore` 默认忽略 ODB、CAE、日志、模型权重、运行数据。
- 单元测试覆盖路径迁移。

### 2. App 页面拆分与服务层封装

目标：拆分超大的 `streamlit_app.py`。

交付：

- `material_ai_workbench/pages/`：页面函数。
- `material_ai_workbench/services/`：训练、Abaqus、案例库、代理模型服务。
- `material_ai_workbench/ui/`：通用显示组件。
- 页面层不直接处理文件细节。
- 所有服务可被 CLI、Streamlit、未来 PySide6 客户端复用。

### 3. 标准任务 JSON Schema

目标：自然语言仿真不能直接执行，只能生成可审查任务。

交付：

- `schemas/material_training.schema.json`
- `schemas/abaqus_job.schema.json`
- `schemas/odb_postprocess.schema.json`
- `schemas/batch_simulation.schema.json`
- `schemas/case_query.schema.json`
- `schemas/report_generation.schema.json`
- schema 校验失败时给出中文错误。
- 每个 schema 配一组示例和测试。

### 4. 任务队列与可恢复执行

目标：Abaqus 长任务不能阻塞界面，失败后可恢复。

交付：

- `Task`、`TaskRun`、`TaskEvent` 数据模型。
- 本地 SQLite 任务表。
- 队列状态：pending/running/succeeded/failed/cancelled。
- Abaqus Job 日志尾部监控。
- 失败重试与人工继续。
- App 展示任务进度、日志和产物路径。

## P1：让数据资产真正可训练

### 5. 真实材料曲线导入 v1

目标：从实验或 Abaqus CSV 得到可拟合材料曲线。

交付：

- 工程应力-应变到真应力-真应变转换。
- 塑性应变计算。
- 多曲线合并：温度、应变率、方向。
- 异常点检测、平滑、重采样。
- 输出拟合前后对比图。
- 数据质量报告。

### 6. 本构参数拟合 v1

目标：从真实曲线拟合 Abaqus 可用材料卡。

交付：

- 双线性塑性。
- 多线性塑性。
- Swift/Voce 硬化。
- J2 + 硬化参数导出。
- 拟合误差、残差图、适用范围说明。
- 生成 Abaqus material card 或 include 文件。

### 7. 案例库检索与标签系统

目标：把日常案例从文件堆变成工程知识库。

交付：

- 标签：材料、结构类型、工况、求解器、失效模式、成功/失败原因。
- INP 结构特征向量。
- ODB/CSV 结果特征向量。
- 相似案例检索。
- 案例对比视图。
- 从相似案例生成新任务 JSON。

### 8. ODB 后处理 v1

目标：从“能提取”升级为“可配置、可批量、可复现”。

交付：

- ODB 字段配置文件。
- node set / element set 选择。
- 最后一帧、指定帧、全帧曲线三种模式。
- 云图截图与结果 CSV 绑定。
- 后处理报告模板。
- 单元测试使用 mock ODB 元数据；真实 ODB 作为可选集成测试。

## P2：有限元深度学习模型

### 9. 代理模型实验管理

目标：让每次训练可追溯、可对比、可复现。

交付：

- 数据集版本号。
- 模型版本号。
- 特征列、目标列、随机种子记录。
- holdout、k-fold、leave-one-out。
- MAE/RMSE/R2/相对误差/误差分布。
- 模型卡 `model_card.md`。
- App 中模型对比表。

### 10. 时间序列代理模型

目标：预测整条载荷-位移、应力-应变、PEEQ 曲线，而不是只预测最大值。

交付：

- 从 `frame_series_index.csv` 读取序列。
- 序列对齐、归一化、截断/重采样。
- MLP baseline：预测关键统计量。
- GRU/LSTM baseline：预测曲线。
- 曲线误差指标。
- 曲线预测图和报告。

### 11. 复合材料 RVE 数据生成 v0

目标：建立下一阶段复合材料最小闭环。

交付：

- 2D 随机纤维 RVE 生成器。
- 体积分数、纤维半径、随机种子参数化。
- 基体/纤维材料参数。
- Abaqus INP 生成或脚本建模。
- 单轴/剪切边界条件。
- 等效 E11/E22/G12/nu12 提取。

### 12. RVE 周期性边界与均匀化 v1

目标：从简单边界升级到工程可信的周期性边界。

参考：EasyPBC 与 Spatium。

交付：

- RVE 面/边/角节点识别。
- PBC equation 生成。
- 6 个基本宏观应变工况。
- 等效刚度矩阵计算。
- 与 pyLabFEA Homogenization notebook 的概念对应。
- 最小验证报告。

### 13. 体素/CNN 复合材料代理模型

目标：支持截图资料中的“结构图像/体素 -> 等效性能”路线。

交付：

- RVE 体素化导出。
- 图像/体素数据集 manifest。
- 2D CNN baseline。
- 3D CNN 预留接口。
- 多输出回归：E11/E22/G12/nu12。
- 与 MLP 表格模型对比。

### 14. 迁移学习与领域自适应

目标：利用历史案例，让少量新材料/新结构也能快速建模。

参考：Li et al. 2024 缺口层合板 allowable load space。

交付：

- 预训练模型保存。
- 微调数据集选择。
- 冻结层/学习率/早停配置。
- 新旧域误差对比。
- 训练过程可视化。
- 外推风险提示。

### 15. 物理约束损失与 PINN 风格验证

目标：让模型输出更符合力学常识。

交付：

- 单调性约束。
- 对称性/各向同性/正定性检查。
- 屈服函数凸性检查入口。
- 能量非负/刚度正定约束。
- 物理违规样本报告。

## P3：产品化和客户端

### 16. LLM Provider 层

目标：支持不同 LLM API，同时保证安全和可审查。

交付：

- OpenAI-compatible。
- DeepSeek/通义/Claude/本地模型适配。
- API Key 不入库、不入 Git。
- prompt 模板版本化。
- 调用日志只记录摘要和 token，不记录密钥。
- 所有执行前必须显示任务 JSON 并由用户确认。

### 17. Abaqus MCP 工具扩展

目标：自然语言仿真最终通过现有 MCP 与 Abaqus 实时连通。

交付：

- 读取模型树、part、material、section、step、load、BC、interaction。
- 修改材料参数。
- 修改输出请求。
- 提交已有 job。
- 打开 ODB 并切换场变量。
- viewport 截图。
- 操作日志和回滚提示。

### 18. FastAPI 后端

目标：为桌面客户端和 Streamlit 共用业务能力。

交付：

- `/tasks`
- `/materials`
- `/cases`
- `/datasets`
- `/surrogates`
- `/abaqus`
- OpenAPI 文档。
- 本地鉴权或仅 localhost 绑定。

### 19. PySide6 桌面客户端 v1

目标：从 Streamlit 原型走向真正本地客户端。

交付：

- 项目主页。
- 案例库。
- 材料库。
- Job 队列。
- LLM 设置。
- Abaqus MCP 状态。
- ODB 后处理。
- 报告中心。

### 20. 发布与简历材料

目标：公开发布后别人能理解、运行、信任这个项目。

交付：

- README 重写。
- 安装文档。
- 5 分钟演示脚本。
- 15 分钟面试讲解稿。
- 简历项目描述。
- STAR 问答。
- GitHub Release。
- 小型 demo 数据包。
