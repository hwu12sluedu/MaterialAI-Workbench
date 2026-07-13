# pyLabFEA 项目研读与 App 化路线

## 1. 我们对这个项目的定位

pyLabFEA 不是要替代 Abaqus 的通用有限元软件，而是一个适合学习和研究的“有限元 + 材料本构 + 机器学习屈服函数”实验平台。

它对我们的价值主要有三点：

1. 用较透明的 Python 代码展示有限元主流程：材料、几何、网格、边界条件、求解、后处理。
2. 用可控小模型学习弹性、塑性、等效应力、屈服面、硬化、均匀化等材料力学概念。
3. 用机器学习训练材料屈服函数，并通过 Abaqus UMAT 做材料力学行为验算。

长期目标不是直接照搬 pyLabFEA，而是把其中可复用的材料训练、结果可视化、Abaqus 验算流程抽出来，封装成一个面向工程师的本地 App。

## 2. 已完成的本机复现结果

环境：

- conda 环境：`pylabfea`
- Python：3.12.13
- pyLabFEA：4.4.2
- 安装方式：本地源码 editable 安装

验证：

- 官方测试：`pytest tests -v` 通过，`11 passed`
- 修复了 Matplotlib 3.11 对 `plt.cm.get_cmap(...)` 的兼容问题
- 主要教学 notebook 已全部执行成功，输出在 `_learning_runs`

已执行成功的 notebook：

- `pyLabFEA_Introduction.ipynb`
- `pyLabFEA_Composites.ipynb`
- `pyLabFEA_Equiv-Stress.ipynb`
- `pyLabFEA_Plasticity.ipynb`
- `pyLabFEA_Homogenization.ipynb`
- `pyLabFEA_ML-FlowRule-Tresca.ipynb`
- `pyLabFEA_ML-FlowRule-Hill.ipynb`
- `pyLabFEA_ML-FlowRule-Training.ipynb`

## 3. 内容地图

### 3.1 基础有限元与材料力学

对应 notebook：

- `Introduction`
- `Composites`
- `Equiv-Stress`
- `Plasticity`
- `Homogenization`

核心概念：

- 1D/2D 有限元模型
- 弹性材料参数
- 复合材料 Voigt / Reuss 等效刚度
- J2 等效应力
- 主应力、偏应力、屈服准则
- 弹塑性响应与线性硬化
- 多材料局部应力、应变、塑性应变分布

这部分适合作为 App 的“材料力学基础算例库”和“教学/验证模块”。

### 3.2 机器学习本构

对应 notebook：

- `ML-FlowRule-Tresca`
- `ML-FlowRule-Hill`
- `ML-FlowRule-Training`

核心流程：

1. 定义参考材料，例如 J2、Tresca、Hill、Barlat。
2. 在 3D 或 6D 应力空间中生成屈服点数据。
3. 用 SVM/SVC 训练机器学习屈服函数。
4. 评估训练集、测试集、支撑向量、屈服面误差。
5. 把训练好的 ML flow rule 放回 pyLabFEA 的材料对象中做有限元计算。
6. 导出 Abaqus UMAT 可读取的参数文件。

这部分是后续原创项目的核心：材料数据驱动的本构训练。

### 3.3 数据驱动材料

对应源码和示例：

- `src/pylabfea/data.py`
- `examples/Train_CPFEM`
- `examples/Texture`

作用：

- 读取微观力学或晶体塑性模拟数据
- 提取弹性常数、屈服应力、塑性硬化信息
- 支持带晶体织构信息的数据
- 把真实或仿真数据转换成 ML flow rule 训练数据

这部分是未来接实验数据、CPFEM 数据、Abaqus 批量仿真数据的入口。

### 3.4 Abaqus UMAT 验算

对应目录：

- `examples/UMAT`

核心文件：

- `ml_umat.f`：Abaqus UMAT，用 Fortran 实现 ML flow rule
- `femBlock.inp`：单元模型，用于多载荷路径下的应力-应变曲线验算
- `plate_shear.inp`：薄板剪切算例，用于比较 J2 和 ML 本构
- `calc_properties.py`：Abaqus Python 脚本，批量提交工况并读取 ODB
- `plot_sig_eps.py`：读取 Abaqus 结果并画应力-应变曲线
- `models/*.csv` 和 `models/*_meta.json`：训练好的 SVM 支撑向量和元数据

Abaqus 验算流程：

1. pyLabFEA 训练 ML flow rule。
2. 导出 `abq_<material>-svm.csv` 和 `abq_<material>-svm_meta.json`。
3. Abaqus UMAT 读取这些 SVM 参数。
4. `femBlock.inp` 或其他 `.inp` 调用 `ml_umat.f`。
5. Abaqus 求解。
6. Python 读取 ODB，提取应力、应变、塑性应变、Mises、PEEQ。
7. 与参考材料模型或 Abaqus 内置 J2 模型对比。

本机 Abaqus 调用建议：

- 提交 job：`D:\ABAQUS\2023\Commands\abaqus.bat`
- 读取 ODB：`D:\ABAQUS\2023\EstProducts\win_b64\code\bin\SMAPython.exe`

## 4. 源码模块怎么封装

### `basic.py`

适合封装成 App 的“应力应变工具箱”：

- J2 等效应力
- 主应力
- 偏应力
- 应力空间坐标变换
- 等效塑性应变

### `material.py`

适合封装成 App 的“材料模型核心”：

- 弹性参数定义
- 塑性参数定义
- J2 / Hill / Barlat 等屈服准则
- 应力应变曲线计算
- SVM 屈服函数训练
- ML 参数导出
- 屈服面可视化

### `model.py`

适合封装成 App 的“小型验证求解器”：

- 创建 1D/2D 简化 FEM 模型
- 多材料分区
- 边界条件
- 网格
- 求解
- 全局/局部应力应变结果
- 云图可视化

### `data.py`

适合封装成 App 的“材料数据导入与清洗模块”：

- 读取材料力学数据
- 从应力-应变数据中提取屈服点
- 拟合弹性常数
- 生成训练集
- 可视化训练数据和屈服面

## 5. App 化目标

建议 App 名称暂定：

`MaterialAI Workbench`

定位：

一个本地材料本构训练与 Abaqus 验算工具。用户输入材料参数或导入材料数据，App 训练 ML flow rule，自动生成 Abaqus UMAT 参数，并运行标准材料力学验算算例，输出报告。

## 6. MVP 功能范围

第一版不要做成完整 CAE 平台，只做一个窄而完整的闭环。

### MVP 输入

- 材料类型：J2 / Hill / Barlat / 数据驱动
- 弹性参数：E、nu 或 C 矩阵
- 塑性参数：屈服强度、硬化参数、各向异性参数
- ML 参数：C、gamma、训练点数量、训练方式
- Abaqus 验算开关：是否运行 UMAT 验算

### MVP 处理流程

1. 创建参考材料。
2. 生成训练数据。
3. 训练 SVM 屈服函数。
4. 画屈服面和训练点。
5. 计算应力-应变曲线。
6. 导出 UMAT 参数文件。
7. 可选调用 Abaqus 单元模型验算。
8. 读取 Abaqus 结果。
9. 生成 HTML/PDF 报告。

### MVP 输出

- 材料参数摘要
- 训练集和测试集评分
- 支撑向量数量
- 屈服面图
- 应力-应变曲线
- Abaqus 验算结果 CSV
- Abaqus 与 pyLabFEA/reference 的对比图
- 可追溯报告

## 7. 推荐技术架构

### 第一阶段：本地 Web App

优先使用 Python 技术栈，降低工程复杂度：

- UI：Streamlit 或 PySide6
- 后端：pyLabFEA 封装服务
- 数据：项目文件夹 + JSON/CSV
- 图表：Matplotlib
- 报告：Markdown/HTML/PDF

建议先用 Streamlit 做原型，因为它能最快把表单、图、结果和文件下载串起来。

### 第二阶段：桌面端工程化

当核心流程稳定后，再考虑：

- PySide6 桌面端
- 或 Electron/Tauri + Python/FastAPI 后端

桌面端界面可以包括：

- 项目管理
- 材料库
- 训练任务列表
- Abaqus Job 面板
- 结果图预览
- 报告导出
- LLM API 配置

## 8. 与 Abaqus 联合验算的路线

### 第一阶段：标准材料点/单元验算

用 `examples/UMAT/femBlock.inp` 做标准工况：

- 单轴拉伸 x/y/z
- 双轴拉伸
- 剪切
- 提取 S、LE、SDV、PEEQ、Mises

目标：验证 ML 本构的应力-应变行为是否接近参考模型。

### 第二阶段：板剪切算例

用 `plate_shear.inp` 比较：

- Abaqus 内置 J2
- ML flow rule UMAT

目标：验证场变量云图，包括 Mises、塑性应变、剪切应力。

### 第三阶段：自定义工程小模型

创建一个简化工程模型，例如：

- 拉伸试样
- 开孔板
- 弯曲梁
- 接触压痕

目标：展示这个材料本构在更接近工程问题时的表现。

## 9. 后续执行建议

建议我们按下面顺序推进：

1. 我先把 pyLabFEA 的训练流程封装成几个稳定函数。
2. 做一个命令行版本：输入材料参数，输出训练结果和图。
3. 再做 Streamlit 原型 App。
4. 接入 Abaqus 单元模型验算。
5. 增加报告生成。
6. 最后再考虑桌面端和 LLM 交互。

## 10. 关键风险

1. pyLabFEA 是 GPLv3，若做公开发布或商业分发，需要注意开源协议义务。
2. ML flow rule 当前主要基于 SVM 屈服面，不能简单宣传成通用神经网络本构。
3. Abaqus UMAT 编译和运行依赖本机 Fortran/编译链配置，后续需要单独验证。
4. 真实材料数据质量会显著影响训练效果，需要有数据清洗和异常检查。
5. App 第一版必须控制范围，不要一开始就做完整 Abaqus 前处理器。

## 11. 我们的项目定位句

面向机械工程师的材料本构训练与 Abaqus 验算工具：基于 pyLabFEA 训练机器学习屈服函数，自动导出 UMAT 参数并完成 Abaqus 标准力学行为验算，输出可追溯的材料模型报告。

## 12. 长期平台愿景：有限元 AI Workbench

最终目标不是只做一个材料曲线小工具，而是构建一个面向工程师和普通技术用户的有限元 AI 平台。它要把有限元、机器学习、自然语言交互、模型管理和工程报告串成一个闭环，让复杂仿真不再只依赖少数专家手工操作。

这个平台可以拆成六个核心方向：

1. `ML + FEA`：用机器学习学习有限元中的材料行为、边界响应、关键场变量和失效趋势。
2. `FEA -> ML`：用有限元批量生成高质量训练样本，补足实验数据昂贵、稀缺、覆盖不全的问题。
3. `ML -> FEA`：用代理模型、降阶模型和特征提取加速高成本有限元计算，尤其是非线性、接触、塑性、大批量参数扫描问题。
4. `自然语言做仿真`：把工程问题、材料参数、载荷工况、验收指标转成可执行的仿真任务，并能解释设置依据。
5. `模型与数据管理`：管理材料模型、训练数据、Abaqus job、结果文件、云图、报告和历史版本，让每一次仿真都可追溯。
6. `智能分析与数据发现`：用聚类、降维、异常检测等无监督方法发现仿真结果中的模式，例如工况分群、失效区域、关键参数敏感性。

平台的底层逻辑是一条工程闭环：

```text
工程问题
-> 参数化有限元模型
-> 批量仿真数据
-> 特征提取与数据清洗
-> 机器学习/神经网络/代理模型
-> 快速预测或辅助决策
-> Abaqus 高保真验算
-> 可视化报告与模型入库
```

从产品形态上看，未来可以演进成三层：

1. `仿真执行层`：调用 Abaqus、pyLabFEA、后处理脚本和批量 job 管理。
2. `AI 模型层`：训练材料本构模型、代理模型、降阶模型、分类/聚类模型和结果预测模型。
3. `交互应用层`：提供桌面端或本地 Web App，支持自然语言建模、参数表单、结果可视化、报告导出和 LLM API 配置。

第一阶段不要直接追求完整平台，而是先做一个窄而完整的材料本构闭环：

```text
材料参数/仿真数据
-> pyLabFEA 生成或读取训练样本
-> 训练 ML/神经网络本构或屈服模型
-> Abaqus 单元级验算
-> 曲线、云图、误差指标、报告
-> 保存为材料模型资产
```

这个小闭环如果做扎实，后面就可以自然扩展到更大的方向：结构响应代理模型、非线性接触加速、工况聚类、参数优化、自然语言仿真助手和工程级模型管理。

我们当前学习 pyLabFEA 的意义，就是先掌握其中最可控的一块：材料本构、训练数据、屈服函数、Abaqus 验算。它会成为未来有限元 AI Workbench 的第一个可落地模块。

## 13. 已启动的第一版原型

已经新增目录：

```text
material_ai_workbench/
```

当前原型完成了一个最小但可运行的材料 AI 闭环：

```text
J2/Hill 参考材料
-> pyLabFEA 生成应力空间训练数据
-> SVC 训练机器学习屈服模型
-> 导出 Abaqus UMAT 参数 CSV/JSON
-> 输出屈服面图、摘要 JSON 和 Markdown 报告
```

运行示例：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name demo_j2
```

Hill 各向异性材料示例：

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material hill --name demo_hill --sy 50 --C 1.5 --gamma 1
```

如果需要同时运行 pyLabFEA 内部小有限元应力-应变曲线计算，可以增加：

```powershell
--with-curves
```

第一版输出位置：

```text
material_ai_workbench/runs/<时间戳>_<名称>/
```

每个 run 会包含：

- `summary.json`
- `reports/material_model_report.md`
- `figures/yield_locus.png`
- `figures/stress_strain_curves.png`
- `data/stress_strain_curves.csv`
- `models/abq_<材料名>-svm.csv`
- `models/abq_<材料名>-svm_meta.json`

已验证：

- J2 默认快速路径跑通。
- Hill 默认快速路径跑通。
- J2 带 `--with-curves` 的完整曲线路径已跑通。
- 原项目 `tests/test_basic.py` 通过。
- 原项目 `tests/test_ml.py` 通过。

当前原型暂时不自动提交 Abaqus job。下一步应接入 `examples/UMAT/ml_umat.f`、`femBlock.inp` 和 `calc_properties.py`，形成 Abaqus 单元级材料行为验算闭环。

## 14. Abaqus 单元级验算桥接已跑通

已经新增：

```text
material_ai_workbench/abaqus_bridge.py
```

它负责把 MaterialAI Workbench 的训练结果接入 pyLabFEA 的 Abaqus UMAT 示例：

```text
Workbench run
-> 读取 summary.json
-> 找到 models/abq_<材料名>-svm.csv/json
-> 准备 abaqus_verification 工作目录
-> 复制 femBlock.inp、ml_umat.f、calc_properties.py
-> 调用 Abaqus Python
-> Abaqus 编译 UMAT
-> Abaqus/Standard 求解
-> 读取 ODB
-> 输出 CSV、JSON、曲线图和桥接报告
```

已验证命令：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\20260702_165040_smoke_j2_fast --max-load-cases 1 --timeout-seconds 1200 --run
```

已验证结果：

- 状态：`completed`
- Abaqus/Standard job：`COMPLETED`
- UMAT 编译与链接：成功
- ODB 读取：成功
- NaN 计数：`0`
- 结果行数：`24`
- 最大 Mises：约 `59.9993 MPa`
- 最大 PEEQ：约 `0.00915636`
- 结果目录：

```text
material_ai_workbench/runs/20260702_165040_smoke_j2_fast/abaqus_verification/
```

关键输出：

- `bridge_summary.json`
- `abaqus_verification_report.md`
- `logs/abaqus_python.log`
- `results/abq_smoke_j2_fast-res.csv`
- `results/abq_smoke_j2_fast-res_meta.json`
- `results/abaqus_stress_strain_check.png`

这意味着第一条工程闭环已经成立：

```text
pyLabFEA 训练 ML 屈服模型
-> 导出 Abaqus UMAT 参数
-> Abaqus 单元级材料行为验算
-> ODB 后处理
-> CSV/曲线/报告
```

下一步可以把这个桥接入口接入 Streamlit App，形成按钮式操作：训练材料、准备 Abaqus 验算、运行 Abaqus、查看结果曲线和报告。

## 15. Streamlit 可视化 App 原型

已经新增：

```text
material_ai_workbench/streamlit_app.py
```

启动方式：

```powershell
conda run -n pylabfea streamlit run material_ai_workbench/streamlit_app.py --server.port 8501
```

当前 App 包含四个工作区：

1. `材料训练`
   - 选择 J2 或 Hill 参考材料
   - 输入弹性参数、屈服强度、Hill 比例
   - 设置 SVC 的 `C`、`gamma`、载荷方向数、采样序列
   - 一键调用 `run_material_workbench`
   - 自动生成训练报告、屈服面图和 UMAT 参数

2. `Abaqus 验算`
   - 选择已有训练 run
   - 准备 Abaqus 验算目录
   - 调用 Abaqus UMAT 单元验算
   - 输出 ODB 后处理 CSV、曲线图和桥接报告

3. `结果浏览`
   - 浏览已有 run
   - 查看训练 Accuracy、F1、MCC、支持向量数
   - 查看屈服面图、应力-应变图
   - 查看 Abaqus 验算状态、最大 Mises、最大 PEEQ
   - 预览 CSV 和 Markdown 报告

4. `模型管理`
   - 查看材料模板库
   - 加载或删除材料模板
   - 查看训练 run 历史
   - 汇总材料类型、屈服强度、训练指标、支持向量数和 Abaqus 状态
   - 查看当前选择 run 的 Abaqus 验算摘要

这个原型已经把命令行闭环转成了按钮式工程界面。下一步可以继续增强：

- 加入任务队列，避免 Abaqus 长任务阻塞界面。
- 增加真实实验曲线或 Abaqus 批量仿真数据导入。
- 增加神经网络代理模型训练页。
- 接入 LLM API，把自然语言仿真需求转成材料训练和 Abaqus 验算任务。

## 16. 材料库与模型管理已加入

已经新增：

```text
material_ai_workbench/material_library.py
material_ai_workbench/library/materials.json
```

这一步把 App 从单次训练工具推进到了“可管理资产”的雏形：

```text
材料模板
-> 加载到训练页
-> 训练 ML 屈服模型
-> 生成 run 历史
-> 可选 Abaqus 验算
-> 在模型管理页统一查看状态
```

当前材料库采用 JSON 文件保存，方便学习和调试。内置模板包括：

- `Demo_J2_60MPa`
- `Demo_Hill_sheet`

模型管理页当前可以查看：

- 材料模板名称、类型、E、nu、屈服强度、SVC 参数和备注
- 已训练 run 的材料类型、训练指标、支持向量数量和 Abaqus 验算状态
- 当前选中 run 的 Abaqus 验算摘要

这一步的意义是先把“材料模型资产”这个概念落地。后续再扩展时，可以自然演进到：

- 材料模板版本管理
- 真实实验曲线导入
- Abaqus 批量仿真数据入库
- 多个模型之间的误差对比
- 神经网络代理模型训练记录
- 面向简历和 GitHub 展示的项目级报告

## 17. 自然语言任务解析层 v0 已加入

本阶段不直接做完整桌面客户端，而是先做 `NL2Abaqus Task Layer`。目标是把用户的自然语言仿真需求转换成一个可审查、可确认、可执行的任务 JSON。

已经新增：

```text
material_ai_workbench/nl_tasks.py
```

Streamlit App 已新增 `AI 任务` 页面。第一版是规则版，不急着接真实 LLM API：

```text
自然语言输入
-> 规则/模板解析
-> 标准任务 JSON
-> 用户确认
-> 调用材料训练或 Abaqus 验算
-> 输出报告
```

当前已经支持从自然语言中解析：

- J2 / Hill 材料类型
- E、nu、屈服强度
- Hill r1-r6 各向异性比例
- SVC C、gamma
- 是否需要 Abaqus 单元验算
- Abaqus 验算载荷工况数

识别到 Abaqus 验算需求时，App 会要求额外勾选确认，避免自然语言误触发长时间求解。

等规则版继续稳定后，再把解析器替换或增强为多 LLM API 适配层。这样既能展示自然语言仿真能力，又不会让 LLM 直接失控操作 Abaqus。

当前四条原规划的真实进度：

1. `把本流程接入 Streamlit，形成可视化 App 原型`：已开始并基本跑通。
2. `增加 Abaqus job 提交与 ODB/CSV 读取`：已完成单元级 UMAT 验算桥接；完整任务队列和复杂模型管理未完成。
3. `加入真实材料曲线或 Abaqus 批量仿真数据导入`：未开始。
4. `在 SVM 屈服模型之外，增加神经网络代理模型实验`：未开始。

项目发布、中文文档和简历包装总纲见：

- `PROJECT_RELEASE_PLAN_CN.md`
- `docs/TECHNICAL_ARCHITECTURE_CN.md`
