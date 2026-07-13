# pyLabFEA Notebook 与源码精读路线

## 1. 为什么还要继续学 pyLabFEA

MaterialAI Workbench 的产品目标是机器学习驱动的有限元工作台，但它的底层学习价值来自 pyLabFEA：

- `Material` 让你理解材料弹性、塑性、屈服函数和 ML flow rule。
- `Model` 让你看到小型有限元求解器如何组装、施加载荷和计算响应。
- `Data` 让你理解材料实验/仿真数据如何变成机器学习样本。
- `training` 让你理解应力空间采样、训练集生成和模型评分。

所以学习顺序不能只看 App，要回到 notebook 和源码，把“按钮背后的算法”吃透。

## 2. Notebook 学习顺序

| 顺序 | Notebook | 你要学会什么 | 对产品的作用 |
|---:|---|---|---|
| 1 | `pyLabFEA_Introduction.ipynb` | 基本材料、模型、求解流程 | 看懂 pyLabFEA 的对象体系 |
| 2 | `pyLabFEA_Equiv-Stress.ipynb` | Mises、Tresca、Hill 等效应力 | 理解 ML 屈服面在学什么 |
| 3 | `pyLabFEA_Plasticity.ipynb` | 弹塑性响应、硬化、应力应变曲线 | 对接实验曲线和 Abaqus 单元验证 |
| 4 | `pyLabFEA_Homogenization.ipynb` | 均匀化思想和微结构响应 | 对接复合材料 RVE 标签生成 |
| 5 | `pyLabFEA_Composites.ipynb` | 复合材料弹性与微观力学 | 对接 Fiber/Interface/Matrix 微观建模 |
| 6 | `pyLabFEA_ML-FlowRule-Training.ipynb` | ML flow rule 训练流程 | 当前材料训练页面的基础 |
| 7 | `pyLabFEA_ML-FlowRule-Hill.ipynb` | Hill 各向异性 ML 屈服 | 当前 Hill demo 的理论来源 |
| 8 | `pyLabFEA_ML-FlowRule-Tresca.ipynb` | Tresca 屈服面学习 | 后续扩展更多屈服准则 |

## 3. 源码阅读顺序

### 3.1 `src/pylabfea/basic.py`

先看张量工具和应力/应变表示。

重点问题：

- Voigt 向量和真实应力张量如何互相转换？
- 等效应力、偏应力、不变量是怎么计算的？
- 为什么机器学习屈服函数需要统一的应力特征表达？

### 3.2 `src/pylabfea/material.py`

这是最重要的文件。

重点入口：

- `Material.elasticity()`：定义弹性刚度。
- `Material.plasticity()`：定义 J2、Hill、Barlat 等塑性参数。
- `Material.create_sig_data()`：生成训练用应力样本。
- `Material.calc_yf()`：计算屈服函数。
- `Material.export_MLparam()`：导出 Abaqus UMAT 可读取的 ML 参数。

对应产品：

- `material_ai_workbench/pipeline.py` 调用材料训练。
- `material_ai_workbench/composite_workflow.py` 用 `Material.elasticity()` 记录三相材料。

### 3.3 `src/pylabfea/model.py`

这是小型有限元求解器。

重点问题：

- 节点、单元、自由度如何编号？
- 单元刚度如何组装到全局刚度？
- 边界条件和载荷如何施加？
- 材料响应如何进入有限元迭代？

对应产品：

- 当前 App 的 Abaqus 验证是工业求解器路线。
- pyLabFEA 的 `Model` 更适合作为教学、快速验证和未来轻量代理数据生成器。

### 3.4 `src/pylabfea/data.py`

重点问题：

- 实验或仿真数据如何标准化？
- 多组曲线如何合成材料训练数据？
- 真实曲线导入后，怎样进入 `Material.from_data()`？

对应产品：

- `material_ai_workbench/data_import.py`
- 后续“真实材料曲线 -> 本构训练 -> Abaqus 验证”的入口。

### 3.5 `src/pylabfea/training.py`

重点问题：

- 应力空间采样如何覆盖屈服面？
- 训练集/测试集如何划分？
- SVM/ML 模型的评分怎么解释？

对应产品：

- 当前 J2/Hill SVC 训练。
- 后续 Barlat、复合材料失效准则和数据驱动屈服面。

## 4. 从 pyLabFEA 到我们产品的映射

```text
pyLabFEA Material
-> 材料相定义、弹性/塑性/ML 屈服

pyLabFEA Data
-> 实验曲线、Abaqus CSV、材料样本标准化

pyLabFEA training
-> 应力空间采样、ML flow rule、模型评分

MaterialAI Workbench
-> Abaqus 自动化、案例库、ODB 特征、复合材料 RVE、代理模型、自然语言客户端
```

## 5. 你每天应该怎么学

1. 先跑 notebook。
2. 找到 notebook 调用的 pyLabFEA 函数。
3. 打开源码读函数输入、输出和核心公式。
4. 在 App 里找到对应页面。
5. 用一个小案例验证它对 Abaqus 或 ML 数据的作用。

## 6. 当前新增复合材料模块如何反哺 pyLabFEA 学习

复合材料模块新增了三类学习材料：

- `pylabfea_material_summary.json`：证明 Fiber/Interface/Matrix 已经映射到 pyLabFEA 材料对象。
- `phase_map.csv`：未来 CNN/3D CNN 的结构输入。
- `composite_dataset.csv`：复合材料参数扫描形成的机器学习表格数据。

这让 pyLabFEA 不只是“学材料模型”，而是变成整个材料 AI 产品的底层语言。
