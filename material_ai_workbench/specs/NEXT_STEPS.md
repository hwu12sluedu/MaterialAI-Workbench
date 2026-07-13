# MaterialAI Workbench — Next Steps

Generated 2026-07-03 after a full project audit (941 files, 21 core modules).
Feed this file directly to an AI coding agent.

---

## What Was Fixed During This Audit

| Fix | File | What |
|-----|------|------|
| Horizontal jitter in Abaqus panel | `streamlit_app.py:1018-1064` | Column ratio changed, long paths use `st.caption`, duplicate `_show_abaqus_summary` removed, buttons given `key=` |
| `Path("").exists()` crash | `streamlit_app.py:1710-1712` | `preview_plot` empty-string guard before `Path()` construction |
| ODB candidates too narrow | `streamlit_app.py:1745` | `_find_odb_candidates` now searches runs/ tree + all case directory sources, not just `abaqus_verification/` |
| Long path `st.write` jitter | `streamlit_app.py` lines 138, 402, 499-500, 1013 | Changed to `st.caption` with backtick wrapping (word-breaks) |

---

## Remaining Bugs — Fix These First

### Priority 1: Crashes and Data Corruption

| # | File:Line | Bug | Fix |
|---|-----------|-----|-----|
| 1 | `case_library.py:557` | `result_features["summary"]["odb_files"]` stores **relative paths** as strings, but `_case_odb_options` expects **absolute path dicts**. ODB files from scanned cases may not appear in extraction dropdown. | Change line 557 from `[item["relative_path"] for item in odb_files]` to `[item["path"] for item in odb_files]` (absolute paths) |
| 2 | `abaqus_bridge.py:236-249` | `_patch_calc_properties` uses `\n` in `.replace()` calls. On Windows, if `calc_properties.py` has `\r\n` line endings, ALL patches FAIL silently. Abaqus will run the unpatched script and fail mysteriously. | Normalize line endings before patching: `text = text.replace("\r\n", "\n")` then do replacements, then restore `\r\n` if needed. OR use regex that matches both `\r?\n`. |
| 3 | `streamlit_app.py:1789-1792` | `_run_table_rows` silently swallows corrupted `bridge_summary.json` — sets `abaqus_status = "read_error"` with no logging or user feedback. Runs disappear from history silently. | Add `import logging; _log = logging.getLogger(__name__)` at module top. Add `_log.warning("Failed to read %s: %s", bridge_path, exc)` before setting `abaqus_status = "read_error"`. |

### Priority 2: Robustness

| # | File:Line | Bug | Fix |
|---|-----------|-----|-----|
| 4 | `pipeline.py:34` + `run_workbench.py:58` + `run_composite_workflow.py:51` + `run_composite_batch.py:58` | Default output paths are CWD-relative strings like `Path("material_ai_workbench/runs")`. If the process is launched from a different directory, output goes to the wrong place. | Import from `config.py` and use `RUNS_ROOT`/`COMPOSITE_ROOT`/etc. Change defaults to `None` and resolve inside the function using config values. |
| 5 | `composite_workflow.py:23-24` | Hardcoded `D:/ABAQUS/2023/...` path (same as the already-fixed `abaqus_bridge.py`). | Replace with `from material_ai_workbench.config import ABAQUS_BAT, ABAQUS_SMAPYTHON` |
| 6 | `abaqus_bridge.py:252-257` | `material_name` is interpolated directly into PS1 script. Name with spaces (e.g. "test material") breaks the command line. | Wrap in single quotes: `'{material_name}'`. Also sanitize single-quotes: `material_name.replace("'", "''")` |
| 7 | `abaqus_bridge.py:322-328` | `_postprocess_result_csv` uses hardcoded column names `PEEQ`, `MISES`, `E11`, `S11`. If Abaqus version changes column naming, `KeyError` crashes the entire verification. | Use `.get()` with graceful fallback: if a column is missing, skip that plot, log warning, don't crash. |
| 8 | `batch_simulation.py:49-51` | `@property samples` uses `dict.setdefault()` which **mutates** the data dict on READ. Reading `plan.samples` permanently inserts `"samples": []` if absent. | Change to `return self.data.get("samples", [])` (no mutation). Add a separate `ensure_samples()` method for the one place that writes. |
| 9 | `case_library.py:618-619` | `_try_float` removes commas when both `,` and `.` are present — corrupts European-style `1.234,56` (1234.56) into `123456`. | Check if comma is AFTER the last period (European decimal), then replace `.` → `""` and `,` → `.`. If period is after the last comma (English thousands), keep current behavior. |
| 10 | `composite_workflow.py:1102-1111` | `shell=True` with `capture_output=True` can deadlock on Windows when subprocess produces >4KB output. | Switch to list-form command: `[str(abaqus_bat), "cae", f"noGUI={script}"]` without `shell=True`. |

### Priority 3: UI Polish (streamlit_app.py)

| # | Line(s) | Issue | Fix |
|---|---------|-------|-----|
| 11 | ~26 locations | Buttons without `key=` parameter risk `DuplicateElementId` errors. Most critical: lines 822 and 1552 both have label "加载到训练页". | Add unique `key=` to every `st.button()` call. Pattern: `key="case_scan"`, `key="mcp_check"`, etc. |
| 12 | 142 | 11 tabs overflow horizontal space on laptop screens. Sidebar is unused (only has one run selector). | Move navigation to `st.sidebar` as `st.radio`. Main area shows only the selected page. |
| 13 | 496, 542, 556, 570, 587, 591, 957, 1175, 1247, 1503, 1521, 1832, 1883 | 13 `st.dataframe()` calls without `height` parameter. Tables with many rows stretch the page indefinitely. | Add `height=400` to every `st.dataframe()` call. |
| 14 | 281-332 | Training panel left column has 4 form sections stacked without dividers — visually cramped. | Add `st.divider()` between each logical section. |
| 15 | 1053-1090 | Composite panel has ~20 number inputs in a 38%-width column without sub-group labels. | Add `st.caption("纤维属性")`, `st.caption("基体属性")`, `st.caption("界面")`, `st.caption("RVE 网格")` between input groups. |
| 16 | 1249 inside 1191 | Nested expander (composite_dataset.csv inside 复合材料批量数据). | Remove inner expander; render CSV preview directly inside the outer expander. |
| 17 | 834-835 | English labels "Bridge host" / "Bridge port" in an otherwise Chinese UI. | Change to "Bridge 主机地址" / "Bridge 端口". |
| 18 | 1038-1041, 267-270 | `st.warning` used for both terminal failure ("failed") and in-progress ("running"). | Use `st.error` for "failed"/"timeout", `st.warning` for non-terminal, `st.info` for "not invoked". |

### Priority 4: Dead Code Cleanup

| # | File | Issue | Action |
|---|------|-------|--------|
| 19 | `task_queue.py` | Never imported by any consumer. In `__all__` but never used. | Remove from `__init__.py` or integrate into `streamlit_app.py`. |
| 20 | `time_series_surrogate.py` | Never imported. | Remove from `__init__.py` or integrate into surrogate UI. |
| 21 | `param_recommender.py` | Never imported. | Remove from `__init__.py` or integrate into AI Task panel. |
| 22 | `logging_config.py` | Imported by some modules but `streamlit_app.py` is the primary user and doesn't use it. | Add `from material_ai_workbench.logging_config import get_logger` to `streamlit_app.py`. Replace `print()` debug lines with `logger.info()`. |

---

## Feature Roadmap (After Bugfixes)

### Milestone 1: Engineering Foundation (1 week)
- Initialize git repo with `.gitignore`
- Create `environment.yml` / `requirements.txt` so others can install
- Write minimal pytest suite (`tests/test_pipeline.py`, `tests/test_nl_tasks.py`)
- Create the two missing docs files (`docs/ABAQUS_MCP_WORKBENCH_CN.md`, `docs/CASE_LIBRARY_USER_GUIDE_CN.md`)

### Milestone 2: ML Quality (1 week)
- Add K-fold cross-validation to `surrogate_model.py` (currently single holdout only)
- Add uncertainty quantification (ensemble std or quantile regression for RF predictions)
- `data_import.py`: validate imported curves (monotonic strain, positive stiffness, sanity checks)

### Milestone 3: Material Models (1-2 weeks)
- Add Barlat Yld2000-2D yield criterion support in `pipeline.py` and UI
- Add experimental curve -> material training path (import CSV → estimate E and sy → train model)
- Add hyperelastic entry point (Neo-Hookean, Mooney-Rivlin) if pyLabFEA supports it

### Milestone 4: Abaqus Workflow (1-2 weeks)
- Build job queue in `streamlit_app.py` (submit Abaqus jobs without blocking UI)
- Async ODB extraction queue (batch extract all ODBs without freezing the UI)
- Similar case search in case library (cosine similarity on INP features)

### Milestone 5: Packaging (1 week)
- `pyproject.toml` for pip-installable package
- Docker image for non-Abaqus workflows (training + visualization)
- GitHub Actions CI (pytest + lint on PR)

---

## How to Use This File

Feed to an AI agent with this prompt:

```
Read D:\githubproject\pyLabFEA\material_ai_workbench\specs\NEXT_STEPS.md.
Start with the "Remaining Bugs" section, Priority 1.
Fix each bug in order, verifying with the described acceptance criteria before moving on.
After all Priority 1-4 bugs are fixed, proceed to Milestone 1.
```

Each bug/fix entry includes the exact file path, line numbers, root cause, and the specific code change needed.
