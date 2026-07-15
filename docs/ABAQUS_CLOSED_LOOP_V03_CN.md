# Abaqus 三维带孔板闭环

本流程用一个几何简单但结果链完整的三维带孔板拉伸模型，验证 MaterialAI Workbench 是否真正完成了：参数输入、Abaqus 建模、Job 求解、ODB 提取、工程检查和案例归档。

## 1. 为什么选择这个算例

- 有圆孔应力集中，可检查局部场变量和 ROI 提取。
- 可使用弹塑性材料，能同时得到 `S`、`U`、`RF` 和 `PEEQ`。
- 三维实体模型与日常 Abaqus 工作方式一致，后续可替换为 Hill、Barlat、UMAT 或神经网络材料。
- 参数量适中，适合批量生成仿真训练样本。

## 2. 模型定义

默认配置：

| 项目 | 默认值 |
|---|---:|
| 长 × 宽 × 厚 | 100 × 50 × 5 mm |
| 孔半径 | 5 mm |
| 弹性模量 | 210000 MPa |
| 泊松比 | 0.30 |
| 初始屈服强度 | 250 MPa |
| 双线性切线模量 | 1000 MPa |
| 右端位移 | 0.35 mm |
| 网格尺寸 | 2.5 mm |
| 单元 | C3D10 |

左端面完全夹持，右端面施加轴向位移。模型建立 `FIXED_FACE`、`LOAD_FACE`、`LOAD_FACE_NODES`、`HOLE_ROI` 和 `ALL_ELEMENTS` 命名集。孔周局部特征从 `HOLE_ROI` 提取，反力从 `LOAD_FACE_NODES` 求和。

## 3. 状态含义

| 状态 | 含义 |
|---|---|
| `prepared` | 只生成配置、建模脚本、后处理脚本和启动脚本 |
| `built` | 已真实生成 CAE 和 INP，但未声称求解完成 |
| `solved` | ODB 存在，且求解阶段留下 `.sta/.msg/.dat/.log` 证据 |
| `postprocessed` | 已从 ODB 提取工程特征 |
| `validated` | 自动工程合理性检查通过 |
| `archived` | 已通过检查并写入案例库索引 |
| `blocked` / `failed` | 环境阻断或某一执行阶段失败 |

状态和证据保存在 `acceptance_manifest.json`。界面不能将 `prepared` 或 `built` 显示成已求解。

## 4. 客户端操作

1. 打开 `系统诊断`，确认 Abaqus 批处理为“就绪”。
2. 打开 `带孔板验证`，填写几何、材料、载荷和网格参数。
3. 先点“仅准备文件”，检查参数与脚本。
4. 勾选 Job 提交确认，再点“执行完整闭环”。
5. 在右侧检查阶段状态、ODB 特征和验收报告。
6. 中断后可选择原运行目录并点“恢复选中运行”。

`Abaqus 批处理`在独立进程执行，不修改当前打开的 CAE 会话。`Abaqus MCP`会连接当前 CAE，会话级操作必须在确认后使用。

## 5. 命令行

只准备：

```powershell
materialai-plate-hole --name plate_hole_review
```

完整求解并归档：

```powershell
materialai-plate-hole --name plate_hole_verified --execute --submit-job --archive-case --backend batch
```

恢复：

```powershell
materialai-plate-hole --resume "<acceptance_run_dir>" --execute --submit-job --archive-case
```

环境诊断：

```powershell
materialai-diagnostics --probe-commands
```

## 6. 输出

```text
acceptance_config.json        输入参数
acceptance_manifest.json      状态、证据与结果
acceptance_report.md          人可读验收报告
build_plate_hole.py           Abaqus/CAE 建模与 Job 脚本
extract_plate_hole.py         SMAPython ODB 提取脚本
run_plate_hole.ps1            可审查的手工启动入口
*.cae / *.inp / *.odb         Abaqus 工件
*.sta / *.msg / *.dat / *.log 求解证据
plate_hole_results.json       ODB 特征
plate_hole_results.csv        单行结果
plate_hole_features.csv       可进入机器学习数据集的特征行
```

## 7. 已验证基线

2026-07-15 使用 Abaqus 2023、4 CPU 和默认配置完成一次实机闭环：

| 指标 | 结果 |
|---|---:|
| 节点 / 单元 | 24232 / 14957 |
| 增量 / cutback | 22 / 0 |
| 最大 Mises | 300.0 MPa |
| 最大位移 | 0.35009 mm |
| 右端总反力 | 53691.3 N |
| 孔区最大 PEEQ | 0.07349 |
| 孔区塑性点占比 | 0.6801 |
| Mises / 毛截面名义应力 | 1.3969 |

该结果用于验证软件链路，不是通用设计结论。双线性材料在 5% 塑性应变处定义的 300 MPa 上限会影响 Mises 峰值；正式项目必须换成真实材料曲线并做网格收敛。

## 8. 后续机器学习接口

每次通过的算例产生一行 `plate_hole_features.csv`。后续参数扫描可以把以下内容作为输入：

- 几何：长、宽、厚、孔径；
- 材料：弹性、屈服、硬化或神经网络本构参数；
- 工况：位移、载荷路径；
- 数值：网格尺寸和单元类型。

目标可选最大应力、最大位移、反力、塑性区比例、应力集中比或允许载荷。训练前必须记录数据来源、网格层级和求解状态，失败或未验证样本不能混入标签数据。

## 9. 已知环境问题

部分 Abaqus 2023 SMAPython 环境在 `odb.close()` 时报告 `No module named _ctypes`。当前流程在特征已成功读取后把它记录为 `odb_close_warning`，不会丢弃已提取结果。

若 MCP 心跳成功但执行请求提示 `params.code must be a non-empty string`，说明 Python 2 插件只接受 `str` 而拒绝 JSON 解码后的 `unicode`。更新插件或使用接受 `basestring` 的修正版，然后重载插件或重启 Abaqus/CAE。
