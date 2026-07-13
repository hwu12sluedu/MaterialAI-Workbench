# 复合材料多尺度与有限元深度学习研究地图

资料来源包括：

- 本地截图：`D:\githubproject\composite`
- 论文与项目线索：RVE 均匀化、Abaqus PBC、复合材料失效准则、深度学习代理模型、迁移学习、PINN/物理约束神经网络。

## 本地截图提炼

| 截图 | 关键信息 | 对产品的要求 |
|---|---|---|
| `1333928944.jpg` | Abaqus 计算 RVE 等效属性、三维编织 RVE、fiber/interface/matrix 分解、界面结合 | 建立 RVE 数据结构、材料相定义、界面/cohesive 建模、等效属性提取 |
| `1554208420.jpg` | DNN、CNN、ResNet/DenseNet、多模态、3D CNN、PINN、迁移学习 | 代理模型不能只支持表格；必须支持曲线、图像、体素和物理损失 |
| `1854323870.jpg` | 缺口复合材料层合板的 allowable load space、FEM 数据、ensemble、transfer learning | 需要“旧案例预训练 + 新案例微调”的产品机制 |
| `411684140.jpg` | 体素化结构输入、3D CNN、ResNet-36 多模态网络、输出等效弹性参数 | 需要 RVE 体素/图像数据导入、结构特征编码和多输出回归 |
| `518673542.jpg` | Eshelby、RVE、网格划分、周期性边界、DNN/CNN/Domain Adaptation、Hashin/Tsai-Wu、Abaqus/Python 二次开发、TexGen | 教学体系必须覆盖理论、Abaqus 自动化、失效准则、TexGen/RVE |
| `520144789.jpg` | Python 生成纤维体积分数/随机分布、Abaqus 双重有限元模型 | 下一闭环案例可选“随机纤维 RVE -> Abaqus -> 等效参数 -> NN” |
| `634104067.jpg` | 迁移学习、归纳式迁移、Domain Adaptation、跨材料预测、TensorBoard | 产品需要模型版本、预训练权重、微调数据集、训练过程可视化 |
| `767112292.jpg` | 多相界面/cohesive、连续纤维 RVE、FE2/Direct FE2、批量数据生成 | 后续要支持复合材料批量数据生成和多尺度验证 |

## 关键论文与工具线索

| 方向 | 参考 | 可迁移到本项目的设计 |
|---|---|---|
| 缺口层合板迁移学习 | Li et al., 2024, *Composites Science and Technology*, DOI `10.1016/j.compscitech.2024.110432`，页面：[ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0266353824000022) / [XJTU Scholar](https://scholar.xjtu.edu.cn/en/publications/a-deep-transfer-learning-approach-to-construct-the-allowable-load/) | 建立“材料/几何/铺层/载荷 -> allowable load/失效因子”的迁移学习任务 |
| Abaqus RVE 周期性边界 | EasyPBC: *Development of an ABAQUS plugin tool for periodic RVE homogenisation*, DOI `10.1007/s00366-018-0616-4`，[Springer](https://link.springer.com/article/10.1007/s00366-018-0616-4) | 自动识别 RVE 面/边/角节点，生成 PBC 约束，输出等效刚度 |
| Abaqus 复合材料均匀化插件 | Spatium, *SoftwareX*, DOI `10.1016/j.softx.2025.102219`，[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352711025001864) | 粒子增强复合材料 RVE 生成、网格、PBC、后处理可作为产品模块参照 |
| 体素 RVE + 3D CNN | *Characterizing elastic constants of particulate composites using neural networks*, DOI `10.1093/jom/ufaf026`，[Oxford Academic](https://academic.oup.com/jom/article/doi/10.1093/jom/ufaf026/8242440) | 支持体素化 RVE 图像直接预测等效弹性常数 |
| 3D CNN 预测各向异性等效张量 | Wu et al., 2024, DOI `10.1016/j.cmpb.2024.108381`，[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0169260724003742) / [PubMed](https://pubmed.ncbi.nlm.nih.gov/39232375/) | 把 3D RVE 几何信息作为 CNN 输入，输出各向异性材料张量 |
| 编织复合材料 HPRNN | *Multiscale analysis of woven composites using hierarchical physically recurrent neural networks*, [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0045782526002124) | 先训练 yarn/matrix 微观代理模型，再嵌入宏观多尺度模型 |
| Abaqus 后处理接口 | Abaqus2Matlab, DOI `10.1016/j.advengsoft.2017.01.006`，[文档线索](https://www.researchgate.net/profile/George-Papazafeiropoulos/publication/338753842_Abaqus2Matlab_v30/data/63bc4ed3c3c99660ebdf508a/Documentation-fil.pdf) | 我们的 ODB/CSV 后处理需要保持可追溯、批量、可复现 |

## 对产品的架构要求

1. 数据层必须支持多模态：
   - 标量参数：材料常数、几何尺寸、载荷、边界条件。
   - 曲线：应力-应变、反力-位移、PEEQ 时间序列。
   - 图像：云图、DIC、显微结构图。
   - 体素/网格：RVE 几何、相分布、纤维随机分布。
   - 文本：案例说明、失败原因、工程经验。

2. 仿真层必须支持三类数据生产：
   - pyLabFEA 快速生成教学/算法验证数据。
   - Abaqus 单模型真实验证。
   - Abaqus 批量参数化生成训练样本。

3. 机器学习层必须分阶段：
   - v0：RandomForest/MLP 表格代理模型。
   - v1：曲线/时间序列代理模型。
   - v2：RVE 图像/体素 CNN。
   - v3：物理约束或 PINN 风格损失。
   - v4：迁移学习和领域自适应。

4. 工程验证层必须闭环：
   - 训练误差不能单独作为结论。
   - 每个模型版本必须关联 Abaqus 验证工况。
   - 报告必须给出数据来源、样本范围、误差、外推风险。

## 推荐的最小复合材料闭环题目

题目：随机圆形纤维 RVE 的等效弹性模量预测。

第一版只做 2D 平面应变：

```text
输入：纤维体积分数、纤维半径分布、随机种子、纤维/基体 E 与 nu
-> Python 生成 RVE 几何或体素图
-> Abaqus 批量求解单轴拉伸/剪切
-> 提取等效 E11/E22/G12/nu12
-> 训练 MLP baseline
-> 扩展到 CNN 输入体素图
-> 用新增样本验证迁移学习/主动学习
```

为什么适合作为下一阶段最小闭环：

- 和截图资料高度一致。
- 和 Abaqus 批量仿真、ODB 提取、代理模型天然衔接。
- 对机械工程背景友好，物理含义清晰。
- 能逐步升级到 3D、周期性边界、cohesive 界面、Hashin/Tsai-Wu 和 Direct FE2。
