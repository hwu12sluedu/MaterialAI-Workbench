# 案例智能 API

## `material_ai_workbench.case_package`

- `normalize_case_units(units, parameters=None)`：标准化显式单位声明，不猜测 Abaqus 单位。
- `fingerprint_file(path, size_bytes=None)`：普通文件完整 SHA256；大型文件使用有界采样指纹。
- `evaluate_case_quality(summary)`：返回执行状态、质量分、训练资格和阻断原因。
- `build_case_package(summary)`：构建 `case_package.json` v2 数据结构。
- `write_case_package(summary)` / `load_case_package(case_dir)`：持久化或读取案例包。

## `material_ai_workbench.case_intelligence`

- `rank_similar_cases(query_case, candidates, top_k=5, weights=None)`：输出分项可解释相似度。
- `search_cases_by_text(query, cases=None, cases_root=None, top_k=5)`：自然语言本地检索。
- `build_case_grounding_context(prompt, cases=None, cases_root=None, top_k=3)`：构建不含本地路径的 LLM 上下文。
- `grounding_provenance(context)`：提取附着在任务计划中的只读证据血缘。

## `material_ai_workbench.case_based_workflow`

- `prepare_case_based_plan(payload, cases_root=..., output_root=...)`：验证 Case ID、复制可编辑输入，并生成差异审查工作区。

该函数不会修改原案例、不会自动改写任意 INP，也不会提交 Abaqus。

## `material_ai_workbench.plate_hole_batch`

- `create_plate_hole_batch_plan(config=None)`：创建孔径、屈服强度和位移的笛卡尔批次。
- `load_plate_hole_batch_plan(plan_dir)`：读取持久化计划。
- `run_plate_hole_batch_plan(...)`：准备或恢复样本，可显式提交、归档、导出和训练。
- `batch_table_rows(plan)`：生成客户端与报告使用的状态表。

提交约束：`submit_jobs=True` 时必须同时设置 `execute=True`。训练约束：只有质量门合格且单位一致的案例进入代理模型。

## CLI

```text
materialai-case import|list|inspect|search|export
materialai-plate-hole-batch create|run|status
```

CLI 输出 JSON，适合 PowerShell、CI、桌面客户端和未来 MCP 服务复用。
