# 功能软件测试清单

本清单用于 MaterialAI Workbench 发布候选的黑盒验收。每条测试都应记录版本、机器、时间、实际结果和证据路径。`P0` 失败阻断发布，`P1` 必须修复或形成书面豁免，`P2` 可进入后续版本。

## 1. 测试记录字段

| 字段 | 要求 |
|---|---|
| Test ID | 使用本清单固定编号 |
| Build | Git commit、版本号、ZIP SHA256 |
| Environment | Windows、CPU、内存、Abaqus 版本、许可证状态 |
| Result | Pass / Fail / Blocked / Not Run |
| Evidence | 截图、日志、JSON、CSV、CAE/INP/ODB 哈希 |
| Defect | 失败时关联缺陷编号和复测结果 |

## 2. 安装、启动与退出

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| INS-001 | P0 | 在干净 Windows 用户下解压便携 ZIP | 不要求 Python；文件完整，无路径错误 | 解压清单、SHA256 | 是 |
| INS-002 | P0 | 双击 EXE | 原生窗口打开，后台健康检查通过 | 启动日志、截图 | 是 |
| INS-003 | P0 | 程序目录设为只读后启动 | 用户数据仍写入 `%LOCALAPPDATA%` | 路径检查 | 是 |
| INS-004 | P0 | 连续启动两次 | 单实例策略生效，不产生两个后台服务 | 进程列表、日志 | 是 |
| INS-005 | P0 | 正常关闭窗口 | Streamlit 子进程随之退出，端口释放 | 进程与端口检查 | 是 |
| INS-006 | P1 | 强制终止后台后重启 | 客户端给出可理解错误并可恢复 | 日志、截图 | 是 |
| INS-007 | P1 | 安装路径含空格 | 可启动、可训练、可生成文件 | 日志 | 是 |
| INS-008 | P1 | Windows 用户名含中文 | 工作区可写，报告编码正常 | 路径与报告 | 否 |
| INS-009 | P1 | 首次启动无网络 | 核心本地功能可用，外部 LLM 显示未配置 | 截图 | 是 |
| INS-010 | P2 | 高 DPI 125%/150% | 导航、按钮、表格不重叠 | 截图 | 否 |

## 3. 工作区、配置与安全

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| CFG-001 | P0 | 首次运行 | 自动建立 workspace/config/logs | 目录树 | 是 |
| CFG-002 | P0 | 程序升级覆盖应用目录 | 用户案例、模型和配置不丢失 | 升级前后哈希 | 是 |
| CFG-003 | P0 | 配置无效工作区 | 系统诊断标记 blocked，不静默回退 | diagnostics.json | 是 |
| CFG-004 | P0 | Git/Release 内容扫描 | 不含 `.env`、API Key、用户 ODB/CAE | secret scan 报告 | 是 |
| CFG-005 | P0 | 日志中使用 LLM Key | Key 不得明文出现 | 日志扫描 | 是 |
| CFG-006 | P1 | 修改 Abaqus/MCP 环境变量 | 客户端和 CLI 使用同一配置 | diagnostics.json | 是 |
| CFG-007 | P1 | 工作区磁盘空间不足 | 写入失败可解释，不留下成功状态 | 错误报告 | 否 |
| CFG-008 | P1 | 配置文件损坏 | 启动不崩溃，给出恢复或重建提示 | 日志、截图 | 是 |

## 4. 材料训练

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| MAT-001 | P0 | 默认 J2 训练 | 训练完成，指标、模型、屈服面和报告存在 | summary、PNG、模型 | 是 |
| MAT-002 | P0 | 默认 Hill 训练 | 六个方向比值生效，不复现历史报错 | summary、测试日志 | 是 |
| MAT-003 | P0 | Hill 比值为 0/负值 | 输入被拒绝，错误指向具体字段 | 截图 | 是 |
| MAT-004 | P0 | 默认 Barlat 实验 | 训练完成并明确研究级边界 | summary、报告 | 是 |
| MAT-005 | P1 | Neo-Hookean | 输出应力曲线与参数卡，不调用 SVC | JSON、曲线 | 是 |
| MAT-006 | P1 | Mooney-Rivlin | 输出应力曲线与参数卡 | JSON、曲线 | 是 |
| MAT-007 | P0 | 相同随机种子重复训练 | 关键指标在容差内可复现 | 两次 summary diff | 是 |
| MAT-008 | P1 | 极小样本训练 | 报告提示样本不足，不夸大精度 | 报告 | 是 |
| MAT-009 | P1 | 保存并重新加载材料模板 | 参数完全一致 | 模板 JSON diff | 是 |
| MAT-010 | P1 | 删除材料模板 | 只删除选中项，其他模板不受影响 | 模板目录 | 是 |
| MAT-011 | P1 | pyLabFEA SVM 与 NN 基线 | 两条路径均输出模型与指标 | 模型、metrics | 是 |
| MAT-012 | P2 | 训练中途异常 | Run 状态为失败，已有证据保留 | run summary | 是 |

## 5. 数据导入

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| DAT-001 | P0 | 导入有效应力-应变 CSV | 单位、列映射和预览正确 | normalized CSV | 是 |
| DAT-002 | P0 | CSV 含 NaN/Inf | 明确报错并指出行列 | validation JSON | 是 |
| DAT-003 | P0 | 应变不单调 | 检测并拒绝或要求确认 | validation JSON | 是 |
| DAT-004 | P0 | 重复应变点 | 按规则处理并记录 | normalized CSV | 是 |
| DAT-005 | P1 | 单位为 Pa 而界面选择 MPa | 数值转换正确 | 前后对照 | 是 |
| DAT-006 | P1 | Abaqus 批量 CSV | 工况和样本来源不丢失 | import manifest | 是 |
| DAT-007 | P1 | 中文文件名与列名 | 导入、报告和预览编码正常 | 截图、CSV | 否 |
| DAT-008 | P1 | 大 CSV | 内存与响应时间在目标内 | 性能记录 | 是 |

## 6. Abaqus 诊断与 MCP

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| ABQ-001 | P0 | Abaqus 与 SMAPython 路径存在，MCP 未启动 | `batch_ready=true`、`mcp_ready=false`、overall partial | diagnostics.json | 是 |
| ABQ-002 | P0 | 两个执行路径均缺失 | overall blocked，给出环境变量提示 | diagnostics.json | 是 |
| ABQ-003 | P0 | 执行版本探测 | 返回 Abaqus 版本和 SMAPython 版本，不提交 Job | stdout evidence | 是 |
| ABQ-004 | P0 | 启动 v5 Socket Bridge 后检查 | ping 成功，端点与桥接版本正确 | telemetry | 是 |
| ABQ-005 | P0 | 读取当前模型与 Job | 返回模型名、Job 名和视口 | diagnostics.json | 是 |
| ABQ-006 | P0 | MCP 端口错误 | 快速超时并显示启动指引 | 错误文本 | 是 |
| ABQ-007 | P0 | ping 成功但 execute 拒绝 unicode | 诊断标记 live context warn，不误报 ready context | diagnostics.json | 是 |
| ABQ-008 | P1 | 设置 Abaqus 工作目录 | CAE cwd 更新且目录必须存在 | MCP 返回值 | 是 |
| ABQ-009 | P0 | 提交 Job 未勾确认 | 按钮禁用，不发送请求 | UI 录屏 | 是 |
| ABQ-010 | P0 | 提交已确认 Job | 状态来自 Job；失败时保留 `.sta/.msg` | MCP/Job 证据 | 否 |
| ABQ-011 | P1 | 停止并重启 Bridge | 客户端可重新连接，无需重启桌面端 | telemetry | 否 |
| ABQ-012 | P1 | 生成会话快照 | 写入用户工作区，不写安装包目录 | snapshot paths | 是 |
| ABQ-013 | P0 | GBK 控制台经 `conda run` 输出含替代字符的诊断 | CLI 输出保持 ASCII 安全 JSON；同时校验正文，不能只信退出码 | stdout、diagnostics.json | 是 |

## 7. 三维带孔板闭环

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| PH-001 | P0 | 仅准备默认算例 | 状态 prepared；配置、两脚本和 PowerShell 存在 | manifest | 是 |
| PH-002 | P0 | prepared 算例检查 | 不存在 ODB 时不得显示 solved | manifest | 是 |
| PH-003 | P0 | build-only | 生成 CAE/INP，状态 built，solve=skipped | manifest、文件哈希 | 实机 |
| PH-004 | P0 | 默认完整求解 | `.sta` 显示 completed，ODB 非空 | sta、ODB | 实机 |
| PH-005 | P0 | ODB 后处理 | 提取 Mises、U、RF、PEEQ、ROI 塑性比例 | results.json | 实机 |
| PH-006 | P0 | 工程检查 | 位移、反力、应力集中和 PEEQ 检查有明确结果 | manifest | 是 |
| PH-007 | P0 | 求解通过后归档 | 案例库出现 case_id，来源可追溯 | case_summary | 实机 |
| PH-008 | P0 | 求解中断后恢复 | 从原 run_dir 继续，不生成虚假新结果 | manifest 时间线 | 实机 |
| PH-009 | P0 | 后处理失败但 ODB 已成功 | solve 保持 pass，总体不得 archived | manifest | 是 |
| PH-010 | P1 | SMAPython close `_ctypes` 错误 | 特征保留，记录 odb_close_warning | results.json | 实机 |
| PH-011 | P0 | 孔径过大 | 参数校验拒绝 | 错误文本 | 是 |
| PH-012 | P0 | 网格大于孔半径 | 参数校验拒绝 | 错误文本 | 是 |
| PH-013 | P1 | 位移改变 | 最大位移与边界条件在容差内 | validation | 实机 |
| PH-014 | P1 | MCP 后端未连接 | 状态 blocked，不回退并伪装执行 | manifest | 是 |
| PH-015 | P1 | batch 后端且 CAE 正在打开 | 独立求解不改当前 CAE 模型 | 前后模型清单 | 否 |
| PH-016 | P1 | feature CSV | 一行参数和结果完整，可进入数据集 | CSV schema | 是 |

## 8. Job、ODB 与案例库

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| JOB-001 | P0 | 队列加入多个 INP | 顺序、CPU、超时和名称正确 | queue JSON | 是 |
| JOB-002 | P0 | Job 成功 | 状态 completed，返回码和日志保留 | queue history | 实机 |
| JOB-003 | P0 | Job 失败 | 状态 failed，可重试，不阻塞 UI | queue history | 是 |
| JOB-004 | P1 | 超时 | 进程终止、状态 timeout/failed、日志完整 | queue history | 是 |
| ODB-001 | P0 | 读取有效 ODB | Step、Frame、Field 和 Region 正确 | summary JSON | 实机 |
| ODB-002 | P0 | ODB 不存在 | 明确 FileNotFound，不生成空成功报告 | 错误证据 | 是 |
| ODB-003 | P1 | 指定 ROI | 提取值只来自目标集合 | 对照结果 | 实机 |
| ODB-004 | P1 | 多帧序列 | 帧数、时间和字段统计一致 | frame CSV | 实机 |
| CAS-001 | P0 | 导入包含 INP/ODB/报告的目录 | 文件分类和关键特征正确 | case_summary | 是 |
| CAS-002 | P1 | 重复案例 | 检出路径重复，不静默重复导入 | duplicate result | 是 |
| CAS-003 | P1 | 相似案例搜索 | 返回可解释的特征距离 | Top-N 结果 | 是 |
| CAS-004 | P0 | 导出训练集 | 行可追溯到 case_id 和源结果 | dataset manifest | 是 |

## 9. 代理模型与自然语言

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| ML-001 | P0 | Random Forest 基线 | 训练/验证划分、指标和模型文件齐全 | metrics、模型 | 是 |
| ML-002 | P0 | MLP 基线 | 指标和预测文件齐全，随机种子可复现 | metrics | 是 |
| ML-003 | P1 | 样本数不足 | 拒绝或警告，不给出误导性 R2 | 报告 | 是 |
| ML-004 | P1 | 多保真训练 | 低/高保真来源和残差模型可追溯 | manifest | 是 |
| ML-005 | P1 | 时间序列训练 | case/frame 索引不泄漏到验证集 | split report | 是 |
| NL-001 | P0 | 本地规则自然语言 | 无 API Key 时仍生成受限任务草案 | task JSON | 是 |
| NL-002 | P0 | LLM 返回非法 JSON | 校验失败，不执行 Abaqus | 错误证据 | 是 |
| NL-003 | P0 | LLM 请求任意命令 | schema/安全层拒绝 | 审计日志 | 是 |
| NL-004 | P0 | 有效任务但未确认 | 不提交 Job | UI 状态 | 是 |
| NL-005 | P1 | API 超时/限流 | 本地核心功能不受影响 | 日志、UI | 是 |
| NL-006 | P0 | 日志与报告 | API Key 不出现 | secret scan | 是 |

## 10. 发布门禁

| ID | 优先级 | 操作 | 预期结果 | 证据 | 自动化 |
|---|---|---|---|---|---|
| REL-001 | P0 | 快速单测 | 全部通过，无未解释失败 | pytest XML | 是 |
| REL-002 | P0 | 桌面源码 smoke | 健康检查通过并干净退出 | smoke log | 是 |
| REL-003 | P0 | 冻结客户端 smoke | EXE 可启动、关闭和清理后台 | frozen smoke log | 是 |
| REL-004 | P0 | wheel/sdist 检查 | build 与 twine check 通过 | build log | 是 |
| REL-005 | P0 | ZIP 内容审计 | 无开发缓存、workspace、密钥、ODB/CAE | artifact inventory | 是 |
| REL-006 | P0 | 版本一致性 | pyproject、模块、资源和 tag 一致 | version check | 是 |
| REL-007 | P0 | 文档链接 | MkDocs 构建通过，无失效内部链接 | mkdocs log | 是 |
| REL-008 | P1 | 首屏启动时间 | 在目标机器阈值内 | 性能记录 | 是 |
| REL-009 | P1 | 内存稳定性 | 连续操作后无持续泄漏趋势 | 监控记录 | 否 |
| REL-010 | P0 | 实机 Abaqus 门禁 | 至少一个 PH-004 至 PH-007 闭环通过 | 验收包 | 实机 |

## 11. 本轮实机结果

2026-07-15 默认三维带孔板算例已通过 `PH-001`、`PH-003`、`PH-004`、`PH-005`、`PH-006`、`PH-007`、`PH-010` 和 `PH-016`。该记录属于开发机验收证据，独立 QA 项目仍需在干净发布包和独立工作区重复执行。

同日 `0.3.0` 发布候选在独立 [MaterialAI-Workbench-QA](https://github.com/hwu12sluedu/MaterialAI-Workbench-QA) 中完成七套自动化门禁，共 `34 passed`、零失败、零跳过。覆盖 `ABQ-001`、`ABQ-003`、`ABQ-004`、`ABQ-005`、`ABQ-007`、`ABQ-013`、`REL-001`、`REL-002`、`REL-003`、`REL-004`、`REL-005`、`REL-006`、`REL-007` 和 `REL-010`。

独立 Abaqus/CAE 2023 实机验证确认 MCP v5.0.3 的 Python 2 `unicode` 修复生效：Bridge 心跳、模型、视口和 Job 上下文均可读取，`overall_status=ready`、`mcp_ready=true`。真实三维带孔板验收状态为 `archived`，最大位移 `0.35021 mm`、反力 `53.88 kN`、最大 Mises 应力 `300 MPa`、应力集中比 `1.3919`；ODB 为真实求解器输出。冻结 ZIP 的最终体积和 SHA256 以 GitHub Release 附件为准。
