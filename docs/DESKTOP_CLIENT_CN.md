# Windows 客户端使用与排错

## 1. 系统要求

- Windows 10/11 x64。
- 建议至少 8 GB 内存；训练和大批量数据处理建议 16 GB 以上。
- 基础功能不要求安装 Python。
- Abaqus 功能需要用户自己的 Abaqus 安装、许可证和可访问的命令路径。

客户端使用 Windows WebView 组件显示本地界面。若系统精简过或窗口组件损坏，可安装/修复 Microsoft Edge WebView2 Runtime 后重试。

## 2. 安装与启动

1. 从 GitHub Releases 下载 `MaterialAI-Workbench-Windows-x64-*.zip`。
2. 将整个压缩包解压到本地目录，例如 `D:\EngineeringTools`。
3. 打开解压得到的 `MaterialAIWorkbench` 文件夹，双击 `MaterialAIWorkbench.exe`。
4. 首次启动等待 20-60 秒；程序会自动寻找空闲的本机端口，不固定占用 8501。

不要只在压缩包预览窗口中双击 EXE。便携版的依赖文件位于 EXE 旁边，必须完整解压。

当前便携版尚未购买 Windows 代码签名证书，因此首次启动时 Windows Defender SmartScreen 可能显示“未知发布者”。请只从本项目的官方 GitHub Release 下载，先核对同版本 `.sha256` 文件；确认一致后，可选择“更多信息 > 仍要运行”。

## 3. 数据保存位置

程序与用户数据分离，升级时替换程序目录不会删除案例：

```text
%LOCALAPPDATA%\MaterialAIWorkbench\workspace
%LOCALAPPDATA%\MaterialAIWorkbench\config\.env
%LOCALAPPDATA%\MaterialAIWorkbench\logs\desktop.log
%LOCALAPPDATA%\MaterialAIWorkbench\logs\streamlit.log
```

建议定期备份 `workspace`。大型 ODB/CAE 文件由案例库索引，不强制复制到仓库或模型目录。

## 4. 首次使用检查

1. 打开 `材料训练`，使用默认 J2 参数完成一次训练。
2. 打开 `结果浏览`，确认曲线、指标和运行目录均可读取。
3. 打开 `数据导入`，导入一份 CSV 并检查列识别和数据质量提示。
4. 需要 Abaqus 时，再配置 `Abaqus 验算` 和 `Abaqus MCP`。
5. 打开 `案例库`，导入一个带 INP/STA/ODB/CSV 的真实案例并检查质量体检。
6. 打开 `带孔板批量`，先只准备 1 个样本；确认脚本后再允许真实求解。

## 5. Abaqus 连接

### 批处理/ODB 通道

在客户端中填写本机的：

```text
abaqus.bat
SMAPython.exe
```

路径因 Abaqus 版本和安装位置而异。客户端会在提交前检查文件是否存在，不会附带 Abaqus 可执行程序。

### CAE 实时通道

1. 打开 Abaqus/CAE。
2. 选择 `Plug-ins > Abaqus MCP > Start Socket Bridge`。
3. 在客户端 `Abaqus MCP` 页面测试连接。
4. 默认地址为 `127.0.0.1:48152`。

## 6. 自然语言服务

本地规则解析不联网，可直接使用。外部语言模型是可选项：

- API Key 只保存在当前用户的本地 `.env`。
- 每次外部调用和 Abaqus 提交都需要显式允许。
- 模型返回先转换为受约束的任务 JSON，再由本地代码校验。
- 当前不支持通过自然语言执行任意 Python 或 Abaqus 脚本。
- 引用历史案例时只发送无本地路径的结构化摘要；返回的 Case ID 必须来自本地检索结果。
- “历史案例复用工作区”只复制可编辑输入并生成差异单，不自动修改模型或提交 Job。

## 7. 常见问题

| 现象 | 检查方法 |
|---|---|
| 双击后没有窗口 | 等待 60 秒，查看 `logs\desktop.log`；确认压缩包已完整解压，修复 WebView2 Runtime |
| Windows 显示“未知发布者” | 核对下载来源和同版本 SHA256；当前便携版尚未进行商业代码签名 |
| 提示本地服务启动失败 | 查看 `logs\streamlit.log` 最后几十行；重新下载完整压缩包，不要混用不同版本文件 |
| 提示客户端已在运行 | 切回已有窗口；若异常退出，结束旧的 `MaterialAIWorkbench.exe` 后重试 |
| 页面显示服务器断开 | 关闭客户端后重新打开；确认安全软件没有阻止本机回环连接 |
| Abaqus 命令不存在 | 在设置中改为本机实际 `abaqus.bat` / `SMAPython.exe` 路径 |
| MCP 连接失败 | 确认 CAE 已启动 Socket Bridge，并核对主机和端口 |
| API 连接失败 | 先用“测试连接”，检查 Base URL、模型名、余额、网络和 Key 是否仍有效 |

## 8. 更新与卸载

更新时下载新版本，解压到新目录并启动即可。确认新版本正常后可删除旧程序目录。卸载程序只需删除便携目录；若也要删除个人数据，再手动删除 `%LOCALAPPDATA%\MaterialAIWorkbench`。
