# pyLabFEA Notebook 中文学习与源码导读计划

## 1. 为什么必须单独整理 notebook 教学

pyLabFEA 的 notebook 是这个项目的理论和源码根基，但它们对初学者不友好：

- 英文说明多，中文解释少。
- 代码偏研究/教学风格，不是产品工程风格。
- 有限元、塑性力学、等效应力、机器学习流动法则混在一起。
- 很多变量名需要结合材料力学背景才能理解。
- notebook 里展示的是“原理实验”，我们 App 里需要把它们改造成“工程流程”。

所以源码教学不能只讲我们新增的 `material_ai_workbench`，还必须专门讲 pyLabFEA 原始 notebook。

## 2. 当前 notebook 清单

| Notebook | 代码单元 | Markdown 单元 | 学习主题 |
|---|---:|---:|---|
| `pyLabFEA_Introduction.ipynb` | 11 | 12 | 有限元最小入门、模型/材料/网格/求解流程 |
| `pyLabFEA_Equiv-Stress.ipynb` | 5 | 6 | 等效应力、屈服函数、应力张量标量化 |
| `pyLabFEA_Plasticity.ipynb` | 13 | 11 | 弹塑性材料、非线性有限元、塑性响应 |
| `pyLabFEA_Composites.ipynb` | 5 | 6 | 复合材料微观力学、线弹性均匀化 |
| `pyLabFEA_Homogenization.ipynb` | 23 | 24 | 非线性材料均匀化、多相材料等效性能 |
| `pyLabFEA_ML-FlowRule-Training.ipynb` | 11 | 10 | 机器学习流动法则训练数据生成 |
| `pyLabFEA_ML-FlowRule-Tresca.ipynb` | 4 | 5 | Tresca 屈服准则与 ML flow rule |
| `pyLabFEA_ML-FlowRule-Hill.ipynb` | 11 | 7 | Hill 各向异性屈服与 ML flow rule |

## 3. 推荐学习顺序

### 第 1 轮：先跑通，不深究

目标：知道每个 notebook 大概在做什么。

顺序：

1. `pyLabFEA_Introduction.ipynb`
2. `pyLabFEA_Equiv-Stress.ipynb`
3. `pyLabFEA_Plasticity.ipynb`
4. `pyLabFEA_ML-FlowRule-Training.ipynb`
5. `pyLabFEA_ML-FlowRule-Hill.ipynb`

暂时跳过：

- `Composites`
- `Homogenization`
- `Tresca`

原因：它们重要，但不是当前 App MVP 的主线。

### 第 2 轮：边读源码边做中文注释

目标：每个关键代码块都能解释：

- 输入是什么。
- 输出是什么。
- 为什么要这样算。
- 对应有限元/材料力学概念是什么。
- 和我们 App 里的哪个模块有关。

### 第 3 轮：把 notebook 思路产品化

目标：把 notebook 里的研究代码变成稳定函数和 App 流程。

例如：

```text
Notebook 里手动生成训练数据
-> pipeline.py 中封装成函数
-> Streamlit 页面输入参数
-> 输出报告和模型文件
```

## 4. 每个 notebook 要输出的中文教学文档

### 4.1 Introduction

输出文档：

```text
docs/notebook_study/01_Introduction_CN.md
```

必须讲清楚：

1. pyLabFEA 的最小有限元流程。
2. 节点、单元、材料、边界、载荷如何组织。
3. notebook 中每段代码对应的有限元步骤。
4. 结果如何解释。
5. 它和 Abaqus 的概念如何对应。

### 4.2 Equivalent Stress

输出文档：

```text
docs/notebook_study/02_Equivalent_Stress_CN.md
```

必须讲清楚：

1. 为什么需要等效应力。
2. Von Mises / Tresca / Hill 等效应力的工程意义。
3. 应力张量如何变成一个标量。
4. 屈服面是什么。
5. 这部分如何连接到 SVM 屈服模型。

### 4.3 Plasticity

输出文档：

```text
docs/notebook_study/03_Plasticity_CN.md
```

必须讲清楚：

1. 弹性、塑性、硬化的区别。
2. 非线性有限元为什么要迭代。
3. pyLabFEA 如何描述弹塑性材料。
4. 应力-应变曲线怎么看。
5. 这部分如何连接到 Abaqus UMAT 验证。

### 4.4 ML FlowRule Training

输出文档：

```text
docs/notebook_study/04_ML_FlowRule_Training_CN.md
```

必须讲清楚：

1. 为什么机器学习可以表示屈服/流动法则。
2. 训练样本如何生成。
3. 输入特征是什么。
4. 标签是什么。
5. SVM/SVC 在这里学到的是什么。
6. 我们的 `pipeline.py` 如何借鉴它。

### 4.5 ML FlowRule Hill

输出文档：

```text
docs/notebook_study/05_ML_FlowRule_Hill_CN.md
```

必须讲清楚：

1. Hill 各向异性是什么。
2. r 值/方向性为什么重要。
3. Hill 屈服面和 J2 有什么不同。
4. notebook 如何生成 Hill 数据。
5. 当前 App 的 Hill demo 做了什么、还没做什么。

### 4.6 Tresca

输出文档：

```text
docs/notebook_study/06_ML_FlowRule_Tresca_CN.md
```

必须讲清楚：

1. Tresca 和 Mises 的区别。
2. Tresca 屈服面为什么有棱角。
3. 机器学习拟合非光滑屈服面的难点。
4. 后续是否值得接入 App。

### 4.7 Composites

输出文档：

```text
docs/notebook_study/07_Composites_CN.md
```

必须讲清楚：

1. 复合材料微观力学。
2. RVE 思路。
3. 等效弹性参数。
4. 和自动化设备结构件/复材零件的潜在关系。

### 4.8 Homogenization

输出文档：

```text
docs/notebook_study/08_Homogenization_CN.md
```

必须讲清楚：

1. 均匀化是什么。
2. 多相材料为什么需要等效性能。
3. 非线性均匀化难在哪里。
4. 未来如何变成“仿真数据生成器”。

## 5. 每篇 notebook 中文导读的统一格式

每篇文档都按这个格式写：

```text
# Notebook 中文导读：标题

## 1. 这个 notebook 解决什么问题
## 2. 你需要先懂哪些概念
## 3. 代码整体流程图
## 4. 每个代码块逐段解释
## 5. 关键变量表
## 6. 输出结果怎么看
## 7. 和 Abaqus/工程仿真的对应关系
## 8. 和 MaterialAI Workbench 的关系
## 9. 常见报错和排查
## 10. 学完后你应该能回答的问题
```

## 6. 当前 App demo 的边界

当前 demo 只有两类材料入口：

1. `j2`：J2 isotropic，各向同性塑性演示。
2. `hill`：Hill anisotropic，各向异性塑性演示。

这不是最终产品的材料范围，只是最小 MVP。

后续可扩展：

- Tresca
- Barlat
- 多线性塑性
- Swift / Voce 硬化
- 实验曲线驱动塑性
- 超弹性
- 黏塑性
- 损伤/失效模型
- 复合材料均匀化模型

## 7. 学习验收标准

学完 pyLabFEA notebook 后，你应该能独立解释：

1. J2/Mises 为什么是各向同性。
2. Hill 为什么能描述板材各向异性。
3. 屈服面是什么。
4. SVM 在屈服模型里学的是什么边界。
5. 应力-应变曲线如何从材料模型得到。
6. pyLabFEA 的小有限元和 Abaqus 大模型是什么关系。
7. 为什么我们要用 Abaqus 做真实验算。
8. 为什么案例库能成为神经网络代理模型的数据来源。
