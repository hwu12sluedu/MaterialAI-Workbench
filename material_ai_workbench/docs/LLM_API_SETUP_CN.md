# LLM API 配置与自然语言仿真使用说明

MaterialAI Workbench 当前支持 OpenAI-Compatible 的 `/chat/completions` 接口。LLM 的作用不是直接替代 Abaqus，而是把自然语言需求转换为本产品可执行的结构化任务 JSON，再由本地 Python/Abaqus 流程执行。

## 在 App 中配置

打开：

```text
http://localhost:8501/
```

进入 `AI 任务` 页面，展开 `LLM API（可选）`。

可用操作：

- `提供商`：选择 OpenAI、DeepSeek、通义千问、SiliconFlow、本地 Ollama 或自定义 OpenAI-Compatible 服务。
- `套用提供商预设`：自动填入 Base URL、默认模型和 API Key 环境变量名。
- `API Key`：可临时填写，也可点击保存写入本地 `.env`。
- `保存 LLM 配置`：写入项目根目录 `.env`，不会提交到 Git。
- `测试连接`：调用一次 LLM，并验证它能返回 MaterialAI 可解析的任务 JSON。
- `LLM 增强解析`：把自然语言需求转换为可执行任务。

## .env 示例

OpenAI：

```env
MATERIALAI_LLM_PROVIDER=openai
MATERIALAI_LLM_BASE_URL=https://api.openai.com/v1
MATERIALAI_LLM_MODEL=gpt-4.1-mini
MATERIALAI_LLM_API_KEY_ENV=OPENAI_API_KEY
MATERIALAI_LLM_REQUIRE_API_KEY=true
OPENAI_API_KEY=sk-...
```

DeepSeek：

```env
MATERIALAI_LLM_PROVIDER=deepseek
MATERIALAI_LLM_BASE_URL=https://api.deepseek.com/v1
MATERIALAI_LLM_MODEL=deepseek-chat
MATERIALAI_LLM_API_KEY_ENV=DEEPSEEK_API_KEY
MATERIALAI_LLM_REQUIRE_API_KEY=true
DEEPSEEK_API_KEY=...
```

本地 Ollama：

```env
MATERIALAI_LLM_PROVIDER=ollama
MATERIALAI_LLM_BASE_URL=http://localhost:11434/v1
MATERIALAI_LLM_MODEL=qwen2.5:7b
MATERIALAI_LLM_API_KEY_ENV=OLLAMA_API_KEY
MATERIALAI_LLM_REQUIRE_API_KEY=false
```

## 当前可执行的自然语言任务

### 1. 材料本构训练

示例：

```text
用 J2 金属材料，E=210000 MPa，nu=0.3，屈服 250 MPa，训练材料模型，输出应力应变曲线。
```

执行结果：

- 训练 pyLabFEA/SVC 材料屈服模型
- 输出屈服面、曲线、UMAT 参数 CSV/JSON
- 生成材料训练报告

### 2. 材料训练 + Abaqus UMAT 单元验算

示例：

```text
用 Hill 各向异性板材，E=70000 MPa，nu=0.33，屈服 180 MPa，r1=1.2 r2=1.0 r3=0.8 r4=1.0 r5=1.0 r6=1.0，训练材料模型，并跑 1 个 Abaqus 单元验算。
```

执行前需要勾选：

```text
允许本次任务调用 Abaqus
```

执行结果：

- 完成材料训练
- 准备 Abaqus UMAT 验算目录
- 调用 Abaqus 求解少量载荷工况
- 后处理 CSV 并生成验算报告

### 3. 复合材料 RVE + 3D 带孔板

示例：

```text
建立一个单向碳纤维复合材料微观 RVE，纤维体积分数 0.55，纤维 E=230000 MPa，基体 E=3500 MPa，生成 120x40x2 mm 的三维带孔板拉伸模型，孔半径 5 mm，应变 0.003，可以提交 Abaqus 求解。
```

如果不勾选 `允许本次任务调用 Abaqus`：

- 只生成微观 RVE、材料卡、Abaqus 建模脚本、预览图和报告。

如果勾选：

- 进一步调用 Abaqus/CAE 建模。
- 若 LLM 任务 JSON 中 `abaqus.submit_job=true`，还会提交求解 Job。

## 安全边界

LLM 只能生成当前产品支持的结构化任务。对于任意复杂几何、接触、多 Step 工艺仿真、真实 CAD 导入等需求，当前不会直接自动完成；系统会在 `warnings` 中说明能力边界。后续会逐步扩展为“案例库检索 + 相似案例复用 + Abaqus MCP 实时建模”的自然语言仿真客户端。
