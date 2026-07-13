# 从 pyLabFEA 到有限元深度学习模型

这是一条闭环教程路线，目标是让你最终能独立做出“仿真数据 -> AI 模型 -> Abaqus 验证 -> 工程报告”的项目。

## 0. 准备

在项目根目录运行：

```powershell
cd D:\githubproject\pyLabFEA
conda run -n pylabfea python -c "import pylabfea as fea; print(fea.__version__)"
conda run -n pylabfea python -m pytest tests -q
```

注意：本机建议使用 `conda run -n pylabfea ...`，不要直接调用环境里的 `python.exe`，避免底层 native 库加载问题。

## 1. pyLabFEA notebook 学习地图

| 顺序 | Notebook | 你要学会什么 | 对应产品能力 |
|---:|---|---|---|
| 1 | `pyLabFEA_Introduction.ipynb` | 最小有限元流程：几何、材料、边界、网格、求解、后处理 | 理解 App 为什么需要材料、模型、边界、结果 |
| 2 | `pyLabFEA_Equiv-Stress.ipynb` | Mises/Tresca/Hill 等效应力和屈服判断 | 理解 SVM 学的是屈服边界 |
| 3 | `pyLabFEA_Plasticity.ipynb` | 弹塑性、硬化、非线性迭代、各向异性 | 连接真实材料曲线和 Abaqus 验证 |
| 4 | `pyLabFEA_ML-FlowRule-Training.ipynb` | 如何生成应力空间训练样本 | 连接 `pipeline.py` 的训练数据生成 |
| 5 | `pyLabFEA_ML-FlowRule-Hill.ipynb` | Hill 各向异性屈服与 ML flow rule | 当前 Hill demo 的理论基础 |
| 6 | `pyLabFEA_ML-FlowRule-Tresca.ipynb` | 非光滑屈服面与 ML 拟合 | 后续材料模型扩展 |
| 7 | `pyLabFEA_Composites.ipynb` | 复合材料微观力学 | RVE 和等效材料参数 |
| 8 | `pyLabFEA_Homogenization.ipynb` | 多相材料均匀化、Taylor/Sachs 模型 | 复合材料多尺度建模 |

## 2. 每个 notebook 的统一学习方法

每个 notebook 都按以下步骤学：

1. 先运行全部单元。
2. 把每个输入参数写成中文含义。
3. 把每张图解释成工程结论。
4. 找到它调用的 `pylabfea` 函数或类。
5. 在 `docs/api/API_INVENTORY_AUTOGEN_CN.md` 中查对应 API。
6. 回答“这个 notebook 的思路如何产品化到 App 中”。

## 3. 源码模块导读

### `src/pylabfea/basic.py`

核心作用：应力、应变、主应力、偏应力、等效应力、坐标变换。

必须掌握：

- `sig_eq_j2`：J2/Mises 等效应力。
- `sig_princ`：主应力。
- `sig_dev`：偏应力。
- `eps_eq`：等效应变。
- `Stress`、`Strain`：把应力/应变封装成对象。

对应工程问题：

- 为什么屈服面能从 6 维应力空间降维显示？
- 为什么 Abaqus 里 Mises 是关键场变量？

### `src/pylabfea/material.py`

核心作用：材料定义、屈服函数、塑性响应、机器学习屈服模型。

必须掌握：

- `Material` 如何定义弹性、塑性和各向异性。
- J2/Hill/Barlat 类模型在代码中的关系。
- SVC/SVR 模型如何被训练为屈服函数。
- 模型如何导出给 Abaqus UMAT。

对应工程问题：

- 当前 App 的 J2 和 Hill 参数如何变成训练样本？
- 后续怎样扩展到 Barlat、Swift/Voce、实验曲线？

### `src/pylabfea/model.py`

核心作用：轻量 FE 模型，包含节点、单元、section、边界、求解。

必须掌握：

- 模型几何如何建立。
- 材料如何分配到区域。
- 边界条件如何施加。
- 结果如何后处理。

对应工程问题：

- pyLabFEA 小模型和 Abaqus 大模型的概念如何对应？

### `src/pylabfea/training.py`

核心作用：生成机器学习屈服函数训练样本。

必须掌握：

- 6 维应力空间采样。
- 训练样本覆盖为什么重要。
- `training_score` 如何评价模型。

对应工程问题：

- 为什么只用单轴拉伸曲线训练不出完整屈服面？

## 4. MaterialAI Workbench 源码导读

### `pipeline.py`

主线：材料参数 -> pyLabFEA 材料对象 -> 训练数据 -> SVC 屈服模型 -> 图和报告 -> Abaqus UMAT 文件。

运行：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name doc_j2 --with-curves
```

看输出：

```text
material_ai_workbench/runs/<run_name>/summary.json
material_ai_workbench/runs/<run_name>/reports/material_model_report.md
material_ai_workbench/runs/<run_name>/models/
```

### `abaqus_bridge.py`

主线：把训练出的模型复制到 Abaqus 验证目录，调用 Abaqus，读取 CSV/ODB，生成验证报告。

运行：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<run_name> --max-load-cases 1 --run
```

### `case_library.py`

主线：把日常 Abaqus 案例变成结构化资产。

它提取：

- INP：材料、step、单元类型、节点/单元数量估算、载荷、边界、输出请求。
- CSV：Mises、PEEQ、位移、反力等候选指标。
- 日志：warning/error 数量。
- ODB：路径、后处理记录。

### `odb_postprocess.py` 与 `abaqus_batch_client.py`

主线：通过 SMAPython 或 MCP 读取 ODB。

必须知道：

- 普通 Python 不能直接 `import odbAccess`。
- ODB 读取要用 Abaqus 自带 SMAPython。
- 大批量读取要避免界面冻结，优先短脚本和批处理。

### `dataset_export.py`

主线：把案例库合成为机器学习数据集。

输出：

- `case_dataset.csv`
- `frame_series_index.csv`
- `dataset_manifest.json`
- `dataset_report.md`

### `surrogate_model.py`

主线：读取数据集，训练代理模型。

当前支持：

- RandomForest baseline。
- MLP baseline。
- holdout / 小样本评估。
- 预测图、指标、模型文件、报告。

必须理解：

- 样本量少时，模型只能证明流程。
- 代理模型必须和 Abaqus 验证结果绑定。
- 误差报告比“训练成功”更重要。

## 5. 从表格代理模型走向有限元深度学习

### 5.1 表格代理模型

输入：

- 材料参数。
- INP 结构特征。
- ODB 统计特征。

输出：

- Max Mises。
- Max U。
- Max PEEQ。
- 反力峰值。

适合：

- 早期闭环。
- 小样本验证。
- 工程可解释。

### 5.2 时间序列模型

输入：

- 每帧 S/PEEQ/U/RF 统计。

输出：

- 整条载荷-位移曲线。
- 整条应力-应变曲线。

适合：

- 非线性过程预测。
- 失稳或塑性演化。

### 5.3 RVE 图像/体素 CNN

输入：

- RVE 相分布图。
- 体素结构。
- 材料相参数。

输出：

- 等效 E/G/nu。
- 各向异性刚度矩阵。
- 强度或失效指标。

适合：

- 复合材料。
- 多孔材料。
- 微结构敏感性能。

### 5.4 迁移学习

输入：

- 历史案例大数据集。
- 新材料少量样本。

输出：

- 微调后的新材料预测模型。

适合：

- 你每天积累 Abaqus 案例后的长期产品形态。

## 6. 最小复合材料闭环实战

推荐题目：随机纤维 RVE 等效弹性预测。

步骤：

1. Python 生成随机纤维分布。
2. 计算纤维体积分数。
3. Abaqus 生成 2D RVE 模型。
4. 运行 E11、E22、G12 三类载荷。
5. 从 ODB 提取平均应力和平均应变。
6. 计算等效 E11、E22、G12、nu12。
7. 导出数据集。
8. 训练 MLP baseline。
9. 把体素图加入 CNN baseline。
10. 写闭环报告。

最终你要能解释：

- RVE 代表什么。
- 周期性边界为什么重要。
- 为什么 CNN 比纯表格模型更适合微结构图像。
- 为什么 Abaqus 验证是模型可信度的底线。
