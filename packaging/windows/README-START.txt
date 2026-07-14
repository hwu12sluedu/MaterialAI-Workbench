MaterialAI Workbench Windows 便携版
==================================

开始使用
1. 将整个压缩包解压到本地文件夹，不要只从压缩包内直接运行。
2. 打开解压得到的 MaterialAIWorkbench 文件夹，双击 MaterialAIWorkbench.exe。
3. 首次启动需要加载数值计算组件，通常需要 20-60 秒。

安全提示
- 当前便携版尚未购买 Windows 代码签名证书，首次启动可能显示“未知发布者”。
- 请只从项目官方 GitHub Release 下载，并核对随包发布的 SHA256 文件。
- 核对无误后，可在 SmartScreen 中选择“更多信息 > 仍要运行”。

使用要求
- 基础材料训练、数据导入、案例管理和结果浏览不要求安装 Python。
- 提交 Abaqus 作业需要用户自己的 Abaqus 安装与有效许可证。
- 连接已打开的 Abaqus/CAE，需要在 CAE 中启动 Abaqus MCP Socket Bridge。

本地数据
- 工作目录：%LOCALAPPDATA%\MaterialAIWorkbench\workspace
- 配置目录：%LOCALAPPDATA%\MaterialAIWorkbench\config
- 日志目录：%LOCALAPPDATA%\MaterialAIWorkbench\logs

排错
- 客户端关闭后会自动停止本地服务。
- 启动失败时先查看 logs\desktop.log 和 logs\streamlit.log。
- 软件不会随压缩包分发 Abaqus，也不会把本地 ODB、CAE 或 API Key 上传到 GitHub。

项目主页
https://github.com/hwu12sluedu/MaterialAI-Workbench
