# Barlat / Yld2000-2D 到 pyLabFEA Yld2004-18p 的工程映射

本页说明 MaterialAI Workbench 里 `barlat` 选项到底做了什么，以及它不能代表什么。

## 1. 当前产品定位

当前 App 的 Barlat 入口用于学习、快速对比和早期工程探索。界面接收 8 个 Yld2000-2D 风格的各向异性系数 `alpha1 ... alpha8`，内部会把它们展开为 pyLabFEA 可调用的 18 参数 Barlat/Yld2004 形式。

这不是严格的 Yld2000-2D 标定器，也不是可以直接交付量产材料卡的实验标定流程。正式项目必须使用 0、45、90 度单拉、双向拉伸、平面应变、r 值或等塑性功轮廓等实验数据重新识别参数。

## 2. 为什么需要映射

pyLabFEA 的 `Material.plasticity(..., barlat=..., barlat_exp=...)` 接口接收的是 18 个系数，目标是描述三维应力空间下的 Barlat 类各向异性屈服函数。

但对于板材成形和初学者，Yld2000-2D 的 8 个 alpha 更直观：它们通常与平面应力下的轧制方向、横向、45 度方向和剪切/双向响应相关。因此 Workbench 保留 8 参数输入，再执行一个确定性展开。

## 3. 当前代码映射

核心函数在 `material_ai_workbench/pipeline.py`：

```python
def _barlat18_from_yld2000_alphas(config):
    raw = config.barlat_coeffs if config.barlat_coeffs is not None else config.barlat_alphas
    alphas = [float(value) for value in raw]
    a1, a2, a3, a4, a5, a6, a7, a8 = alphas
    shear = (a7 + a8) / 2.0
    first_transform = [a1, a2, a3, a4, a5, a6, a7, a8, shear]
    second_transform = [a2, a1, a4, a3, a6, a5, a8, a7, shear]
    return first_transform + second_transform
```

也就是：

```text
输入：a1, a2, a3, a4, a5, a6, a7, a8

第一组 9 参数：
[a1, a2, a3, a4, a5, a6, a7, a8, (a7+a8)/2]

第二组 9 参数：
[a2, a1, a4, a3, a6, a5, a8, a7, (a7+a8)/2]

输出：18 参数 = 第一组 + 第二组
```

这样做的目的不是复制论文里的完整标定，而是让用户可以：

- 用 8 个直观参数改变屈服面方向性；
- 在 pyLabFEA 的 18 参数接口下跑通训练；
- 通过测试保证各向同性输入时屈服面近似圆形，各向异性输入时方向响应会改变。

## 4. 如何在 App 中使用

1. 打开 Streamlit App。
2. 进入材料训练页面。
3. 材料模型选择 `Barlat/Yld2000 experimental`。
4. 先保留默认 alpha 全部为 1，确认它接近各向同性。
5. 再调整 alpha，例如让 `a1`、`a2`、`a7`、`a8` 有明显差别，观察屈服面和 Abaqus 验算变化。

建议学习顺序：

1. J2：理解各向同性屈服。
2. Hill：理解二次型各向异性。
3. Barlat：理解非二次型屈服面和板材方向性。
4. 实验曲线导入：用真实材料数据反推参数。

## 5. 命令行示例

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench `
  --material barlat `
  --name learn_barlat `
  --sy 120 `
  --barlat-exponent 8 `
  --barlat-alphas 1.0,0.9,1.1,1.0,1.0,1.0,0.85,1.15 `
  --with-curves
```

输出重点看：

- `yield_surface_*.png`：屈服面方向性；
- `training_report.md`：训练质量；
- `*_meta.json`：写入的 alpha、指数和 SVM 参数；
- Abaqus 验算结果：是否与材料训练期望一致。

## 6. 已有自动测试

测试文件：`tests/test_pipeline_barlat.py`

覆盖三类检查：

- 8 个 alpha 能稳定展开为 18 个正系数；
- alpha 全为 1 时，代表性板材方向上的屈服响应接近 J2；
- 非均匀 alpha 会产生明显方向性响应。

运行：

```powershell
conda run -n pylabfea python -m pytest tests/test_pipeline_barlat.py -q
```

## 7. 参考文献

- Barlat 等，Yld2000-2D：Plane stress yield function for aluminum alloy sheets - Part 1: Theory，International Journal of Plasticity, 2003. DOI: https://doi.org/10.1016/S0749-6419(02)00019-0
- Barlat 等，Yld2004-18p：Linear transformation-based anisotropic yield functions，International Journal of Plasticity, 2005. DOI: https://doi.org/10.1016/j.ijplas.2004.06.004
- Abaqus Barlat anisotropic plasticity verification examples: https://help-3dexperience.aesvietnam.com/English/SIMA3DXVERRefMap/simaver-c-barlatplasticity.htm

## 8. 下一步应该怎么升级

后续要把 Barlat 从工程入口升级为生产级功能，需要新增：

1. 从 0、45、90 度拉伸和 r 值自动识别 alpha；
2. 支持等双拉、平面应变和剪切实验点；
3. 输出参数识别残差和置信区间；
4. 与 Abaqus 内置 Barlat 或 UMAT 结果做单元级对比；
5. 将真实板材冲压/拉伸案例纳入案例库，持续修正参数。
