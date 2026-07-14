# 自然语言服务配置（可选）

`仿真任务` 页面默认使用本地规则解析器，不联网，也不需要 API Key。外部语言模型只用于把更自由的描述转换为受约束的任务 JSON。

## 客户端配置

1. 打开 `仿真任务`。
2. 展开 `外部语言模型（可选）`。
3. 选择提供商预设或填写 OpenAI-compatible Base URL。
4. 填写模型名与 API Key，点击 `测试连接`。
5. 测试通过后保存到当前用户的本地配置。

Windows 客户端配置文件位于：

```text
%LOCALAPPDATA%\MaterialAIWorkbench\config\.env
```

源码安装则默认使用仓库根目录 `.env`。该文件已被 Git 忽略。

## 安全边界

- 未勾选允许外部调用时，不发送文本到模型服务。
- 模型只返回 JSON，不直接执行 Python、Shell 或任意 Abaqus 脚本。
- 任务 JSON 需要通过本地 schema 校验。
- Abaqus 提交还有独立确认开关。
- API Key 以本地配置保存，不进入案例数据集、报告或 GitHub 仓库。

## 支持接口

当前适配 OpenAI-compatible `/chat/completions`。内置预设包括 OpenAI、DeepSeek、通义千问、SiliconFlow 和本地 Ollama，也可以填写自定义兼容服务。

服务商的模型名、配额和接口规则可能变化，请以各服务商当前官方文档为准。
