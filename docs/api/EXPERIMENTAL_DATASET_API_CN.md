# CFRP 实验数据 API

模块：`material_ai_workbench.experimental_datasets`

## 一次完成导入

```python
from pathlib import Path

from material_ai_workbench.experimental_datasets import (
    prepare_cfrp_experimental_dataset,
)

result = prepare_cfrp_experimental_dataset(
    source_path=Path(r"D:\data\Dataset_Processing-Structure-Property_CFRPs.xlsx")
)

print(result.normalized_csv)
print(result.quality_report_json)
print(result.split_manifest_json)
```

不提供 `source_path` 时会从官方地址下载，此时必须传入 `accept_license=True`。

## 结果对象

`ExperimentalDatasetResult` 包含：

| 属性 | 含义 |
|---|---|
| `dataset_dir` | 当前数据版本根目录 |
| `source_workbook` | 通过哈希校验的原始 Excel |
| `normalized_csv` | 稳定英文列名的标准化表格 |
| `manifest_json` | 来源、许可、哈希和派生文件清单 |
| `quality_report_json` | 缺失、范围、重复与质量门结果 |
| `split_manifest_json` | 每个目标的材料类型留一折 |
| `data_card_md` | 当前数据版本的中文数据卡 |

`dataset_manifest.json` 的 `columns` 数组逐列保存 `role`、`unit` 和原始字段来源；
带 `reported` 的单位表示只复述源文件标签，尚未做物理单位纠正。

## 分步调用

```python
from material_ai_workbench.experimental_datasets import (
    build_cfrp_quality_report,
    build_grouped_split_manifest,
    read_cfrp_experimental_workbook,
)

rows = read_cfrp_experimental_workbook("source.xlsx")
quality = build_cfrp_quality_report(rows)
splits = build_grouped_split_manifest(rows)
```

`read_cfrp_experimental_workbook` 只接受当前已登记版本的工作表与字段结构。字段漂移、行数变化或材料分组变化会抛出 `ValueError`，要求先审查新版本。

## 安全边界

- 不自动修正源文件单位。
- 不自动删除重复值。
- 不填补缺失目标。
- 不把原始 Excel 打包进 Python 包。
- 不把这份宏观性能表称为材料本构数据。

CLI 成功时返回 `status=prepared` 和退出码 `0`；文件、网络或校验错误返回
`status=error` 的 JSON 到标准错误流，并使用退出码 `2`，方便桌面端稳定接管。
