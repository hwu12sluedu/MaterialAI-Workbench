# CFRP 公开实验数据：受控导入与可信划分

这一节完成 MaterialAI Workbench 第一个真实公开实验数据入口。目标不是立刻追求一个好看的 `R2`，而是先保证数据来源、许可、单位、缺失值和训练/测试边界都能复查。

## 1. 数据是什么

数据来自 Alsheghri 等人的 CFRP 性能预测研究：

- 论文 DOI：[`10.1371/journal.pone.0319787`](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0319787)
- 数据 DOI：[`10.17632/fspdwb4mst.1`](https://data.mendeley.com/datasets/fspdwb4mst/1)
- 数据版本：`1`
- 许可：`CC BY-NC 3.0`
- 样本：62 条、9 种 CFRP 类型
- 输入：CNT 体积分数、夹层体积分数、玻璃化转变温度、制造压力
- 输出：弯曲强度、弯曲模量、拉伸强度、II 型能量释放率

这是一份“工艺/结构参数到宏观性能”的小样本表格，不是应力-应变曲线，也不是可直接写入 Abaqus 的本构参数表。

## 2. 为什么不能直接随机切分

同一种 CFRP 类型的试样具有共同的材料体系和制造条件。若把同类试样逐行随机拆到训练集和测试集，模型可能只是在识别同类样本，而不是预测没见过的材料类型。

本工具按 `material_type_id` 生成留一类型验证：每一折完整留出一种 CFRP 类型。弯曲强度和弯曲模量有 9 折；拉伸强度和 II 型能量释放率只有前 5 类有标签，因此各有 5 折。

## 3. 从官方源自动下载

源数据采用非商业许可，所以命令要求显式确认：

```powershell
conda run -n pylabfea materialai-cfrp-data --accept-license
```

程序先查询 Mendeley 官方文件元数据，再核对文件 ID、内容 ID、大小和 SHA-256。任何一项变化都会停止，不会把未知新版本静默混入实验。

## 4. 导入已经下载的文件

```powershell
conda run -n pylabfea materialai-cfrp-data `
  --source-xlsx "D:\data\Dataset_Processing-Structure-Property_CFRPs.xlsx"
```

本地文件也必须匹配版本 1 的官方 SHA-256：

```text
759fe8568ac38a7d45db0aaa65b4aa3d8d9386d46615411e530d375d5f6652e8
```

## 5. 输出目录

默认输出到：

```text
workspace/datasets/alsheghri_2025_cfrp_experiment/v1/
├── raw/
│   └── Dataset_Processing-Structure-Property_CFRPs.xlsx
├── derived/
│   ├── cfrp_experimental_normalized.csv
│   ├── grouped_splits.json
│   └── quality_report.json
├── DATA_CARD_CN.md
└── dataset_manifest.json
```

`raw` 中保存校验后的不可变源文件；`derived` 是可重建结果。Git 忽略整个工作区，不会把第三方原始数据上传到仓库。

## 6. 已发现的数据问题

对官方版本 1 的实际审计结果：

| 检查项 | 结果 | 处理 |
|---|---:|---|
| 总行数 | 62 | 与论文和数据说明一致 |
| 材料类型 | 9 | 生成稳定类型名和样本 ID |
| 输入特征缺失 | 0 | 不填补 |
| 拉伸强度缺失 | 20 | 按目标排除，不删除整行 |
| II 型能量释放率缺失 | 20 | 按目标排除，不删除整行 |
| 额外完全重复行 | 6 | 保留并报告，不擅自去重 |
| 弯曲模量单位 | 源文件标为 MPa | 原样保留，不静默换算 |
| II 型能量释放率单位 | 源文件标为 kJ/m2 | 使用 `reported` 字段名原样保留，待回查试验定义 |

重复值可能来自原始数据组织或重复试样记录。在没有作者级证据前，工具只做告警。训练阶段可另做“保留/去重”敏感性分析，但不能覆盖原始数据。

## 7. 如何检查质量报告

```python
import json
from pathlib import Path

root = Path("workspace/datasets/alsheghri_2025_cfrp_experiment/v1")
quality = json.loads((root / "derived/quality_report.json").read_text(encoding="utf-8"))

print(quality["status"])
print(quality["missing_counts"])
print(quality["duplicate_extra_rows"])
```

状态为 `pass_with_warnings` 是预期结果：文件和结构通过，但小样本、缺失目标、重复记录和单位解释必须进入后续报告。

## 8. 如何检查分组折

```python
import json
from pathlib import Path

root = Path("workspace/datasets/alsheghri_2025_cfrp_experiment/v1")
splits = json.loads((root / "derived/grouped_splits.json").read_text(encoding="utf-8"))
target = splits["targets"]["flexural_strength_mpa"]

for fold in target["folds"]:
    print(fold["fold_id"], fold["train_count"], fold["test_count"])
```

后续训练器必须读取这里保存的样本 ID，不能重新随机拆分。

## 9. 与最终产品的关系

这一数据集提供“公开实验锚点”，用于证明我们的数据治理和机器学习验证方法可信。它与最终有限元神经网络的关系是：

1. 当前数据验证工艺变量到宏观性能的回归流程。
2. Abaqus RVE/PBC 数据将补充微观结构和有效刚度/强度标签。
3. 自己的试验或脱敏工程案例提供最终外部验证。
4. 三类数据不能混为同一精度声明，而应分别显示来源和误差。

下一步是在固定分组折上实现 Mean/Ridge/RF/SVR 基线，保存逐样本预测与不确定性，再决定 MLP 是否真的带来提升。
