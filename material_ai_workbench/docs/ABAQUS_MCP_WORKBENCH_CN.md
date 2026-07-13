# Abaqus MCP 实时连接工作台 — 使用指南

## 概述

Abaqus MCP（Material-CAE Protocol）是一个基于 TCP Socket 的实时桥接协议，让 MaterialAI Workbench 可以直接与运行中的 Abaqus/CAE 会话通信。通过这个桥接，你可以在 Web 界面中读取模型信息、提交 Job、提取 ODB 数据和抓取视口截图，无需手动切换窗口。

## 前置条件

1. **Abaqus/CAE 2023 或更高版本**（理论支持 2021+，但仅在 2023 上测试）
2. **Abaqus MCP 插件已安装**：插件文件 `abaqus_mcp_plugin.py` 需要放在 Abaqus 插件目录中
3. **Abaqus/CAE 已启动**并且已打开目标模型（可选，部分功能不需要）

## 启动 Bridge

在 Abaqus/CAE 中：

```
Plug-ins > Abaqus MCP > Start Socket Bridge
```

默认监听地址：`127.0.0.1:48152`

## 可用操作

### 连接检查
- 点击"检查连接"按钮 → 显示 Bridge 状态和基本遥测信息

### 模型信息
- 点击"读取模型" → 获取 Parts、Materials、Sections、Steps、Loads、BCs 等完整模型树

### Job 管理
- "读取 Job" → 列出当前工作目录下的所有 Job 及其状态
- "提交并等待 Job 完成" → 在显式确认后提交 Job，并监控其执行状态
- "监控 Job" → 读取 `.sta` / `.msg` 文件的尾部诊断信息

### ODB 读取
- "读取 ODB 元数据" → 打开本地 ODB 文件（只读），枚举 Steps、Frames、Field Outputs
- 提取最后帧的场变量统计（S/PEEQ/U/RF/CPRESS/COPEN 的 min/max/mean/max_abs）

### 视口操作
- "抓取当前视口" → 截取当前 Abaqus/CAE 视口的 PNG 图像
- 截图自动保存到 `mcp_sessions/` 目录

### 会话快照
- "生成会话快照" → 一次性收集：Bridge 状态 + 模型信息 + Job 列表 + 视口截图，生成 Markdown 报告

## 常见问题

### 连接失败（Connection Refused）
- 确认 Abaqus/CAE 已打开
- 确认插件已加载：检查 `Plug-ins > Abaqus MCP` 菜单是否存在
- 确认 Bridge 已启动：点击 `Start Socket Bridge`
- 检查防火墙是否阻止 48152 端口

### 操作超时
- 默认超时 10 秒。大模型或复杂 Job 的某些操作可能需要更长时间
- 可以在页面中调整超时参数

### Abaqus 窗口冻结
- 长时间执行的 Python 脚本可能会短暂冻结 Abaqus/CAE 的 GUI
- 设计原则：短脚本状态读取应保持低延迟（< 500ms）
- 如遇到持续冻结，在 Abaqus 中按 Ctrl+Break 中断 Python 执行

### 无法连接到远程 Abaqus
- MCP 默认仅监听 `127.0.0.1`（本地回环）
- 如需远程连接，修改 Abaqus MCP 插件中的 host 为 `0.0.0.0`
- 注意安全风险：远程连接无认证机制，仅适用于受控网络

## 协议概述

- **传输层**：TCP Socket
- **消息格式**：JSON，每条消息以换行符 `\n` 分隔
- **请求结构**：`{"id": "<uuid>", "method": "<method_name>", "params": {...}}`
- **响应结构**：`{"id": "<uuid>", "result": {...}}` 或 `{"id": "<uuid>", "error": "<message>"}`
- **超时**：客户端默认 10 秒超时
