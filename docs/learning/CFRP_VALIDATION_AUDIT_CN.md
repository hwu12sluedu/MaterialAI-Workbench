# CFRP 验证协议与重复样本审计

本章回答一个经常被忽略的问题：同一个复合材料机器学习模型，为什么在论文式逐行交叉验证中看起来非常准确，换成真正的“预测一种没有见过的材料”后却可能失效？

## 1. 先区分两种工程问题

### 问题 A：已知材料内插值

训练集中已经包含某种 CFRP 的其他试样，只需要预测同类材料的另一条记录。这与试验数据补点、质量波动估计比较接近。

### 问题 B：未知材料外推

某种材料类型的全部试样都从训练集中移除，再预测该材料。这更接近产品目标：面对一种没有训练过的新配方、新界面或新工艺，模型还能否给出有用预测？

问题 B 明显更难，也是当前项目的发布门槛。

## 2. 四种验证协议

审计模块使用同一组特征、目标和模型运行四种组合：

| 协议 | 数据 | 测试样本如何留出 | 能回答什么 |
|---|---|---|---|
| `grouped_raw` | 原始 | 完整留出一种材料类型 | 新材料类型泛化，当前发布门槛 |
| `grouped_deduplicated` | 完全去重 | 完整留出一种材料类型 | 严格泛化对重复权重的敏感性 |
| `row_loocv_raw` | 原始 | 每次只留出一行 | 已知材料内部插值，论文协议背景 |
| `row_loocv_deduplicated` | 完全去重 | 每次只留出一行 | 去掉完全重复记录后的内部插值 |

这里的“逐行留一”不等于“新材料留一”。当一行进入测试集时，同一材料类型的其他行仍可能在训练集里。

## 3. 什么叫完全重复

本模块只有在下列字段全部完全相等时才判为同一记录：

```text
材料类型
+ 4 个输入特征
+ 4 个目标值（包括缺失状态）
```

`sample_id`、Excel 来源行号和派生名称不参与判断。每个重复簇保留来源行最靠前的一条记录，其他记录只从派生的去重视图中移除，受控原始 CSV 不会被修改。

官方数据共有：

- `62` 条原始记录；
- `6` 个完全重复簇；
- `12` 条属于重复簇的记录；
- 去重后 `56` 条记录。

逐行留一原始协议测试这 12 条记录时，训练集中均存在另一条完全相同记录；整类材料留出协议中不存在这种泄漏，因为副本与测试样本属于同一个被整体留出的材料类型。

## 4. 运行审计

先准备受控数据：

```powershell
conda run -n pylabfea materialai-cfrp-data --accept-license
```

运行全部目标和全部基线模型：

```powershell
conda run -n pylabfea materialai-cfrp-validation-audit
```

只检查弯曲强度：

```powershell
conda run -n pylabfea materialai-cfrp-validation-audit `
  --target flexural_strength_mpa `
  --model ridge `
  --model random_forest
```

默认 Random Forest 使用 100 棵树。审计不做超参数搜索，因此不会把测试折用于选参。

## 5. 真实结果

以下结果来自固定随机种子 `42`、Random Forest `100` 棵树的本地完整运行。

### 每种协议的最小 MAE 模型

| 目标 | 整类留出原始 | 逐行留一原始 | 逐行留一去重 |
|---|---|---|---|
| 弯曲强度 | Ridge：MAE 40.68，R2 0.839 | RF：MAE 18.27，R2 0.964 | RF：MAE 19.84，R2 0.960 |
| 弯曲模量 | Ridge：MAE 4.452，R2 0.697 | Ridge：MAE 2.642，R2 0.871 | Ridge：MAE 2.830，R2 0.843 |
| 拉伸强度 | RF：MAE 5.986，R2 -0.079 | RF：MAE 4.862，R2 0.042 | RF：MAE 5.528，R2 -0.054 |
| Mode-II 断裂能 | Mean：MAE 419.2，R2 -0.603 | SVR：MAE 130.7，R2 0.708 | SVR：MAE 148.7，R2 0.662 |

源数据中弯曲模量和 Mode-II 断裂能的单位标签尚未独立核实，表中保留源标签口径。

### 最重要的观察

以 Mode-II 为例：

```text
Random Forest：
整类材料留出原始 R2 = -0.853
逐行留一原始 R2     =  0.735
逐行留一去重 R2     =  0.684
```

去重后逐行留一仍然很高，因此成绩差异不能只归因于 6 条重复行。更主要的原因是：逐行留一训练集仍包含同一材料类型的其他试样，而整类留出要求模型迁移到一种完全不可见的材料。

这也是为什么不能只拿一张高 R2 图宣称“模型可以预测新型复材”。

## 6. 输出文件

每次运行产生独立、带时间戳的目录：

```text
workspace/experiments/cfrp_validation_audits/<run_id>/
├─ run_manifest.json
├─ summary.json
├─ protocol_comparison.csv
├─ predictions.csv
├─ duplicate_clusters.csv
├─ REPORT_CN.md
└─ figures/
```

- `protocol_comparison.csv`：目标、协议、模型、MAE、RMSE、R2、排名及协议差值。
- `predictions.csv`：每条 OOF 预测以及 `exact_duplicate_in_training` 标记。
- `duplicate_clusters.csv`：重复簇、保留样本、移除样本和来源行。
- `run_manifest.json`：输入哈希、运行环境、配置、产物哈希和限制。

## 7. 源码阅读顺序

1. `run_cfrp_validation_audit()`：组织四种协议和全部产物。
2. `_audit_duplicates()`：构造稳定重复簇和去重视图。
3. `_build_protocol_folds()`：创建分组留出或逐行留一折。
4. `_validate_protocol_folds()`：保证每条有效样本只测试一次。
5. `_evaluate_protocol()`：每一折重新训练并产生 OOF 预测。
6. `_add_protocol_deltas()`：计算相对严格协议的成绩变化。
7. `_render_report()`：把统计结果翻译成工程结论。

## 8. 为什么下一步才适合加神经网络

神经网络必须使用同样的四协议审计。如果只在逐行留一上增加 MLP，它很可能得到漂亮分数，却无法证明能预测新材料。

正确顺序是：

```text
先固定数据和验证协议
-> 再做训练折内部调参
-> 再加入 MLP
-> 比较 MLP 是否在 grouped_raw 上稳定超过简单模型
-> 最后连接 RVE、实验和 Abaqus 结构响应数据
```

## 9. 面试时怎么解释

可以这样说：

> 我没有直接采用随机划分报告高 R2，而是把逐行 LOOCV 与整类材料留出并排评估，并对源数据中的完全重复记录做了敏感性分析。结果表明，部分性能在已知材料内部插值时表现很好，但对全新材料类型的泛化明显下降。因此项目把整类材料留出作为发布门槛，并把高不确定性样本送回 Abaqus 或试验验证。

这比“我训练了一个随机森林，R2 很高”更接近真实工程研发。
