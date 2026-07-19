# 教学文档入口

目标：让你能从机械/有限元背景出发，真正理解 pyLabFEA、MaterialAI Workbench、Abaqus 验证和有限元深度学习模型，而不是只会运行一个界面。

## 学习闭环

```text
有限元基础
-> pyLabFEA 源码与 notebook
-> 材料屈服与塑性
-> 机器学习屈服函数
-> Abaqus UMAT 验证
-> 案例库与 ODB 后处理
-> 数据集导出
-> 代理模型训练
-> 复合材料 RVE
-> 有限元深度学习模型
```

## 学习顺序

### 第一阶段：跑通与看懂

1. 启动环境。
2. 跑 `pyLabFEA_Introduction.ipynb`。
3. 跑 J2 材料训练。
4. 跑 Hill 材料训练。
5. 看输出报告和图。
6. 跑最小 Abaqus 验算。

命令：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name learn_j2 --with-curves
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material hill --name learn_hill --sy 50 --C 2 --gamma 1 --with-curves
```

验收问题：

- J2 为什么是各向同性？
- Hill 的 r 值为什么影响屈服面？
- SVM 在这里学的是分类边界还是回归曲线？
- Abaqus UMAT 读取的 CSV/JSON 是什么？

### 第二阶段：源码导读

阅读顺序：

1. `src/pylabfea/basic.py`
2. `src/pylabfea/material.py`
3. `src/pylabfea/model.py`
4. `src/pylabfea/training.py`
5. `material_ai_workbench/pipeline.py`
6. `material_ai_workbench/abaqus_bridge.py`
7. `material_ai_workbench/case_library.py`
8. `material_ai_workbench/odb_postprocess.py`
9. `material_ai_workbench/dataset_export.py`
10. `material_ai_workbench/surrogate_model.py`

每读一个文件都要回答：

- 输入是什么？
- 输出是什么？
- 关键对象是什么？
- 对应有限元或材料力学概念是什么？
- 在 App 中由哪个页面调用？
- 能否用一条命令或一个测试复现？

### 第三阶段：Abaqus 闭环

学习目标：

1. 知道 pyLabFEA 训练出的材料模型如何导出。
2. 知道 UMAT、INP、Abaqus Job、ODB 分别是什么。
3. 能从 Abaqus 结果中提取应力、应变、位移、反力、PEEQ。
4. 能把结果变成训练数据。

命令示例：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<run_name> --max-load-cases 1 --run
```

### 第四阶段：代理模型

学习目标：

1. 认识特征和标签。
2. 知道为什么 5 个样本只能验证流程，不能证明模型精度。
3. 会比较 RandomForest 和 MLP。
4. 会解释 MAE、RMSE、R2、相对误差。

命令示例：

```powershell
conda run -n pylabfea python -m material_ai_workbench.closed_loop_report
```

### 第五阶段：复合材料 RVE

学习目标：

1. 知道 RVE 是什么。
2. 知道纤维、基体、界面、周期性边界是什么。
3. 知道等效 E/G/nu 如何从 Abaqus 结果提取。
4. 知道表格 MLP 与体素 CNN 的区别。

最小题目：

```text
随机纤维体积分数 -> Abaqus RVE -> 等效弹性常数 -> MLP/CNN 代理模型
```

## 本目录文档

- `COMPOSITE_SURROGATE_MASTERY_CN.md`：复合材料代理模型八周学习、真实 Abaqus 数据闭环和掌握标准。
- `COMPOSITE_ML_VALIDATION_CN.md`：分类与回归任务、朴素贝叶斯边界、论文/实验基准和五级验证链。
- `PYLABFEA_TO_FE_DEEP_LEARNING_TUTORIAL_CN.md`：完整学习路径。
- `BARLAT_YLD2000_TO_YLD2004_CN.md`：Barlat/Yld2000-2D 到 pyLabFEA Yld2004-18p 的工程映射、限制和测试方法。

## 自动 API 清单

学习源码时先生成 API 清单：

```powershell
conda run -n pylabfea python tools/generate_api_inventory.py
```

输出：

```text
docs/api/API_INVENTORY_CN.md
```
