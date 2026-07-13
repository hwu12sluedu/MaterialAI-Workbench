# DeepSeek 2026-07-06 全日任务单：真实取向 Fiber RVE 可视化与数据闭环

## 背景判断

当前 MaterialAI Workbench 的复合材料微观结构显示存在明显产品可信度问题：

- `rve_visualization.py` 当前 3D 图是 voxel/scatter 点云，像调试图，不像真实复合材料微观结构。
- `composite_workflow.write_microstructure_preview()` 当前 2D 图是规则 3x3 圆形截面，缺少纤维角度、随机性、真实界面层和三维感。
- 当前 `generate_fiber_layout()` 假设 fiber 沿 global X，且只在 YZ 平面排圆截面；这对早期 PBC 验证可以保留，但不能作为产品级 “参考 Multimech” 微观建模体验。

今天 DeepSeek 的核心目标不是继续堆功能，而是把复合材料 RVE 从“抽象图”升级成“真实微观纤维结构 + 可训练数据资产”。

## 总目标

实现一个产品级的实时 Fiber RVE 视图：

```text
用户调参数
-> 实时生成带取向角的 fiber layout
-> 3D 中显示真实圆柱/短纤维/界面包覆层/透明基体
-> 2D 截面显示斜切椭圆或 fiber 穿过截面的真实形态
-> layout / phase map / dataset row 都记录 fiber 角度、长度、取向张量等 ML 特征
-> smoke 测试和截图证明不再是抽象点云或规则圆阵列
```

## 禁止项

今天不要再做这些：

- 不要用 `Scatter3d(symbol="square")` 当最终 3D RVE 产品图。
- 不要只画 2D 规则圆阵列。
- 不要只做“更漂亮的颜色”而不改数据结构。
- 不要只写文档不改代码。
- 不要把可视化和真实 `fiber_layout.json` 脱钩，图必须来自同一个 layout 数据源。
- 不要让 fiber 只有 global X 一个方向；至少支持 `theta_deg` 角度和一定取向分散。

## 任务 1：扩展 RVE 参数模型

### 目标

在 `CompositePlateConfig` 中加入 fiber 取向与真实几何参数，默认保持旧流程可运行。

### 文件

- `material_ai_workbench/composite_workflow.py`
- `material_ai_workbench/composite_dataset.py`
- `material_ai_workbench/streamlit_app.py`

### 建议字段

在 `CompositePlateConfig` 中新增：

```python
fiber_orientation_theta_deg: float = 0.0      # 绕 Z 或板面内主方向角，0 表示沿 X
fiber_orientation_phi_deg: float = 0.0        # 离开板面的俯仰角，MVP 可先固定 0
fiber_orientation_spread_deg: float = 8.0     # 取向分散，用于随机短纤维或制造偏差
fiber_length_normalized: float = 1.2          # 纤维长度相对 RVE 尺寸
fiber_length_std: float = 0.08
fiber_diameter_normalized: float | None = None # 若为空，仍由 Vf 校准半径
fiber_geometry_mode: str = "oriented_cylinders" # "ud", "oriented_cylinders", "chopped"
```

### 验收

- 旧的测试不需要改配置也能通过。
- `asdict(config)` 可 JSON 化。
- Streamlit 左侧 RVE 控件新增角度和分散度输入。

## 任务 2：重写 fiber layout，生成真实带角度纤维

### 目标

替换单纯 YZ 圆心布局，生成真正的 3D fiber segment 数据。`fiber_layout.json` 应成为唯一真实数据源。

### 文件

- `material_ai_workbench/composite_workflow.py`

### 输出结构

`generate_fiber_layout()` 仍可保留原名，但返回必须新增：

```json
{
  "coordinate_system": "unit_cube_xyz",
  "fiber_geometry_mode": "oriented_cylinders",
  "target_vf": 0.55,
  "actual_vf": 0.542,
  "fiber_radius_normalized": 0.08,
  "interface_radius_normalized": 0.095,
  "orientation_tensor": {"a11": 0.93, "a22": 0.05, "a33": 0.02, "a12": 0.1},
  "fibers": [
    {
      "id": 1,
      "center": [0.5, 0.42, 0.31],
      "start": [-0.1, 0.37, 0.31],
      "end": [1.1, 0.47, 0.31],
      "direction": [0.996, 0.087, 0.0],
      "theta_deg": 5.0,
      "phi_deg": 0.0,
      "length": 1.2,
      "radius": 0.08,
      "interface_radius": 0.095
    }
  ]
}
```

### 关键要求

- 支持随机种子复现。
- fiber 应有角度，不是全部平行 global X。
- `actual_vf` 必须仍然按 voxel phase 或几何近似校准，误差 <= 3%。
- 对穿出 RVE 边界的 fiber，MVP 可允许显示穿出并用半透明 box 裁切视觉；后续再做周期性 wrap。
- 保留旧字段 `centers` 一段时间做兼容，但新代码优先读 `fibers`。

### 验收

新增测试：

- `test_oriented_fiber_layout_contains_segments_and_angles`
- `test_oriented_fiber_layout_vf_within_three_percent`
- `test_orientation_tensor_is_written_to_layout`

## 任务 3：3D 可视化从点云改为真实 fiber cylinders

### 目标

`rve_visualization.py` 里不要再用 scatter square 表示最终视图。使用 Plotly `Mesh3d` 或 `Surface` 生成真实圆柱/短纤维：

- fiber：蓝色或深青色实体圆柱
- interface：半透明琥珀色外层圆柱/管
- matrix：透明或半透明 box
- RVE bounds：细线框
- 可旋转、可缩放、参数实时变化

### 文件

- `material_ai_workbench/rve_visualization.py`
- `material_ai_workbench/streamlit_app.py`

### 实现建议

新增函数：

```python
def cylinder_mesh_between_points(start, end, radius, n_sides=20) -> dict[str, np.ndarray]:
    ...

def plot_oriented_fiber_rve_3d(config: CompositePlateConfig, *, show_matrix=True, show_interface=True) -> go.Figure:
    ...
```

MVP 不必做到 CAD 级布尔裁剪，但视觉必须满足：

- 能看出每根 fiber 是一段有方向的圆柱。
- 能看出 interface 是包覆在 fiber 外的一层。
- matrix 是透明实体，不是满屏灰色点。
- 图例应显示 Fiber / Interface / Matrix / RVE bounds。

### 验收

- 不再出现第一张图那种满屏方块散点作为主视图。
- `plot_oriented_fiber_rve_3d()` 返回 figure，至少包含 `Mesh3d` trace。
- Streamlit 右侧 RVE 预览默认使用新函数。
- 运行：

```powershell
conda run -n pylabfea python -m pytest tests/test_rve_visualization.py -q
```

## 任务 4：2D 静态预览改为真实截面/投影

### 目标

替换第二张图那种规则圆截面。静态 PNG 应该像“工程报告中的 RVE 截面图”，至少包含：

- 斜向 fiber 在截面上的投影或斜切椭圆。
- 随机/准随机位置，不是 3x3 棋盘。
- interface 层应是包覆环或沿 fiber 方向的外层。
- 标注 `theta_mean`, `orientation_spread`, `actual_vf`。

### 文件

- `material_ai_workbench/composite_workflow.py`

### 建议

新增：

```python
def write_oriented_microstructure_preview(...)
```

或直接改 `write_microstructure_preview()`，但要保证旧测试通过。

### 验收

- 生成的 `micro_rve_preview.png` 不能再是规则 3x3 圆阵列。
- 至少有一个测试检查 `layout["fibers"]` 中 theta 不全为 0，且 PNG 文件存在。

## 任务 5：phase map / Abaqus RVE 与可视化保持一致

### 目标

当前 phase map 用到的是“到 YZ 圆心距离”，无法表达倾斜 fiber。需要改为“点到 3D 线段距离”，让 voxel phase 与带角度 fiber layout 对齐。

### 文件

- `material_ai_workbench/composite_workflow.py`

### 实现要求

新增通用函数：

```python
def distance_point_to_segment(point_xyz, start_xyz, end_xyz) -> float:
    ...

def classify_voxel_phase(point_xyz, fibers, radius, interface_radius) -> str:
    ...
```

用于：

- `write_micro_rve_inp()`
- `_write_single_micro_rve_pbc_inp()`
- `build_rve_phase_grid()` 或新 visualization grid

### 验收

- 同一 `fiber_layout.json` 同时驱动 visualization 和 phase map。
- `phase_map.csv` 中 fiber/interface/matrix 比例与 layout summary 一致。
- `actual_vf` 仍在目标 ±3% 内。

## 任务 6：把取向特征写入 ML 数据资产

### 目标

我们最终围绕机器学习，所以 fiber 可视化参数必须进入数据集，而不是只停留在图里。

### 文件

- `material_ai_workbench/composite_workflow.py`
- `material_ai_workbench/composite_dataset.py`
- `material_ai_workbench/case_library.py` 如有必要

### 新增 CSV 字段

在 `composite_plate_dataset_row.csv` 和批量数据集中新增：

```text
fiber_orientation_theta_deg
fiber_orientation_phi_deg
fiber_orientation_spread_deg
fiber_length_normalized
fiber_radius_normalized
fiber_aspect_ratio
orientation_a11
orientation_a22
orientation_a33
orientation_a12
```

### 验收

- 单个 product smoke 的 CSV 有这些列。
- composite batch 导出的 dataset 也有这些列。
- 代理模型训练不因新增列失败。

## 任务 7：UI 调整

### 目标

让用户在 Streamlit 中实时调整：

- Vf
- fiber count
- theta angle
- orientation spread
- fiber length
- interface thickness
- random seed

右侧实时刷新新 3D fiber RVE，不再展示点云作为主图。

### 文件

- `material_ai_workbench/streamlit_app.py`

### 验收

- 修改角度后，3D 图中 fiber 方向肉眼可见变化。
- 修改 seed 后，fiber 排布变化。
- 修改 Vf 后，actual Vf 指标更新。
- UI 文案用中文，说明这是“微观 fiber 取向预览”，不要写成“voxel scatter”。

## 任务 8：测试、截图、状态文档

### 测试命令

必须跑：

```powershell
conda run -n pylabfea python -m py_compile material_ai_workbench/streamlit_app.py material_ai_workbench/rve_visualization.py material_ai_workbench/composite_workflow.py
conda run -n pylabfea python -m pytest tests/test_composite_workflow.py tests/test_product_closed_loop.py tests/test_rve_visualization.py -q --disable-warnings
conda run -n pylabfea python -m pytest tests material_ai_workbench/tests -q -m "not slow" --disable-warnings
```

### 产物

保存以下文件：

```text
material_ai_workbench/composite_runs/<latest>/figures/micro_rve_preview.png
material_ai_workbench/composite_runs/<latest>/micro_rve/fiber_layout.json
material_ai_workbench/composite_runs/<latest>/composite_plate_dataset_row.csv
material_ai_workbench/composite_runs/<latest>/product_closed_loop_report.md
```

新增或更新状态文档：

```text
docs/00_project_status/DEEPSEEK_RVE_VISUAL_UPDATE_20260706_CN.md
```

文档需要说明：

- 旧图为什么不合格。
- 新图如何表达真实 fiber 取向。
- 取向数据如何进入 ML 数据集。
- 还有哪些未完成，比如真实 Abaqus 几何 cylinder meshing / 周期性 wrap / PBC 严格约束。

## 今日优先级

如果时间不够，按这个顺序砍：

1. 必须完成：任务 1、2、3、5、6 的最小实现。
2. 必须完成：测试和一条 product smoke。
3. 尽量完成：2D PNG 静态预览。
4. 可推迟：复杂周期性 wrap、真实 Abaqus cylinder mesh、漂亮动画。

## 最终验收标准

今天结束时，给 Codex/用户的结果必须满足：

- App 里看到的 RVE 不再是散点方块和规则圆阵列。
- 3D 里能明确看到真实 fiber 圆柱、角度、界面层、透明 RVE box。
- fiber 角度和取向分散可实时调整。
- `fiber_layout.json`、`phase_map.csv`、`composite_plate_dataset_row.csv` 互相一致。
- 快速测试集通过。
- 有最新截图/报告证明改动。
