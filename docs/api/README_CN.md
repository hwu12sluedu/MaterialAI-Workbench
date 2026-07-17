# API 使用文档入口

API 文档分两层：

1. 自动清单：列出 `src/pylabfea` 和 `material_ai_workbench` 的公开函数、类和方法。
2. 使用指南：按业务流程说明应该调用哪些 API。

v0.4 案例包、可解释检索、历史案例约束和带孔板批量接口见
[案例智能 API](CASE_INTELLIGENCE_API_CN.md)。

## 生成自动 API 清单

```powershell
conda run -n pylabfea python tools/generate_api_inventory.py
```

输出：

```text
docs/api/API_INVENTORY_CN.md
```

每次新增函数、类或模块后都应该重新运行。

## API 学习顺序

1. 先读 `pylabfea.basic`：应力应变基础。
2. 再读 `pylabfea.material`：材料与屈服模型。
3. 再读 `pylabfea.model`：有限元模型。
4. 再读 `pylabfea.training`：训练样本生成。
5. 再读 `material_ai_workbench.pipeline`：产品化材料训练。
6. 再读 `material_ai_workbench.abaqus_bridge`：Abaqus 验证。
7. 再读 `material_ai_workbench.case_library`：案例库。
8. 再读 `material_ai_workbench.dataset_export` 和 `surrogate_model`：数据集与代理模型。

## API 稳定性约定

| 层级 | 稳定性 | 用法 |
|---|---|---|
| `src/pylabfea` | 上游学习库，尽量不改接口 | 用于学习和底层算法 |
| `material_ai_workbench` 顶层函数 | 当前产品服务层雏形 | 可以被 CLI、Streamlit、未来客户端调用 |
| 下划线开头函数 | 内部实现 | 不作为公开 API |
| 运行目录中的生成脚本 | 临时产物 | 不作为 API |

## 最小 API 调用样例

```powershell
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name api_doc_j2 --with-curves
```

Python 中调用：

```python
from material_ai_workbench.pipeline import WorkbenchConfig, run_material_workbench

config = WorkbenchConfig(material_type="j2", name="api_doc_j2")
summary = run_material_workbench(config)
print(summary.run_dir)
```
