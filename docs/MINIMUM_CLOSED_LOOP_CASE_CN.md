# 最小闭环验证案例设计

## 1. 案例题目

建议题目：

```text
薄板单轴拉伸材料本构代理模型闭环验证
```

英文名：

```text
Minimal Closed-Loop Validation: Sheet Tensile Coupon Surrogate
```

当前实现状态：闭环报告 v0 已经跑通，真实输出位于 `material_ai_workbench/closed_loop_reports/<时间戳>_closed_loop_validation/`，其中包含 `closed_loop_validation_report.md` 和 `closed_loop_manifest.json`。当前真实代理模型样本数仍为 1，所以该报告证明产品链路完整，不证明预测精度。

这个题目足够小，但能覆盖我们产品最核心的闭环：

```text
材料参数
-> 训练材料模型
-> 生成 Abaqus 验算
-> 读取 ODB
-> 提取结果特征和帧曲线
-> 归档案例
-> 导出训练数据集
-> 训练代理模型
-> 输出误差报告
```

## 2. 为什么选薄板单轴拉伸

选择原因：

1. 机械工程背景容易理解。
2. 应力-应变结果直观。
3. Abaqus 单元模型可快速求解。
4. 可先做 J2 isotropic，再做 Hill anisotropic。
5. 结果指标明确：Max Mises、Max U、反力、PEEQ。
6. 后续可扩展到不同厚度、不同材料、不同加载方向。
7. 能自然连接真实材料曲线和板材各向异性。

这个案例不是为了复杂，而是为了证明产品闭环真的跑通。

## 3. 当前 MVP 适用范围

当前 App demo 只有：

- J2 isotropic
- Hill anisotropic

所以闭环验证也应该先围绕这两个材料做，不要一开始引入 Barlat、损伤、超弹性或复杂接触。

第一版闭环只做：

```text
小型拉伸算例 + J2/Hill 材料 + ODB 后处理 + 数据集导出 + 代理模型 baseline
```

## 4. 最小闭环输入

### 4.1 材料输入

J2 isotropic：

- Young's modulus: `210000 MPa`
- Poisson's ratio: `0.3`
- Yield stress: `60 MPa`
- SVC C: `1.0`
- SVC gamma: `1.0`

Hill anisotropic：

- Young's modulus: `210000 MPa`
- Poisson's ratio: `0.3`
- Reference yield stress: `60 MPa`
- Hill ratios: 先用当前默认值
- SVC C: `2.0`
- SVC gamma: `1.0`

### 4.2 Abaqus 模型输入

第一版可以继续使用当前 UMAT 单元级 `femBlock.inp`。

原因：

- 已经能跑通。
- 结果快。
- ODB 已能读取。
- 适合作为自动化验证基准。

第二版再扩展为薄板 coupon 几何：

- 长度 `100 mm`
- 宽度 `20 mm`
- 厚度 `1 mm`
- 一端固定
- 另一端施加位移
- 平面应力或薄壳/实体简化

## 5. 最小闭环流程

### Step 1：训练 J2 材料模型

执行：

```text
输入 J2 参数
-> 生成训练数据
-> 训练 SVM/SVC 屈服模型
-> 输出屈服面、曲线、模型参数、报告
```

验收：

- 有 `summary.json`
- 有 `material_model_report.md`
- 有 `yield_locus.png`
- 有 `stress_strain_curves.png`
- 有 `abq_*-svm.csv`
- 有 `abq_*-svm_meta.json`

### Step 2：Abaqus 单元级验算

执行：

```text
训练结果
-> abaqus_bridge.py
-> 准备 UMAT 验算目录
-> 调用 Abaqus/Standard
-> 读取 ODB
-> 输出应力-应变曲线和报告
```

验收：

- Abaqus Job 完成。
- 生成 `.odb`。
- 生成 `results/*-res.csv`。
- 生成 `abaqus_stress_strain_check.png`。
- 生成 `abaqus_verification_report.md`。

### Step 3：归档为案例

执行：

```text
选择 abaqus_verification 文件夹
-> 扫描并归档案例
-> 提取 INP/CSV/日志/ODB 元数据
```

验收：

- 有 `case_summary.json`
- 有 `case_report.md`
- INP 节点、单元、材料、Step 可识别。
- CSV 最大 Mises/PEEQ 可识别。
- 日志 warning/error 可识别。

### Step 4：ODB 深度后处理

执行：

```text
选择 ODB
-> 提取最后一帧 S/U/PEEQ/RF
-> 输出 JSON/CSV/Markdown
```

验收：

- 有 `odb_field_summary.json`
- 有 `odb_field_summary.csv`
- 有 `odb_field_report.md`
- `case_summary.json` 中出现 `odb_extractions`

### Step 5：ODB 帧曲线提取

执行：

```text
选择 ODB
-> 提取每一帧 S/U
-> 输出 frame series
```

验收：

- 有 `odb_frame_series.json`
- 有 `odb_frame_series.csv`
- 有 `odb_frame_series_report.md`
- CSV 中每帧有 `S` 和 `U` 两行。
- `case_summary.json` 中出现 `odb_frame_series`

### Step 6：导出训练数据集

执行：

```text
案例库
-> 导出训练数据集
```

验收：

- 有 `case_dataset.csv`
- 有 `frame_series_index.csv`
- 有 `dataset_manifest.json`
- 有 `dataset_report.md`
- `case_dataset.csv` 中包含 `latest_odb_max_mises`
- `frame_series_index.csv` 中指向逐帧曲线 CSV

### Step 7：代理模型 baseline

执行：

```text
case_dataset.csv
-> 特征清洗
-> 训练 RandomForest / MLP
-> 预测 Max Mises / Max U
```

验收：

- 有 `features.csv`
- 有 `targets.csv`
- 有 `surrogate_model.pkl`
- 有 `surrogate_metrics.json`
- 有 `prediction_vs_truth.png`
- 有 `surrogate_report.md`

注意：第一版样本很少，误差指标只用于证明流程，不代表工业精度。

### Step 8：闭环报告

执行：

```text
汇总训练、Abaqus、案例库、后处理、代理模型结果
-> 生成闭环报告
```

验收：

- 有 `closed_loop_validation_report.md`
- 报告能讲清楚：
  - 题目是什么
  - 输入是什么
  - 如何训练
  - 如何 Abaqus 验证
  - 如何提取 ODB
  - 如何导出数据集
  - 如何训练代理模型
  - 当前局限是什么
  - 下一步怎么扩展

## 6. 最小闭环的成功标准

闭环成功不要求代理模型预测很准。

闭环成功要求：

1. 从材料输入到 Abaqus 验证能自动跑通。
2. 从 Abaqus 结果到案例库能自动归档。
3. 从 ODB 到结构化特征能自动提取。
4. 从案例库到训练数据集能自动导出。
5. 从数据集到代理模型能训练并输出误差。
6. 全流程有报告、有图、有 CSV、有 JSON。
7. 你能用中文讲清楚每一步的工程意义。

## 7. 推荐命名

run 名称：

```text
closed_loop_j2_tension_demo
closed_loop_hill_tension_demo
```

案例标题：

```text
闭环验证-J2-薄板拉伸
闭环验证-Hill-薄板拉伸
```

标签：

```text
closed-loop, tensile, J2, Hill, Abaqus, surrogate, MVP
```

## 8. 为什么这个案例适合放进 GitHub

它能展示项目所有核心能力：

- 材料 AI 训练。
- Abaqus 验证。
- 案例库。
- ODB 后处理。
- 训练数据集。
- 代理模型。
- 报告自动化。

它又足够小，不需要复杂几何或大量算例，适合作为公开 demo。

## 9. 后续扩展题目

最小闭环完成后，可以扩展：

1. 不同屈服强度的 J2 参数扫描。
2. 不同 Hill 各向异性参数扫描。
3. 不同加载方向的板材拉伸。
4. 不同厚度的薄板拉伸。
5. 带孔板拉伸应力集中。
6. 简单弯曲回弹。
7. 接触压缩。
8. 自动化设备零件局部强度校核。

其中“带孔板拉伸应力集中”很适合作为第二个公开 demo，因为它比单元拉伸更接近结构工程问题，但仍然足够可控。
