# pyLabFEA 学习记录与路线

## 当前状态

- 项目位置：`D:\githubproject\pyLabFEA`
- 环境名称：`pylabfea`
- Python：3.12.13
- pyLabFEA：4.4.2
- 安装方式：基于 `environment.yml` 创建 conda 环境，并在该环境中安装本地源码
- 验证结果：官方测试 `pytest tests -v` 通过，11 passed
- 注意事项：测试过程中出现大量 `ComplexWarning: Casting complex values to real discards the imaginary part`，但官方测试通过。后续学习 `basic.py` 中主应力/特征值计算时再回看这个 warning。
- 兼容性修复：新版 Matplotlib 中 `plt.cm.get_cmap(...)` 不再可用，已将源码里的相关调用改为 `plt.get_cmap(...)`，并重新以 editable 模式安装。
- 第一份执行产物：`_learning_runs/pyLabFEA_Introduction_executed.ipynb` 已成功生成。
- Jupyter Kernel：已注册 `Python (pylabfea)`，路径为 `D:\Anaconda3\envs\pylabfea\python.exe`。如果 notebook 报 `ModuleNotFoundError: No module named 'pylabfea'`，在 JupyterLab 右上角切换 Kernel 到 `Python (pylabfea)`，然后重新运行 cell。

## 第一阶段目标

目标不是先改项目，而是把 pyLabFEA 作为有限元和机器学习本构的学习沙盘：

1. 看懂最小弹性 FEM 建模流程。
2. 理解等效应力、主应力、偏应力、屈服准则。
3. 理解塑性与线性硬化。
4. 理解 ML flow rule 的训练数据、模型输入输出和评价方式。
5. 最后连接到 Abaqus UMAT 示例。

## 推荐学习顺序

1. `notebooks/pyLabFEA_Introduction.ipynb`
   - 目标：看懂 `Material`、`Model`、几何、网格、边界条件、求解、绘图。
2. `notebooks/pyLabFEA_Equiv-Stress.ipynb`
   - 目标：理解 J2 等效应力、主应力、偏应力，这是后续塑性和屈服面的基础。
3. `notebooks/pyLabFEA_Plasticity.ipynb`
   - 目标：理解弹塑性响应、屈服、硬化和材料响应曲线。
4. `notebooks/pyLabFEA_Homogenization.ipynb`
   - 目标：理解复合/分区材料和宏观等效响应。
5. `notebooks/pyLabFEA_ML-FlowRule-Training.ipynb`
   - 目标：理解用全应力张量数据训练机器学习 flow rule。
6. `examples/UMAT/README.md`
   - 目标：理解训练好的 ML flow rule 如何作为 Abaqus UMAT 使用。

## 每个 notebook 的学习动作

每个示例都按同一套动作走：

1. 原样运行，确认输出。
2. 画出输入、核心对象、输出。
3. 改一个参数，例如材料参数、载荷、网格数量或边界条件。
4. 记录结果变化。
5. 总结这个示例能迁移到 Abaqus 自动化项目的哪一部分。

## 和长期原创项目的连接

pyLabFEA 用来学底层机制和 ML 本构；Abaqus 用来做真实工程仿真。后续原创项目路线：

1. pyLabFEA 学习 FEM、本构、ML flow rule。
2. Abaqus 自动化实现参数化建模、提交 Job、读取 ODB、导出云图和报告。
3. MCP 封装 Abaqus 工具能力。
4. 桌面端 AI Simulation Workbench 管理模型、材料、Job、结果和报告。

项目发布、中文文档和简历包装的总纲见：

- `PROJECT_RELEASE_PLAN_CN.md`
