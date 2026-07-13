# pyLabFEA 与 MaterialAI Workbench API 连接说明

## 1. 设计原则

pyLabFEA 是材料和小型有限元学习内核，MaterialAI Workbench 是面向工程使用的产品层。

接口边界：

- pyLabFEA 负责材料对象、屈服函数、应力空间采样和轻量有限元。
- MaterialAI Workbench 负责 Abaqus 自动化、数据管理、复合材料 RVE、代理模型和报告。

## 2. pyLabFEA 关键入口

### 2.1 定义弹性材料

```python
import pylabfea as FE

mat = FE.Material(name="matrix_phase")
mat.elasticity(E=3500.0, nu=0.35)
```

当前复合材料模块会为三相材料自动生成：

- `fiber_phase`
- `interface_phase`
- `matrix_phase`

输出在：

```text
pylabfea_material_summary.json
```

### 2.2 定义塑性材料

```python
mat = FE.Material(name="j2_demo")
mat.elasticity(E=200000.0, nu=0.3)
mat.plasticity(sy=60.0, khard=0.0)
```

Hill 各向异性：

```python
mat = FE.Material(name="hill_demo")
mat.elasticity(E=200000.0, nu=0.3)
mat.plasticity(sy=60.0, hill=[1.2, 1.0, 0.8, 1.0, 1.0, 1.0], sdim=6)
```

### 2.3 生成机器学习应力样本

```python
sig_train, y_train = mat.create_sig_data(N=40, Nseq=4)
```

这一步对应产品中的材料训练样本生成。

## 3. MaterialAI Workbench 关键入口

### 3.1 单个复合材料案例

```python
from material_ai_workbench import CompositePlateConfig, run_composite_plate_workflow

result = run_composite_plate_workflow(
    CompositePlateConfig(name="demo_composite")
)
```

核心输出：

- `micro_rve_voxel.inp`
- `phase_map.csv`
- `pylabfea_material_summary.json`
- `pbc_loadcase_plan.json`
- `run_pbc_jobs.ps1`
- `extract_rve_effective_stiffness.py`
- `build_plate_with_hole.py`
- `composite_plate_dataset_row.csv`

### 3.2 批量复合材料样本

```python
from material_ai_workbench import CompositeBatchConfig, create_composite_batch_plan, run_composite_batch_plan

plan = create_composite_batch_plan(
    CompositeBatchConfig(name="vf_eta_hole_sweep", sample_count=12)
)
plan = run_composite_batch_plan(plan.plan_dir, max_samples=4)
```

输出：

```text
composite_dataset.csv
```

### 3.3 训练复合材料代理模型

```python
from material_ai_workbench import train_composite_surrogate

surrogate = train_composite_surrogate(
    "material_ai_workbench/composite_batches/<plan>/composite_dataset.csv",
    target_column="max_stress_near_hole_estimate_mpa",
    model_kind="random_forest",
)
```

## 4. 命令行入口

单案例：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_composite_workflow --name demo_composite
```

批量计划：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_composite_batch create --name demo_sweep --sample-count 8
```

运行批量样本：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_composite_batch run material_ai_workbench/composite_batches/<plan> --max-samples 3
```

训练代理模型：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_composite_batch train material_ai_workbench/composite_batches/<plan>/composite_dataset.csv
```

## 5. 后续扩展接口

下一步要把 RVE ODB 的真实等效刚度回填到 `composite_dataset.csv`：

```text
PBC ODB
-> extract_rve_effective_stiffness.py
-> rve_effective_stiffness.csv/json
-> composite_dataset.csv
-> surrogate model
```

这样产品就从“估算标签训练”升级为“真实 Abaqus 微观标签训练”。
