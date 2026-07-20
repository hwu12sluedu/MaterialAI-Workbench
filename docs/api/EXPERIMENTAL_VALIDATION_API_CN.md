# CFRP 验证协议审计 API

模块：`material_ai_workbench.experimental_validation`

## 公开入口

```python
from material_ai_workbench import run_cfrp_validation_audit

result = run_cfrp_validation_audit(
    targets=("flexural_strength_mpa",),
    models=("mean", "ridge", "random_forest", "svr"),
    random_state=42,
    rf_estimators=100,
)

print(result.run_dir)
print(result.summary["release_gate_protocol"])
```

函数签名：

```python
run_cfrp_validation_audit(
    dataset_dir=DEFAULT_DATASET_DIR,
    *,
    output_root=DEFAULT_OUTPUT_ROOT,
    targets=None,
    models=DEFAULT_MODELS,
    random_state=42,
    rf_estimators=100,
) -> ExperimentalValidationAudit
```

## 参数

| 参数 | 含义 |
|---|---|
| `dataset_dir` | `materialai-cfrp-data` 生成的数据版本目录 |
| `output_root` | 审计运行目录根路径 |
| `targets` | 一个或多个受支持目标；`None` 表示全部 |
| `models` | `mean`、`ridge`、`random_forest`、`svr` 的子集 |
| `random_state` | 确定性随机种子 |
| `rf_estimators` | Random Forest 树数量，最少为 10 |

## 返回对象

`ExperimentalValidationAudit` 包含：

| 字段 | 内容 |
|---|---|
| `run_dir` | 本次审计根目录 |
| `manifest_json` | 输入、配置、运行环境与产物哈希 |
| `summary_json` | 面向程序读取的结论摘要 |
| `comparison_csv` | 四种协议的指标对比 |
| `predictions_csv` | 全部 OOF 预测和重复泄漏标记 |
| `duplicate_clusters_csv` | 完全重复簇清单 |
| `report_md` | 中文审计报告 |
| `figure_paths` | 每个目标的协议敏感性图 |
| `summary` | 已解析的摘要字典 |

## 固定协议

公开常量 `PROTOCOLS` 定义四种协议：

```python
from material_ai_workbench.experimental_validation import PROTOCOLS

for protocol in PROTOCOLS:
    print(protocol["id"], protocol["split_strategy"])
```

`grouped_raw` 是发布门槛。`row_loocv_raw` 和 `row_loocv_deduplicated` 只用于解释论文式逐行验证，不作为新材料泛化证据。

## CLI

```powershell
conda run -n pylabfea materialai-cfrp-validation-audit `
  --target flexural_strength_mpa `
  --model ridge `
  --rf-estimators 100
```

成功时标准输出是 JSON，状态为 `completed_with_warnings`，因为小样本、源单位和协议可比性限制始终需要保留。输入目录不存在、哈希不匹配、目标非法或树数量小于 10 时，命令返回退出码 `2`，错误 JSON 写入标准错误。

## 产物契约

`predictions.csv` 的关键字段：

- `protocol`：当前验证协议；
- `sample_id`：稳定样本标识；
- `truth`、`prediction`、`residual`：真实值、OOF 预测和残差；
- `duplicate_cluster_id`：所属完全重复簇；
- `exact_duplicate_in_training`：测试该样本时训练集是否有相同副本。

`protocol_comparison.csv` 的关键字段：

- `mae`、`rmse`、`r2`：当前协议 OOF 指标；
- `duplicate_leakage_sample_count`：存在完全相同训练副本的测试记录数；
- `mae_reduction_vs_grouped_raw_pct`：相对严格原始协议的表观 MAE 降低；
- `r2_gain_vs_grouped_raw`：相对严格原始协议的 R2 增量；
- `dedup_mae_change_pct`：去重前后 MAE 的变化。

## 稳定性边界

只有 `run_cfrp_validation_audit`、`ExperimentalValidationAudit` 和 `PROTOCOLS` 是本模块公开 API。以下划线开头的折构造、指标和报告函数属于内部实现，不应由客户端直接调用。
