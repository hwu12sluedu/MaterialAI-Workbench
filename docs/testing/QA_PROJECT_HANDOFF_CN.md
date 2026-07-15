# 独立功能测试项目交接说明

后续单独建立 `MaterialAI-Workbench-QA` 仓库。它面向发布包做黑盒测试，不直接导入 `material_ai_workbench` 源码，避免“用产品内部实现证明产品自己正确”。

## 1. 项目目标

- 验证 Windows 便携包的安装、启动、退出和升级。
- 通过浏览器协议测试桌面壳内部的 Streamlit 功能。
- 通过 CLI 和生成工件验证材料、Abaqus、ODB、案例库与代理模型。
- 用模拟 MCP Bridge 覆盖断线、超时、非法返回和 Job 状态。
- 在带 Abaqus 许可证的自托管 Windows Runner 上执行实机门禁。
- 输出 HTML/JUnit 报告和可归档证据包。

## 2. 建议目录

```text
MaterialAI-Workbench-QA/
  pyproject.toml
  README.md
  config/
    environments.example.toml
  contracts/
    diagnostics.schema.json
    acceptance_manifest.schema.json
  fixtures/
    csv/
    inp/
    manifests/
    fixture_registry.json
  src/materialai_qa/
    app_process.py
    artifact_assertions.py
    fake_mcp_bridge.py
    release_installer.py
  tests/
    unit/
    cli/
    ui/
    release/
    abaqus_real/
  evidence/
  reports/
```

`contracts/`从产品仓库 `schemas/`同步，并固定到被测版本。QA 仓库只依据公开 CLI、HTTP 页面、文件格式和 Schema 判断结果。

## 3. 测试技术栈

| 层 | 工具 | 用途 |
|---|---|---|
| Python 测试 | pytest | CLI、文件、状态机和错误恢复 |
| UI 黑盒 | Playwright | Streamlit 页面、输入、按钮和表格 |
| Schema | jsonschema | diagnostics/acceptance manifest 合同 |
| 进程 | psutil | EXE、子进程、端口和退出清理 |
| 报告 | pytest-html、JUnit XML | 人读报告和 CI 门禁 |
| Windows 原生窗口 | pywinauto 或 Appium Windows | 最小窗口生命周期检查 |
| Abaqus 实机 | 自托管 Windows Runner | build、solve、ODB、resume、archive |

## 4. 测试配置

定义四种 profile：

| Profile | Python | Abaqus | 网络 | 用途 |
|---|---|---|---|---|
| `portable-offline` | 不要求 | 无 | 关闭 | 安装包核心功能 |
| `source-mock` | 有 | Fake MCP | 可选 | 快速回归与故障注入 |
| `portable-abaqus` | 不要求 | Abaqus 2023 | 关闭 | 发布包实机闭环 |
| `source-llm` | 有 | 可选 | 有 | 外部模型适配器契约 |

实机 Abaqus 测试必须显式标记 `abaqus_real`，普通 GitHub 托管 Runner 不执行。

## 5. 测试数据合同

`fixture_registry.json`至少记录：

```json
{
  "fixture_id": "plate-hole-default-v1",
  "source": "generated-by-qa",
  "sha256": "...",
  "units": "mm-N-MPa",
  "expected": {
    "status": "validated",
    "max_displacement_mm": {"min": 0.315, "max": 0.438},
    "reaction_force_n": {"min": 1.0}
  }
}
```

大型 ODB 不直接提交 Git。实机测试现场生成 ODB，并把输入、版本、哈希、`.sta`、结果 JSON 和精简截图放入 evidence。任何第三方 ODB 必须确认许可和脱敏。

## 6. Fake MCP Bridge

模拟服务应覆盖：

1. 正常 `ping` 和 `execute`。
2. 连接拒绝。
3. 响应超时。
4. response id 不匹配。
5. 非法 JSON。
6. Abaqus kernel 执行异常。
7. Job 从 submitted 到 completed/aborted 的状态序列。
8. Python 2 `unicode` 执行参数兼容回归。

Fake Bridge 只验证客户端协议和错误处理，不代表 Abaqus 求解通过。

## 7. CI 与发布门禁

普通 CI：

```text
contracts -> CLI mock -> UI mock -> portable smoke -> artifact audit
```

发布候选自托管门禁：

```text
download release asset -> verify SHA256 -> clean workspace -> portable smoke
-> Abaqus diagnostics -> plate-hole build -> solve -> ODB extract
-> schema validation -> evidence bundle -> release decision
```

门禁规则：

- 任一 P0 失败则 Release Candidate 不通过。
- 不得只依据进程退出码判定通过；还要检查 stdout/stderr、预期工件、版本资源和日志中的成功标记。
- EXE smoke 必须有外层硬超时，并在超时后确认整个子进程树和监听端口均已清理。
- ZIP 必须校验 SHA256，并扫描 workspace、`.env`、缓存、测试代码、ODB/CAE 和疑似密钥。
- Abaqus 未获得许可证记为 `Blocked`，不能记为 `Pass`。
- `prepared`、`built`、`solved`、`validated` 必须严格区分。
- 实机结果容差按物理量定义，不能用截图相似度代替数值检查。
- 发布证据包不得含 API Key、公司客户数据或未经授权的模型。

## 8. 首个独立迭代

1. 建仓并固定产品 `v0.3.0` Schema。
2. 实现 ZIP 下载、SHA256、版本资源、内容清单和 EXE 启动/退出清理。
3. 实现 Fake MCP Bridge。
4. 自动化 `INS-*`、`CFG-*`、`ABQ-001/002/006/007/012`。
5. 自动化 `PH-001/002/006/011/012/014/016`。
6. 接入 Playwright 覆盖“系统诊断”和“带孔板验证”。
7. 配置自托管 Abaqus Runner 执行 `PH-003` 至 `PH-010`。
8. 生成 `reports/index.html` 和 `evidence/<build-id>.zip`。
9. 注入 PyInstaller 失败、错误 DLL、启动弹窗和无限等待，验证失败产物不会被保留或发布。

产品仓库继续负责白盒单测；QA 仓库负责用户视角和发布包证据，两者不能互相替代。
