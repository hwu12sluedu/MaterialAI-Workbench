# v0.4 案例智能与 3D 带孔板批量仿真

## 1. 本版本解决什么问题

v0.4 把每天完成的 Abaqus 案例从“文件夹”升级为可追溯的数据资产，并把以下链路接起来：

```text
INP/CAE + STA/MSG/DAT + ODB/CSV
-> 案例包 v2
-> 求解与数据质量门
-> 可解释相似案例检索
-> 自然语言差异计划
-> 3D 带孔板批量真实求解
-> ODB 特征与训练白名单
-> RF / MLP / GBR 代理模型
```

关键原则：人工填写的 `success` 只是一条备注。系统必须找到完成日志、ODB、显式单位、材料、网格和数值结果，案例才可作为机器学习真值。

## 2. 案例包 v2

导入案例后，案例目录中同时生成：

```text
case_summary.json     内部兼容摘要
case_package.json     稳定公开契约 v2
case_report.md        人工阅读报告
```

`case_package.json` 包含：

- 来源模式、文件数量和案例指纹。
- 每个文件的 SHA256 指纹；大于 64 MiB 的文件只读取大小、首尾各 1 MiB，避免完整扫描大型 ODB。
- Abaqus 版本、Job 名称和证据状态。
- 显式单位制、材料、几何、载荷、网格和结果标签。
- 数据来源、质量分、阻断原因和建议动作。

JSON Schema 位于 `schemas/case_package.schema.json`。

## 3. 质量门

| 检查 | 训练要求 |
|---|---|
| 模型输入 | 至少有可解析 INP，或可识别的模型输入 |
| 单位 | 已声明单位系统、长度、力和应力单位 |
| 材料 | INP 或参数中能识别材料/本构类型 |
| 网格 | 能获得节点数和单元数 |
| 求解 | 完成日志与匹配 ODB 同时存在，且没有 fatal/abort 证据 |
| 结果 | CSV 或 ODB 提取中有数值目标，例如 Max Mises |
| 血缘 | 有源文件案例指纹 |

`.dat` 中普通的 `error estimate` 不等于求解错误。真正的 `***ERROR`、Job aborted、analysis terminated 等才作为失败证据。

## 4. 在客户端导入案例

1. 打开 `案例库`。
2. 选择一个案例文件夹，或选择单个 `.inp`。
3. 明确选择 Abaqus 单位制和版本。
4. 点击 `扫描并归档案例`。
5. 检查“执行状态”“质量分”“可训练”和“案例质量体检”。
6. 对不合格案例按建议补充 STA/ODB、单位或 ODB 数值提取。

训练导出默认勾选“仅导出质量门合格案例”。被排除案例不会消失，原因保存在 `dataset_manifest.json`。

## 5. 命令行导入与检查

源码环境安装后可使用：

```powershell
materialai-case import "D:\cases\plate_hole_001" `
  --title "S355 带孔板拉伸" `
  --tags "plate-hole,S355,tension" `
  --units "mm-N-s-MPa" `
  --solver-version "2024"

materialai-case list
materialai-case inspect <case-id>
materialai-case search <case-id> --top-k 5
materialai-case export --name plate_hole_training
```

最后一条命令默认只导出可训练案例；增加 `--all-cases` 才导出全部案例用于审计。

## 6. 可解释相似案例

相似度由材料、几何、载荷与边界、网格、单位、结果、文本与标签共同计算。页面会同时显示：

- 分项得分和实际权重。
- 匹配特征，例如材料类型、孔半径、单元类型。
- 差异特征，例如加载位移或网格数量。
- 候选案例的执行状态和训练资格。

质量分只轻量影响排序，不能让一个不相关但“质量高”的案例排到工程上真正相似的案例前面。

## 7. 自然语言引用历史案例

在 `仿真任务` 中勾选“参考本地历史案例库”后：

1. 本地先检索最多 3 个案例。
2. 发送给外部 LLM 的上下文不包含 `case_dir`、`source_folder` 等本地路径。
3. LLM 只能引用检索结果中的 Case ID；虚构 ID 会被本地代码删除。
4. LLM 返回 `case_based_simulation` 和参数差异表。
5. `submit_job` 被强制改为 `false`。
6. 点击执行只生成复用工作区，不启动 Abaqus。

复用工作区包含：

```text
inputs/                    复制的 INP/CAE/子程序等可编辑输入
case_plan_manifest.json    引用案例、差异和安全状态
CHANGE_REVIEW_CN.md        提交前人工审查单
```

当前版本不会尝试对任意 INP 几何做不可靠的字符串替换。工程师应在复制模型中实施差异并复核，再到 Job 页面单独确认提交。

## 8. 3D 带孔板批量流水线

客户端打开 `带孔板批量`，输入孔半径、屈服强度和加载位移列表。总样本数是三者笛卡尔积。

推荐周末执行顺序：

1. 创建 `4,5,6 mm × 250,300,350 MPa × 0.25,0.35 mm`，共 18 个样本。
2. “本次样本数”设为 1，点击 `批量准备脚本`。
3. 检查 `acceptance_config.json`、`build_plate_hole.py` 和诊断报告。
4. 勾选确认，只真实求解 1 个样本。
5. 检查 ODB、云图、Max Mises、位移、反力、PEEQ 和案例质量门。
6. 再放量到 4 个样本，确认 Job 命名和恢复逻辑。
7. 最后运行剩余样本，并更新数据集。
8. 至少 4 个合格案例后再勾选代理模型训练；18 个样本仍属于小样本工程实验。

PowerShell 中逗号列表必须加引号：

```powershell
materialai-plate-hole-batch create `
  --name weekend_plate_hole `
  --hole-radii "4,5,6" `
  --yield-strengths "250,300,350" `
  --displacements "0.25,0.35"

materialai-plate-hole-batch run <plan-dir> --max-samples 1
materialai-plate-hole-batch run <plan-dir> --execute --submit-jobs `
  --max-samples 1 --export-dataset
materialai-plate-hole-batch run <plan-dir> --export-dataset --train-models --max-samples 0
```

只有同时出现 `--execute --submit-jobs` 才允许提交 Abaqus。

## 9. 代理模型治理

- 默认目标是 `abaqus_max_mises`。
- 数据集显式过滤 `training_eligible=False` 的案例。
- 同一训练集出现多个单位制时直接拒绝训练。
- 质量分、执行状态、文件指纹等治理字段不会作为模型特征。
- 同数据集训练 Random Forest、MLP Neural Network 和 Gradient Boosting。
- 少于 4 个合格样本时阻止批量模型比较。
- 报告必须说明样本数、评估方式、MAE、RMSE、R2 和质量限制。

## 10. 状态含义

| 状态 | 含义 |
|---|---|
| `pending` | 尚未处理 |
| `prepared` | 仅生成配置和脚本 |
| `built` | 已生成 CAE/INP，未证明求解 |
| `solved` | 有真实 ODB 求解证据 |
| `postprocessed` | 已提取 ODB 数值结果 |
| `validated` | 自动工程合理性检查完成 |
| `archived` | 已进入案例库并可接受质量门检查 |
| `failed/blocked` | 失败或环境阻断，可修复后恢复 |

任何页面、报告或简历描述都不应把 `prepared` 或 `built` 写成“已完成 Abaqus 验证”。
