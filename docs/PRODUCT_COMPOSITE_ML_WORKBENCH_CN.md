# MaterialAI Workbench：复合材料微观结构 + 有限元 + 机器学习产品说明

## 1. 产品定位

MaterialAI Workbench 是一个围绕机器学习构建的本地 CAE+AI 工作台。它不是替代 Abaqus，也不是只做一个 pyLabFEA notebook 展示，而是把你的日常仿真案例沉淀为可训练数据，把材料本构、微观结构、Abaqus 验证和代理模型放进同一个闭环。

当前主线：

```text
pyLabFEA 材料学习
-> 复合材料 Fiber / Interface / Matrix 微观 RVE 建模
-> Abaqus 微观/宏观仿真脚本生成
-> ODB/CSV 特征提取
-> 机器学习数据集
-> 代理模型 / 迁移学习 / 自然语言仿真客户端
```

## 2. 为什么必须围绕机器学习

有限元负责产生可信标签，机器学习负责把昂贵仿真经验压缩成可复用能力。

本项目的核心学习任务不是单纯求一个等效模量，而是逐步学习如下映射：

```text
微观相分布 phase_map
+ 纤维/界面/基体材料参数
+ 宏观几何、孔、载荷、边界
+ 历史 Abaqus 案例特征
-> 等效弹性/塑性参数、云图特征、最大 Mises、PEEQ、反力、允许载荷或失效因子
```

因此当前代码会导出：

- `phase_map.csv`：未来 CNN/3D CNN 的结构化输入。
- `micro_rve_voxel.inp`：真实 Fiber/Interface/Matrix 三相体素 RVE。
- `pbc_loadcase_plan.json`：六个微观 RVE 周期边界工况。
- `pylabfea_material_summary.json`：pyLabFEA 材料对象摘要。
- `effective_orthotropic_material.inp`：宏观 Abaqus 验证材料卡。
- `build_plate_with_hole.py`：Abaqus 3D 带孔板自动建模脚本。
- `composite_plate_dataset_row.csv`：机器学习表格样本。

## 3. 当前 MVP 已实现

### 3.1 pyLabFEA 结合点

当前流程调用 `pylabfea.Material.elasticity()` 定义三相材料：

- `fiber_phase`
- `interface_phase`
- `matrix_phase`

这一步的意义是让产品从一开始就有清晰的材料对象边界。后续可以继续接入 pyLabFEA 已有的 J2、Hill、Barlat、ML flow rule 和 notebook 教学体系。

### 3.2 复合材料微观 RVE

当前生成的是微观尺度体素模型，不只是等效材料：

- 纤维方向：全局 X。
- 横截面：Y-Z 平面随机圆形纤维。
- 相定义：`FIBER_PHASE`、`INTERFACE_PHASE`、`MATRIX_PHASE`。
- 单元：`C3D8R` 体素网格。
- 输出：节点位移、反力、单元应力和应变。

当前 RVE 已生成两类 Abaqus 输入：

- `micro_rve_voxel.inp`：最小单轴拉伸 sanity case。
- `pbc_jobs/micro_rve_pbc_*.inp`：EXX、EYY、EZZ、GXY、GXZ、GYZ 六个 PBC 工况。

生产级版本会继续加强边/角节点的 PBC 处理、cohesive 界面、损伤准则和 ODB 回填流程。

### 3.3 宏观带孔板验证

宏观模型采用 3D 带孔板拉伸：

- 几何参数：长度、宽度、厚度、孔半径。
- 材料：微观流程得到的工程常数材料卡。
- Abaqus 脚本：自动建模、划分网格、施加位移边界、写入 job。
- 后处理脚本：从 ODB 提取 Mises、位移、反力等摘要。

这个模型对应复合材料资料中“缺口/带孔结构 + 允许载荷空间 + 迁移学习”的路线，是后续最小闭环验证题目。

## 4. 本地运行

在仓库根目录运行：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_composite_workflow --name demo_composite
```

启动 App：

```powershell
conda run -n pylabfea streamlit run material_ai_workbench/streamlit_app.py --server.port 8501
```

进入 `复合材料RVE` 页面，点击 `生成复合材料闭环案例`。

## 5. 代码模块

| 模块 | 作用 |
|---|---|
| `material_ai_workbench/composite_workflow.py` | 复合材料 RVE、phase map、pyLabFEA 摘要、Abaqus 带孔板脚本、报告生成 |
| `material_ai_workbench/composite_dataset.py` | 复合材料批量样本生成、数据集合并、代理模型训练 |
| `material_ai_workbench/run_composite_workflow.py` | 命令行入口，适合批量生成样本 |
| `material_ai_workbench/run_composite_batch.py` | 复合材料批量计划和代理模型命令行入口 |
| `material_ai_workbench/streamlit_app.py` | 可视化工作台入口 |
| `material_ai_workbench/surrogate_model.py` | RandomForest/MLP baseline 代理模型 |
| `material_ai_workbench/case_library.py` | 日常 Abaqus 案例管理 |
| `material_ai_workbench/odb_postprocess.py` | ODB 场变量和帧曲线提取 |
| `src/pylabfea/material.py` | 材料定义、塑性、ML yield function 基础 |

## 6. 文献与资料映射

| 技术线 | 参考 | 对本项目的映射 |
|---|---|---|
| pyLabFEA ML 屈服函数 | Shoghi & Hartmaier, 2022, Frontiers in Materials, DOI `10.3389/fmats.2022.868248` | 支撑 J2/Hill/Barlat 到 ML flow rule 的材料本构学习 |
| Abaqus RVE 周期边界 | EasyPBC, *Engineering with Computers*, DOI `10.1007/s00366-018-0616-4` | 后续加入 PBC、六工况等效刚度和自动后处理 |
| 体素 RVE + 神经网络 | Chuang & Tsai, 2025, *Journal of Mechanics*, DOI `10.1093/jom/ufaf026` | 当前 `phase_map.csv` 是未来 3D CNN 输入的第一版 |
| 缺口复合材料迁移学习 | Li et al., 2024, *Composites Science and Technology*, DOI `10.1016/j.compscitech.2024.110432` | 带孔板验证案例将扩展成允许载荷/失效因子迁移学习 |
| TexGen + Abaqus 体素网格 | TexGen 官方资料：Voxel Meshing and Abaqus | 后续从随机圆纤维扩展到编织/织物复合材料 |
| Abaqus 后处理自动化 | Abaqus2Matlab, DOI `10.1016/j.advengsoft.2017.01.006` | 支撑 ODB/结果文件批量提取、统计分析和训练数据生成思想 |

## 7. 下一阶段产品任务

1. 强化 PBC 边/角节点约束并对照 EasyPBC 思路校核。
2. 从微观 ODB 提取 `E1/E2/E3/G12/G13/G23/nu12/nu13/nu23` 并自动回填数据集。
3. 增加 Hashin / Tsai-Wu 失效因子字段。
4. 用当前 `phase_map.csv` 训练第一个微结构代理模型 baseline。
5. 带孔板宏观模型增加铺层角、孔径、厚度、载荷类型参数扫描。
6. 案例库支持“复合材料案例”分类和相似案例检索。
7. 接入 Abaqus MCP，把生成模型、提交 job、抓云图、读 ODB 做成实时按钮。
8. 封装桌面客户端，Streamlit 作为原型，业务服务层保持共用。

## 8. GitHub 发布目标

发布时仓库必须让别人做到三件事：

1. 看懂：README、中文产品文档、源码教学文档完整。
2. 跑通：一条命令生成复合材料 RVE + 带孔板验证脚本。
3. 复现：测试通过，示例数据小而完整，大型 Abaqus 结果不进入 Git。
