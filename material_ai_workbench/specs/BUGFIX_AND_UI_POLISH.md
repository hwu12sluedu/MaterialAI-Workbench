# Bug Fixes & UI Polish

## Objective
Fix the 28 bugs and 22 UI/UX issues discovered in the 2026-07-03 audit. This spec is designed to be executed BEFORE the Phase 1-6 feature work.

## Prerequisites
- Phase 0 (git + config.py) should be done first, since Task B1 below depends on `config.py` existing.

---

## B0 — Horizontal Jitter in Abaqus Verification Panel (FIXED in streamlit_app.py)
**Severity:** HIGH  
**File:** `streamlit_app.py`, `_abaqus_panel()`, lines 1018-1064

### Root Cause (5 combined issues)
1. `st.write(str(result.work_dir))` at line 1053: long unbroken path string has no spaces → cannot word-wrap → forces horizontal scrollbar in the 42% column. On next rerun, scrollbar disappears. This cycle IS the jitter.
2. `_show_abaqus_summary()` called **twice** at lines 1062+1064 when `run_clicked`: full summary renders for both `result.work_dir` and `run_dir / "abaqus_verification"` (same directory). Doubled content triggers layout oscillation.
3. `st.error(f"Abaqus 可执行文件不存在: {abaqus_bat}")` at line 1039: 40-char path embedded in error → same no-wrap overflow.
4. `st.text_input` with 40-char default path at line 1025 in a narrow 42% column → text input width exceeds column → horizontal overflow.
5. Column ratio `[0.42, 0.58]` too tight for the left-column content.

### Fix Applied
- Changed column ratio to `[0.5, 0.5]`
- `st.write(str(result.work_dir))` → `st.caption(f"工作目录: \`{path}\`")` (backtick-wrapped text word-wraps)
- Removed duplicate `_show_abaqus_summary` call at line 1062; only one call remains at line 1064
- Split long error message: short `st.error` + path in backtick-wrapped `st.caption`
- Added `key=` to both buttons in the panel
- Also fixed `st.write(str(snapshot.report_path))` → `st.caption` in MCP panel (line 1013)
- Also fixed `st.write(str(export.dataset_csv))` → `st.caption` in case library panel (lines 499-500)

### Acceptance
- Open Abaqus Verification tab → no horizontal scrollbar
- Click "准备目录" → success + work_dir display without overflow
- Click "运行 Abaqus" → layout remains stable
- Long paths wrap within their column

---

## BUG FIXES (Priority Order)

### B1 — Eliminate Hardcoded Abaqus Path (BUG 9, BUG 23)
**Severity:** HIGH  
**Files:** `abaqus_bridge.py:18`, `composite_workflow.py:23-24`, `abaqus_batch_client.py:14`

Replace all hardcoded `D:\ABAQUS\2023\...` paths with imports from `config.py`.

In `abaqus_bridge.py`:
```python
# DELETE line 18: DEFAULT_ABAQUS_BAT = Path(r"D:\ABAQUS\2023\Commands\abaqus.bat")
# ADD:
from material_ai_workbench.config import ABAQUS_BAT as DEFAULT_ABAQUS_BAT
```

In `composite_workflow.py`:
```python
# DELETE lines 23-24:
# DEFAULT_ABAQUS_BAT = Path("D:/ABAQUS/2023/Commands/abaqus.bat")
# DEFAULT_SMAPYTHON = Path("D:/ABAQUS/2023/EstProducts/win_b64/code/bin/SMAPython.exe")
# ADD:
from material_ai_workbench.config import ABAQUS_BAT as DEFAULT_ABAQUS_BAT, ABAQUS_SMAPYTHON as DEFAULT_SMAPYTHON
```

In `abaqus_batch_client.py`:
```python
# DELETE line 14: DEFAULT_SMAPYTHON = r"D:\ABAQUS\2023\EstProducts\win_b64\code\bin\SMAPython.exe"
# ADD:
from material_ai_workbench.config import ABAQUS_SMAPYTHON
# Then replace references to DEFAULT_SMAPYTHON with ABAQUS_SMAPYTHON
```

**Acceptance:** `grep -rn "D:\\\\ABAQUS" material_ai_workbench/*.py` returns zero matches.

---

### B2 — Fix CRLF Silently Breaking calc_properties Patching (BUG 6)
**Severity:** HIGH  
**File:** `abaqus_bridge.py`, `_patch_calc_properties()` around line 236

The function does `text.replace("import os\n", ...)` which fails on `\r\n` files.

Replace the current implementation with:
```python
def _patch_calc_properties(text: str, max_load_cases: int) -> str:
    """Patch calc_properties.py for the material AI workbench environment.

    Handles both Unix (\\n) and Windows (\\r\\n) line endings transparently.
    """
    import re

    # Normalize line endings for reliable matching
    text_unix = text.replace("\r\n", "\n")

    # Add missing imports
    if "import subprocess" not in text_unix:
        text_unix = text_unix.replace(
            "import os\n",
            "import os\nimport sys\nimport subprocess\n",
        )
    if "import json" not in text_unix:
        text_unix = text_unix.replace(
            "import datetime\n",
            "import datetime\nimport json\n",
        )

    # Replace os.system with subprocess.check_call
    text_unix = re.sub(
        r"os\.system\('abaqus ([^']+)'\)",
        r"subprocess.check_call(['\"]" + str(DEFAULT_ABAQUS_BAT).replace("\\", "/") + r" \1['\"], shell=True)",
        text_unix,
    )

    # Inject max_load_cases environment variable and check
    if max_load_cases > 0:
        insert_pos = text_unix.find("for i_lc, lc in enumerate(load_cases):")
        if insert_pos != -1:
            indent = "    "
            check_block = (
                f"{indent}max_lc = int(os.environ.get('MATERIAL_AI_MAX_LOAD_CASES', '0'))\n"
                f"{indent}if max_lc > 0 and i_lc >= max_lc:\n"
                f"{indent}    break\n"
            )
            # Insert after the for-loop line (find the newline)
            newline_pos = text_unix.find("\n", insert_pos)
            text_unix = text_unix[:newline_pos+1] + check_block + text_unix[newline_pos+1:]

    # Preserve original line ending style
    if "\r\n" in text:
        text_unix = text_unix.replace("\n", "\r\n")

    return text_unix
```

**Acceptance:**
- Copy `calc_properties.py` with `\r\n` endings → patch produces correctly modified script
- Copy `calc_properties.py` with `\n` endings → patch produces correctly modified script
- Run with `max_load_cases=1` → only 1 load case is executed

---

### B3 — Add try/except Around `run_material_workbench` in Streamlit (BUG 1)
**Severity:** MEDIUM  
**File:** `streamlit_app.py`

At lines 359-360 (inside `_training_panel`):
```python
# REPLACE:
with st.spinner("正在训练材料模型并生成报告..."):
    result = run_material_workbench(config)

# WITH:
with st.spinner("正在训练材料模型并生成报告..."):
    try:
        result = run_material_workbench(config)
    except Exception as exc:
        st.error(f"训练失败: {exc}")
        logger.exception("Training failed")
        return  # abort the rest of the panel
```

At lines 251-252 (inside `_ai_task_panel`):
```python
# REPLACE:
with st.spinner("正在运行材料训练管线..."):
    result = run_material_workbench(config)

# WITH:
with st.spinner("正在运行材料训练管线..."):
    try:
        result = run_material_workbench(config)
    except Exception as exc:
        st.error(f"训练失败: {exc}")
        logger.exception("AI task training failed")
        return
```

Apply the same pattern at every other `run_material_workbench()` call site in the file.

**Acceptance:** Deliberately pass invalid config → UI shows red `st.error` box instead of crash page.

---

### B4 — Validate abaqus_bat Text Input (BUG 2)
**Severity:** MEDIUM  
**File:** `streamlit_app.py`, around line 1022

```python
# AFTER reading abaqus_bat from text input:
abaqus_bat_raw = st.text_input("Abaqus 命令路径", value=str(DEFAULT_ABAQUS_BAT))

# ADD validation:
abaqus_bat_path = Path(abaqus_bat_raw.strip())
if not abaQus_bat_path.is_file() and abaQus_bat_raw.strip():
    st.error(f"Abaqus 可执行文件不存在: {abaQus_bat_raw}")
    abaQus_bat = None  # or str(DEFAULT_ABAQUS_BAT) as fallback
else:
    abaQus_bat = str(abaQus_bat_path)
```

**Acceptance:** Clear the text input → validation error appears, Abaqus is not called with `Path(".")`.

---

### B5 — Quote material_name in Generated PowerShell Script (BUG 7)
**Severity:** MEDIUM  
**File:** `abaqus_bridge.py`, around lines 252-257

```python
# REPLACE:
& '{config.abaqus_bat}' python calc_properties.py {material_name}

# WITH:
& '{config.abaqus_bat}' python calc_properties.py '{material_name}'
```

Also sanitize the material_name by replacing single-quotes:
```python
safe_name = material_name.replace("'", "''")
```

**Acceptance:** Material named "test material" → PowerShell runs correctly. Material with `'` → escaped correctly.

---

### B6 — Handle Missing Columns in Abaqus Result CSV (BUG 8)
**Severity:** MEDIUM  
**File:** `abaqus_bridge.py`, `_postprocess_result_csv()`, around line 322

```python
# REPLACE the fixed column name accesses with:
required_cols = {"PEEQ": "peeq", "MISES": "mises", "E11": "e11", "S11": "s11"}
available = {}
for csv_col, var_name in required_cols.items():
    if csv_col in rows[0]:
        available[var_name] = [_to_float(row[csv_col]) for row in rows]
    else:
        available[var_name] = []

missing = [csv_col for csv_col, var_name in required_cols.items()
           if csv_col not in rows[0]]
if missing:
    logger.warning("Result CSV missing expected columns: %s", missing)

# Then use available["mises"], available["peeq"], etc. with .get() guards
```

**Acceptance:** Feed a CSV without `E11`/`S11` columns → function degrades gracefully, only Mises vs PEEQ plot is generated.

---

### B7 — Fix CaseSummary JSON Forward-Compatibility (BUG 14)
**Severity:** MEDIUM  
**File:** `case_library.py`, `load_case_summary()`, around line 185

```python
# REPLACE:
return CaseSummary(**data)

# WITH:
# Filter to only known fields of CaseSummary
from dataclasses import fields as dc_fields
known_fields = {f.name for f in dc_fields(CaseSummary)}
filtered_data = {k: v for k, v in data.items() if k in known_fields}

# Warn about unknown fields
unknown = set(data.keys()) - known_fields
if unknown:
    logger.warning("Case %s has unknown fields in summary: %s", case_id, unknown)

return CaseSummary(**filtered_data)
```

**Acceptance:** Manually add a fake field to `case_summary.json` → case loads successfully with warning.

---

### B8 — Fix batch_simulation.py samples Property Mutation (BUG 25)
**Severity:** MEDIUM  
**File:** `batch_simulation.py`, around line 49

```python
# REPLACE:
@property
def samples(self) -> list[dict[str, Any]]:
    return self.data.setdefault("samples", [])

# WITH:
@property
def samples(self) -> list[dict[str, Any]]:
    return self.data.get("samples", [])

def ensure_samples(self) -> list[dict[str, Any]]:
    """Get or create the samples list (use this when mutation is intended)."""
    if "samples" not in self.data:
        self.data["samples"] = []
    return self.data["samples"]
```

Then update all callers: places that only READ samples use `.samples` (property, no mutation). The one place that writes samples (in `create_parameter_sweep_plan`) uses `.ensure_samples()`.

**Acceptance:** Read `plan.samples` on a plan with no samples → `[]` (no mutation). `plan.data` still has no `"samples"` key.

---

### B9 — Fix European Decimal Number Handling (BUG 15)
**Severity:** LOW-MEDIUM  
**File:** `case_library.py`, `_try_float()`, around line 618

```python
# REPLACE the heuristic with:
def _try_float(text: str) -> float | None:
    """Parse a string to float, handling common number formats."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        pass

    # Try European format: 1.234,56 → 1234.56
    # Only if comma is last non-digit separator (decimal) and periods are grouping
    if "," in text:
        # If comma appears AFTER the last period, it's likely European decimal
        last_comma = text.rfind(",")
        last_period = text.rfind(".")
        if last_comma > last_period:
            clean = text.replace(".", "").replace(",", ".")
            try:
                return float(clean)
            except ValueError:
                pass

    return None
```

**Acceptance:** `_try_float("1.234,56")` → `1234.56`. `_try_float("1,234.56")` → `1234.56`. Both work.

---

### B10 — Prevent subprocess Deadlock with shell=True (BUG 21)
**Severity:** MEDIUM  
**File:** `composite_workflow.py`, around line 1102

```python
# REPLACE shell=True string form with list form:
abaqus_bat_str = str(config.abaqus_bat)
abaqus_script_str = str(abaqus_script.resolve())

result = subprocess.run(
    [abaqus_bat_str, "cae", f"noGUI={abaqus_script_str}"],
    cwd=str(run_dir),
    capture_output=True,
    text=True,
    timeout=1800,
)
```

**Acceptance:** Build script runs without shell=True. Same behavior but no deadlock risk.

---

### B11 — Fix Uncaught Double-Failure in Batch Panel (BUG 3)
**Severity:** LOW-MEDIUM  
**File:** `streamlit_app.py`, around lines 1376-1378

```python
# REPLACE:
except Exception as exc:
    st.error(f"批量运行异常: {exc}")
    plan = load_batch_plan(chosen)
    if plan:
        _show_batch_plan(plan)

# WITH:
except Exception as exc:
    st.error(f"批量运行异常: {exc}")
    try:
        plan = load_batch_plan(chosen)
        if plan:
            _show_batch_plan(plan)
    except Exception as load_exc:
        st.error(f"加载批量计划也失败了: {load_exc}")
```

**Acceptance:** Corrupt `batch_plan.json` → first error shown, second error caught and displayed.

---

### B12 — Add onerror Handler to shutil.rmtree (BUG 10)
**Severity:** LOW  
**File:** `abaqus_bridge.py`, around line 53

```python
# REPLACE:
shutil.rmtree(work_dir)

# WITH:
def _remove_readonly(func, path, exc_info):
    """Handle read-only files on Windows during rmtree."""
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)

shutil.rmtree(work_dir, onerror=_remove_readonly)
```

**Acceptance:** Copy a read-only file into work_dir, then rmtree → succeeds.

---

## REMAINING LOW-SEVERITY BUGS (Fix Time Permitting)

| Bug | File | Fix |
|-----|------|-----|
| BUG 4 | `streamlit_app.py:284` | Add `if material_type is None: material_type = "j2"` after segmented_control |
| BUG 11 | `abaqus_bridge.py:58` | Add try/except FileNotFoundError around shutil.copy2 with clear error message |
| BUG 12 | `abaqus_bridge.py:101` | Move `import os` to top of function |
| BUG 13 | `abaqus_bridge.py:253` | Escape single-quotes in paths: `.replace("'", "''")` |
| BUG 18 | `pipeline.py:254` | Add `assert len(values) == len(METRIC_NAMES)` or use dict comprehension |
| BUG 22 | `composite_workflow.py:532` | Add `if not phase_rows: return` guard before `phase_rows[0]` |
| BUG 26 | `batch_simulation.py:241` | Add a `stale_timeout` check: if sample status is "running" for >4 hours, reset to "pending" |
| BUG 27 | `batch_simulation.py:334` | Use `rows.get(key, "")` pattern instead of direct key access for all SAMPLE_COLUMNS |
| BUG 28 | `batch_simulation.py:288` | Guard: `if not source or str(source) == ".": logger.warning(...); continue` |

---

## UI POLISH (Priority Order)

### U1 — Move Navigation to Sidebar
**Severity:** HIGH  
**File:** `streamlit_app.py`, lines 136-143

Replace the 11-tab layout with sidebar navigation:

```python
# In the sidebar (replace lines 136-143):
with st.sidebar:
    st.title("MaterialAI")
    st.caption("Workbench")

    page = st.radio(
        "导航",
        ["AI 任务", "材料训练", "数据导入", "案例库",
         "Abaqus MCP", "Abaqus 验算", "复合材料",
         "批量仿真", "结果浏览", "代理模型", "模型管理"],
        label_visibility="collapsed",
    )

    st.divider()

    # Active run indicator
    if st.session_state.get("selected_run_dir"):
        st.caption(f"当前运行: {Path(st.session_state['selected_run_dir']).name}")

    # Version
    st.caption(f"pyLabFEA v{FE.__version__}")

# Main area: dispatch to the selected page
if page == "AI 任务":
    _ai_task_panel()
elif page == "材料训练":
    _training_panel()
elif page == "数据导入":
    _data_import_panel()
elif page == "案例库":
    _case_library_panel()
elif page == "Abaqus MCP":
    _abaqus_mcp_panel()
elif page == "Abaqus 验算":
    _abaqus_panel()
elif page == "复合材料":
    _composite_panel()
elif page == "批量仿真":
    _batch_panel()
elif page == "结果浏览":
    _results_panel()
elif page == "代理模型":
    _surrogate_panel()
elif page == "模型管理":
    _management_panel()
```

Then DELETE the old `st.tabs()` call at line 142 and all the `with tab1:`, `with tab2:`, etc. blocks. Each `_xxx_panel()` function stays the same internally.

**Acceptance:** Sidebar has 11 navigation items. Clicking one changes the main content area. No horizontal tab bar.

---

### U2 — Add Explicit `key=` to Every Button
**Severity:** MEDIUM  
**File:** `streamlit_app.py`, ~28 locations

Add `key=` to every `st.button()` call. Use descriptive, namespaced keys:

```python
# In _ai_task_panel:
st.button("解析任务", key="ai_parse_rule")
st.button("LLM 增强解析", key="ai_parse_llm")
st.button("执行材料训练", key="ai_execute_training")

# In _training_panel:
st.button("开始训练", key="training_start")

# In _data_import_panel:
st.button("导入上传文件", key="import_upload")
st.button("导入当前 Abaqus CSV", key="import_abaqus_csv")

# In _case_library_panel:
st.button("扫描并归档案例", key="case_scan")
st.button("导出案例库训练数据集", key="case_export_dataset")

# In _abaqus_mcp_panel:
c0.button("检查连接", key="mcp_check")
c1.button("停止 Bridge", key="mcp_stop")
st.button("生成会话快照", key="mcp_snapshot")
st.button("设置 Abaqus 工作目录", key="mcp_set_workdir")
c1.button("读取模型", key="mcp_read_model")
c2.button("读取 Job", key="mcp_read_jobs")
c3.button("监控 Job", key="mcp_monitor")
st.button("提交并等待 Job 完成", key="mcp_submit")
c4.button("读取 ODB 元数据", key="mcp_read_odb")
c5.button("抓取当前视口", key="mcp_capture")

# In _abaqus_panel:
c1.button("准备目录", key="abaqus_prepare")
c2.button("运行 Abaqus", key="abaqus_run")

# In _composite_panel:
st.button("生成复合材料闭环案例", key="composite_generate")

# In _batch_panel:
st.button("创建批量计划", key="batch_create")
st.button("只运行材料训练", key="batch_train_only")
st.button("运行材料训练 + Abaqus", key="batch_train_abaqus")

# In _surrogate_panel:
st.button("训练代理模型", key="surrogate_train")
st.button("生成最新闭环报告", key="surrogate_closed_loop")

# In _material_library_controls:
st.button("加载到训练页", key="lib_load")
st.button("保存当前参数", key="lib_save")
```

**Acceptance:** No `DuplicateElementId` errors when multiple panels with similar button labels exist.

---

### U3 — Add `height` Parameter to All Dataframes
**Severity:** MEDIUM  
**File:** `streamlit_app.py`, ~13 locations

```python
# Default height for tables:
DF_HEIGHT = 400

# Apply to every st.dataframe() call:
st.dataframe(rows, height=DF_HEIGHT, use_container_width=True)
```

Locations: lines 496, 542, 556, 570, 587, 591, 957, 1175, 1247, 1503, 1521, 1832, 1883.

**Acceptance:** No table renders more than ~20 rows without scrolling.

---

### U4 — Standardize Language to Consistent Chinese
**Severity:** MEDIUM  
**File:** `streamlit_app.py`

Change English labels to Chinese:
- Line 834: `"Bridge host"` → `"Bridge 主机地址"`
- Line 835: `"Bridge port"` → `"Bridge 端口"`
- Line 1076: Add `st.caption("几何尺寸")` before length/width/thickness inputs
- Lines 1084-1085: `"Abaqus CPUs"` → `"Abaqus CPU 数"`, `"随机种子"` is fine
- Lines 284-288 `format_func`: Keep `"j2"` and `"hill"` as they're technical identifiers, but add Chinese descriptions in parentheses

**Acceptance:** No mixed English labels in Chinese sections.

---

### U5 — Add Section Dividers in Training Panel
**Severity:** MEDIUM  
**File:** `streamlit_app.py`, `_training_panel()`, around lines 281-332

Add `st.divider()` between logical sections:
```python
# After material library expander
st.divider()

# After material type selector
st.divider()

# Before Hill ratios
st.divider()

# Before training button
st.divider()
```

**Acceptance:** Training panel has clear visual separation between material type, elastic properties, Hill ratios, SVC params, and the train button.

---

### U6 — Fix Nested Expander in Composite Panel
**Severity:** MEDIUM  
**File:** `streamlit_app.py`, lines 1191 and 1249

Replace the inner expander (line 1249) with a simple `st.dataframe()` or `st.markdown()` that always renders when the outer expander is open, OR promote it to a sibling expander outside.

```python
# REPLACE:
with st.expander("复合材料批量数据", expanded=False):
    ...
    with st.expander("composite_dataset.csv"):
        st.dataframe(preview_rows, height=300)

# WITH:
with st.expander("复合材料批量数据", expanded=False):
    ...
    st.markdown("**composite_dataset.csv**")
    st.dataframe(preview_rows, height=300)
```

**Acceptance:** No expander-inside-expander. Composite dataset preview is directly visible when outer expander is open.

---

### U7 — Add Sub-Headers for Composite Input Groups
**Severity:** LOW  
**File:** `streamlit_app.py`, `_composite_panel()`, around lines 1056-1071

```python
st.markdown("**微观材料与 RVE**")
st.caption("纤维")           # before fiber E and nu
c1, c2 = st.columns(2)
with c1: vf = st.number_input(...)
with c2: fiber_E = st.number_input(...)

st.caption("基体")           # before matrix E and nu
c3, c4 = st.columns(2)
...

st.caption("界面")           # before interface params
c5, c6 = st.columns(2)
...

st.caption("RVE 网格")       # before nx, ny, nz
c9, c10, c11 = st.columns(3)
...
```

**Acceptance:** Each input group has a visible caption label.

---

### U8 — Add Progress Spinners for Long Operations
**Severity:** LOW  
**File:** `streamlit_app.py`

Wrap all long-running operations with `st.spinner()`:

```python
# Data import (line ~395):
with st.spinner("正在导入并分析数据..."):
    result = import_csv_dataset(...)

# Case scan (line ~462):
with st.spinner("正在扫描案例文件夹..."):
    case_summary = scan_case_folder(...)

# Dataset export (line ~480):
with st.spinner("正在导出案例库数据集..."):
    export = export_case_dataset(...)

# Surrogate training:
with st.spinner("正在训练代理模型..."):
    run = train_surrogate_from_dataset(...)
```

**Acceptance:** User sees a spinner with Chinese text during every operation that takes >500ms.

---

### U9 — Fix st.warning vs st.error Severity (BUG 17 from UI audit)
**Severity:** LOW  
**File:** `streamlit_app.py`

At lines 1038-1041 and 267-270:
```python
# REPLACE:
if result.status != "completed":
    st.warning(f"Abaqus 状态：{result.status}")

# WITH:
if result.status == "failed":
    st.error(f"Abaqus 运行失败: {result.error_message or '未知错误'}")
elif result.status == "timeout":
    st.error(f"Abaqus 运行超时")
elif result.status not in ("completed",):
    st.warning(f"Abaqus 状态：{result.status} (仍在进行中)")
```

**Acceptance:** Failed jobs → red `st.error`. Running jobs → yellow `st.warning`. Not-invoked → blue `st.info`.

---

### U10 — Add Truncation Warning to `_read_csv_preview`
**Severity:** LOW  
**File:** `streamlit_app.py`, `_read_csv_preview()`, around line 1930

```python
# AFTER the loop that reads rows:
if idx >= 30:
    st.caption(f"仅显示前 30 行（共 {total_rows} 行）")
```

Store `total_rows` by counting lines first, or do a two-pass read. For large CSVs, use a fixed buffer:
```python
MAX_PREVIEW = 30
rows = []
with open(path, "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        if i >= MAX_PREVIEW:
            break
        rows.append(row)
    total = i + 1  # approximate

if total > MAX_PREVIEW:
    st.caption(f"仅显示前 {MAX_PREVIEW} 行（文件共 {total}+ 行）")
```

**Acceptance:** Open a 100-row CSV preview → "仅显示前 30 行（文件共 100+ 行）" is shown.

---

## Execution Order

```
B1 (config.py dependency) → must be first
Then execute in parallel:
  Group A (abaqus_bridge.py bugs):    B2, B5, B6, B12
  Group B (streamlit_app.py bugs):    B3, B4, B11
  Group C (other source bugs):        B7, B8, B9, B10
Then UI fixes (all streamlit_app.py):
  U1 (navigation) → must be first (changes structure)
  U2-U10 in any order
```

## Summary of Changes

| Category | Files Changed | Bug Count | UI Count |
|----------|---------------|-----------|----------|
| Critical bugs | `abaqus_bridge.py`, `composite_workflow.py`, `abaqus_batch_client.py` | 3 (B1, B2, B10) | - |
| Medium bugs | `streamlit_app.py`, `abaqus_bridge.py`, `case_library.py`, `batch_simulation.py` | 7 (B3-B9) | - |
| Low bugs | Multiple | 9 | - |
| UI polish | `streamlit_app.py` only | - | 10 (U1-U10) |
| **Total** | | **28 bugs** | **22 UI issues** |
