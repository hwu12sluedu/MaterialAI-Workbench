# MaterialAI Workbench 中文文档中心

这是 MaterialAI Workbench 的中文文档入口。项目由两层组成：

1. `pyLabFEA`：轻量有限元、弹塑性材料、等效应力、机器学习屈服函数、均匀化与复合材料教学代码库。
2. `material_ai_workbench`：在 pyLabFEA 之上新增的工程化工作台，用于材料本构训练、Abaqus UMAT 验证、案例库、ODB/CSV 后处理、批量仿真、代理模型训练和闭环报告。

![MaterialAI Workbench 客户端](assets/materialai-workbench-app.png)

## 最终产品目标

我们要做的不是单一脚本，而是一个面向机械/仿真工程师的本地 CAE + AI 工作台：

```text
日常 Abaqus 案例
-> 案例库归档
-> INP/ODB/CSV/云图/日志/报告特征提取
-> 材料本构训练与有限元代理模型训练
-> Abaqus 真实模型验证
-> 自然语言生成可审查任务 JSON
-> 用户确认后批量运行 Abaqus
-> 自动后处理、报告、数据回写和模型迭代
```

## 今天形成的文档系统

- `docs/00_project_status/`：项目体检、里程碑、任务池、复合材料研究地图。
- `docs/learning/`：从 pyLabFEA 源码/notebook 学到有限元深度学习模型的闭环教程。
- `docs/api/`：可执行 API 使用文档和自动生成的公开函数/类清单。
- `docs/release/`：GitHub 发布前的目录重组、清理、打包和验收流程。
- `tools/`：文档维护工具，当前包括 API 清单生成和发布审计。

## 常用命令

```powershell
conda run -n pylabfea python tools/generate_api_inventory.py
conda run -n pylabfea python tools/release_audit.py
conda run -n pylabfea python -m pytest tests material_ai_workbench/tests -q -m "not slow"
conda run -n pylabfea streamlit run material_ai_workbench/streamlit_app.py --server.port 8501
```

如果安装了 MkDocs Material，可以本地预览文档：

```powershell
conda run -n pylabfea python -m pip install mkdocs mkdocs-material
conda run -n pylabfea mkdocs serve
```
