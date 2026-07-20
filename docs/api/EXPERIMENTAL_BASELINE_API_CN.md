# CFRP 分组基线 API

模块：`material_ai_workbench.experimental_baselines`

## 训练入口

```python
from material_ai_workbench.experimental_baselines import (
    train_cfrp_grouped_baselines,
)

run = train_cfrp_grouped_baselines(
    "workspace/datasets/alsheghri_2025_cfrp_experiment/v1",
    targets=("flexural_strength_mpa",),
    models=("mean", "ridge", "random_forest", "svr"),
    random_state=42,
    interval_coverage=0.90,
    rf_estimators=250,
)

print(run.run_dir)
print(run.summary["targets"]["flexural_strength_mpa"])
```

## 参数

| 参数 | 含义 |
|---|---|
| `dataset_dir` | 受控导入生成的数据版本根目录 |
| `output_root` | 实验输出根目录，默认 `workspace/experiments/cfrp_grouped_baselines` |
| `targets` | `TARGET_COLUMNS` 的子集；默认全部四个目标 |
| `models` | `mean`、`ridge`、`random_forest`、`svr` 的子集 |
| `random_state` | 随机森林随机种子 |
| `interval_coverage` | 分组残差预测区间名义覆盖率，范围 `[0.5, 1.0)` |
| `rf_estimators` | 随机森林树数量，至少 10 |

没有 Mean 时仍可运行单模型实验，但 `mae_improvement_vs_mean_pct` 和 `beats_mean_baseline` 返回空值。

## 返回对象

`ExperimentalBaselineRun` 包含：

| 属性 | 说明 |
|---|---|
| `run_dir` | 当前实验目录 |
| `manifest_json` | 输入哈希、配置、运行库和产物清单 |
| `summary_json` | 按目标组织的模型排名与限制 |
| `comparison_csv` | 模型级汇总指标 |
| `fold_metrics_csv` | 每个材料类型留出折的指标 |
| `predictions_csv` | 逐样本 OOF 预测和区间 |
| `report_md` | 自动生成的中文实验报告 |
| `figure_paths` | 预测图和残差图 |
| `model_paths` | 全量有效样本重训后的模型文件 |
| `summary` | 已解析的汇总字典 |

## 数据与分组校验

```python
from material_ai_workbench.experimental_baselines import (
    load_cfrp_baseline_dataset,
    validate_target_split_contract,
)

bundle = load_cfrp_baseline_dataset(dataset_dir)
folds = validate_target_split_contract(bundle, "flexural_strength_mpa")
```

加载时会检查：

- 数据集 ID、版本字段、特征和目标契约；
- 规范化 CSV 和分组折文件的 SHA-256 与大小；
- 样本 ID 唯一性、有限数值和必需特征；
- 每折训练/测试不相交；
- 测试材料类型不进入训练集；
- 每个有标签样本恰好作为 OOF 测试样本出现一次。

## `predictions.csv` 关键字段

| 字段 | 含义 |
|---|---|
| `fold_id` | 当前样本所属的外层材料类型留出折 |
| `truth` / `prediction` | 实测值与 OOF 预测值 |
| `residual` | `prediction - truth` |
| `prediction_lower` / `prediction_upper` | 嵌套分组残差区间 |
| `interval_covered` | 当前区间是否覆盖真实值 |
| `calibration_sample_count` | 当前外层折内部用于区间校准的 OOF 残差数 |

## 模型文件

模型文件是一个 pickle 字典，包含 `estimator`、`feature_columns`、`target`、单位和训练数据哈希。只加载自己生成或确认可信的 pickle：

```python
import pickle
import numpy as np

with open(model_path, "rb") as handle:
    bundle = pickle.load(handle)

x = np.array([[0.01, 0.08, 120.0, 30.0]])
prediction = bundle["estimator"].predict(x)
```

输入顺序必须与 `bundle["feature_columns"]` 完全一致。模型卡中的 `pickle_sha256` 可用于再次校验文件。

## CLI

```powershell
materialai-cfrp-baseline `
  --dataset-dir workspace/datasets/alsheghri_2025_cfrp_experiment/v1 `
  --target flexural_strength_mpa `
  --model mean `
  --model ridge
```

成功时输出 `status=completed_with_warnings` 的 JSON 和退出码 `0`。文件、哈希、数据契约或训练错误输出 JSON 到标准错误流，并返回退出码 `2`。

## 边界

- 汇总指标只来自固定材料类型 OOF 预测。
- 全量重训模型不能用自己的训练拟合值代替 OOF 指标。
- 该 API 不进行超参数搜索、单位修正或缺失目标填补。
- 模型输出不是本构参数、设计允许值或认证结论。
