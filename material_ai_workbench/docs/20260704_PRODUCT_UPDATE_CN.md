# 2026-07-04 产品更新记录

本轮目标是把 DeepSeek 建议的 10 项任务从 demo 推进到可验证的产品功能，并完成一个真实 Abaqus 复合材料闭环案例。

## 已完成

1. 复合材料微观 RVE 到 Abaqus 3D 带孔板闭环
   - 新增正式入口：`materialai-composite-closed-loop`
   - Python 模块入口：`python -m material_ai_workbench.run_composite_closed_loop`
   - 已真实调用 Abaqus 求解 3D 带孔板拉伸模型，生成 ODB 并完成后处理。

2. Abaqus 复合材料方向修复
   - 为工程常数正交各向异性材料自动创建局部材料方向坐标系。
   - 修复了 Abaqus fatal error：各向异性材料缺少 local orientation。
   - 求解成功标准不再只看 CAE 脚本返回码，而会检查 Abaqus job 日志。

3. ODB 后处理稳健性修复
   - 先写出 `plate_results.json/csv`，再尝试关闭 ODB。
   - 避免 Abaqus Python 2.7 在 `odb.close()` 阶段抛 `_ctypes` 导致有效结果丢失。

4. 实验曲线导入到材料训练
   - CSV 导入增加 NaN/Inf、非单调应变、可疑刚度、百分比应变等校验。
   - 导入后的标准化曲线可自动估算 `E` 和 `sy`，并一键启动材料训练。

5. Barlat/Yld2000-2D 风格各向异性入口
   - UI 和 CLI 已支持 8 个 Barlat 参数与指数。
   - 当前实现会把 8 参数输入映射到 pyLabFEA 的 Barlat 18 参数后端，用于初版训练闭环。

6. Streamlit 产品入口完善
   - 增加 Abaqus Job 队列入口，可提交 `.inp`、查看队列状态、串行处理 job。
   - 案例库增加相似案例推荐。
   - 代理模型页面增加多保真代理模型训练入口。
   - 修复旧 Streamlit 进程导致的导入报错，并验证 `http://localhost:8501/` 可正常打开。

7. 发布基础
   - 新增 Docker healthcheck。
   - Docker Compose 增加 composite/case/import/surrogate/closed-loop 数据目录映射。
   - CI 覆盖 `tests` 与 `material_ai_workbench/tests`。
   - `workspace/`、缓存、构建产物已加入忽略或清理。

## 已验证

### 完整测试

```powershell
conda run -n pylabfea pytest tests material_ai_workbench/tests -q
```

结果：

```text
54 passed, 5 skipped, 1 warning
```

### 复合材料 Abaqus 闭环

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_composite_closed_loop
```

最新成功 run：

```text
material_ai_workbench/composite_runs/20260704_015120_comp_full_demo
```

关键结果：

```text
Abaqus status: abaqus_completed
Max Mises: 1829.1776 MPa
Max displacement: 0.3609 mm
Composite surrogate: MAE=38.78, RMSE=43.13, R2=0.796
```

最新归档案例：

```text
material_ai_workbench/cases/20260704_015254_comp_full_demo_plate_hole
```

### Streamlit App

```text
http://localhost:8501/
```

健康检查：

```text
/_stcore/health -> ok
```

## 下一步建议

1. 把 Abaqus Job 队列升级为真正后台 worker，避免长 job 占用 Streamlit 单次交互。
2. 把 Barlat 初版从参数映射升级为严格 Yld2000-2D 数学形式，并补充屈服面可视化对比。
3. 把复合材料 RVE 从当前参数化体素/工程映射继续推进到更多微观边界条件、PBC 求解和真实微观结果回归。
4. 增加用户案例库的向量检索和自然语言复用能力：从“找相似案例”走向“一句话复做类似仿真”。
