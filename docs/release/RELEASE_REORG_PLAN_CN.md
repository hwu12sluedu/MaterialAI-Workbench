# 发布前项目重组方案

目标：把当前工作区整理成可公开发布、可持续开发、可解释、可测试的 GitHub 项目。

## 目标顶层结构

建议公开仓库最终结构：

```text
material-ai-workbench/
  README.md
  LICENSE
  pyproject.toml
  environment.yml
  mkdocs.yml
  src/
    pylabfea/
    material_ai_workbench/
  apps/
    streamlit_app.py
  examples/
    umat_minimal/
    rve_minimal/
    sample_cases/
  docs/
    index.md
    learning/
    api/
    release/
    00_project_status/
  tests/
  tools/
  schemas/
  configs/
    default.yaml
  workspace.example/
    README.md
```

当前项目中 `material_ai_workbench` 还在根目录，生产化后建议迁入 `src/material_ai_workbench`，并用入口脚本启动 App。

## 数据目录策略

源码仓库只保存：

- 小型 demo 输入。
- 小型 demo 输出截图。
- 可复现脚本。
- 文档需要的最小样例。

不保存：

- 大型 ODB。
- CAE 文件。
- 批量运行全量结果。
- 个人真实工程数据。
- API Key。
- 本地绝对路径配置。

运行数据默认写入：

```text
workspace/material_ai_workbench/
  runs/
  batches/
  cases/
  datasets/
  surrogates/
  imports/
  logs/
  reports/
```

## 配置管理

新增：

```text
configs/default.yaml
configs/local.example.yaml
```

配置项：

- 工作目录。
- Abaqus 路径。
- SMAPython 路径。
- MCP host/port。
- 默认字段：S/PEEQ/U/RF/CPRESS/COPEN。
- 默认 LLM provider。
- 默认模型输出目录。

禁止：

- 把 API Key 写入配置样例。
- 把个人绝对路径写入公开默认配置。

## `.gitignore` 必须覆盖

```gitignore
workspace/
*.odb
*.cae
*.sim
*.prt
*.pkl
*.log
*.sta
*.msg
*.dat
*.lck
__pycache__/
.pytest_cache/
.ipynb_checkpoints/
site/
build/
dist/
*.egg-info/
.env
```

## 重组步骤

1. 建立干净 Git 仓库。
2. 复制源码与文档，不复制运行数据。
3. 把 `material_ai_workbench/*.py` 迁到 `src/material_ai_workbench`。
4. 把 Streamlit 入口迁到 `apps/streamlit_app.py`。
5. 更新 import 路径和入口命令。
6. 增加 `configs/default.yaml`。
7. 增加 `workspace.example/README.md`。
8. 放入最小 demo 数据。
9. 运行测试。
10. 运行文档生成与发布审计。

## 不能立即删除的内容

当前工作区不是 Git 仓库，所以不能直接批量删除历史产物。正确做法：

1. 先运行审计：

```powershell
conda run -n pylabfea python tools/release_audit.py
```

2. 复制到干净发布仓库。
3. 在发布仓库中只保留白名单文件。
4. 原工作区作为本地实验工作区继续保留。

## 发布 Gate

发布前必须全部通过：

```powershell
conda run -n pylabfea python tools/generate_api_inventory.py
conda run -n pylabfea python tools/release_audit.py
conda run -n pylabfea python -m pytest tests -q
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name release_smoke_j2 --with-curves
```

有 Abaqus 时再跑：

```powershell
conda run -n pylabfea python -m material_ai_workbench.abaqus_bridge --run-dir material_ai_workbench\runs\<release_smoke_j2> --max-load-cases 1 --run
```
