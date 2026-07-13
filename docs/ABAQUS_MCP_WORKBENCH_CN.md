# Abaqus MCP Workbench 中文使用指南

## 目标

MaterialAI Workbench 的 Abaqus MCP 层用于连接当前打开的 Abaqus/CAE 会话，让后续 AI 客户端可以读取模型、管理工作目录、提交 job、查看状态、抓取视口截图，并与本地批处理 ODB 提取互补。

## 启动步骤

1. 打开 Abaqus/CAE。
2. 菜单执行 `Plug-ins > Abaqus MCP > Start Socket Bridge`。
3. 确认控制台出现 `Abaqus MCP socket bridge listening on 127.0.0.1:48152`。
4. 打开 Streamlit App 的 `Abaqus MCP` 页面。
5. 点击连接检查，确认 bridge 可访问。

## 当前能力

- 连接状态检查。
- 设置 Abaqus 当前工作目录。
- 获取当前模型信息。
- 列出 job。
- 提交选中的 job 并轮询状态。
- 抓取当前视口截图。
- 生成会话快照，便于后续报告和案例归档。

## 与批处理 ODB 的关系

MCP 适合实时交互，例如查看当前窗口、当前模型、当前 job。批处理 `SMAPython.exe` 适合在后台读取 ODB 结果，尤其是 Abaqus/CAE 没有加载当前 ODB 或需要批量提取帧曲线时。

## 常见问题

- MCP 未连接：确认 Abaqus/CAE 已打开，并已启动 Socket Bridge。
- 端口不一致：检查 App 里的 host/port 是否为 `127.0.0.1:48152`。
- Abaqus 窗口卡住：优先使用新版插件；长时间任务应走 job 队列或 SMAPython 批处理，不要在 UI 中执行大段阻塞脚本。
- 无法读取 ODB：检查 ODB 是否被求解器占用，或改用批处理提取。
