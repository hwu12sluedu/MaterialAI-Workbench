"""Streamlit front end for the MaterialAI Workbench prototype."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import streamlit as st
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from material_ai_workbench.abaqus_bridge import (
    AbaqusBridgeConfig,
    DEFAULT_ABAQUS_BAT,
    prepare_abaqus_verification,
    run_abaqus_verification,
)
from material_ai_workbench.abaqus_batch_client import (
    AbaqusBatchConfig,
    DEFAULT_SMAPYTHON,
)
from material_ai_workbench.abaqus_diagnostics import (
    AbaqusDiagnosticConfig,
    run_abaqus_diagnostics,
)
from material_ai_workbench.abaqus_mcp_client import (
    AbaqusMcpConfig,
    capture_viewport,
    create_session_snapshot,
    get_model_info,
    inspect_odb,
    list_jobs,
    monitor_job_status,
    ping_bridge,
    set_workdir,
    stop_bridge,
    submit_job,
)
from material_ai_workbench.batch_simulation import (
    BATCH_ROOT,
    batch_sample_table_rows,
    create_parameter_sweep_plan,
    list_batch_plans,
    load_batch_plan,
    run_batch_plan,
)
from material_ai_workbench.case_library import (
    append_odb_extraction,
    append_odb_frame_series,
    batch_import_cases,
    case_table_rows,
    file_table_rows,
    filter_cases,
    find_duplicate_cases,
    find_similar_cases,
    infer_case_type,
    inp_feature_table_rows,
    list_cases,
    load_case_summary,
    odb_extraction_table_rows,
    odb_frame_series_table_rows,
    result_feature_table_rows,
    scan_case_folder,
)
from material_ai_workbench.case_based_workflow import prepare_case_based_plan
from material_ai_workbench.case_intelligence import (
    build_case_grounding_context,
    search_cases_by_text,
)
from material_ai_workbench.case_package import evaluate_case_quality, quality_table_rows
from material_ai_workbench.closed_loop_report import (
    CLOSED_LOOP_ROOT,
    generate_closed_loop_report,
    list_closed_loop_reports,
)
from material_ai_workbench.composite_dataset import (
    COMPOSITE_BATCH_ROOT,
    COMPOSITE_SURROGATE_ROOT,
    CompositeBatchConfig,
    composite_surrogate_comparison_rows,
    create_composite_batch_plan,
    list_composite_surrogate_runs,
    list_composite_batch_plans,
    load_composite_batch_plan,
    run_composite_batch_plan,
    train_composite_surrogate,
)
from material_ai_workbench.composite_workflow import (
    COMPOSITE_ROOT,
    CompositePlateConfig,
    list_composite_runs,
    load_composite_manifest,
    run_composite_plate_workflow,
)
from material_ai_workbench.config import (
    ACCEPTANCE_ROOT,
    DIAGNOSTICS_ROOT,
    RUNS_ROOT,
    WORKSPACE_ROOT,
)
from material_ai_workbench.data_import import (
    imported_curve_to_config,
    import_csv_dataset,
    list_imports,
    load_import_summary,
    read_normalized_preview,
    validate_imported_curve_with_workbench,
)
from material_ai_workbench.dataset_export import export_case_dataset
from material_ai_workbench.llm_adapter import (
    ENV_FILE,
    LLM_PROVIDER_PRESETS,
    LlmChatConfig,
    LlmConfigError,
    LlmResponseError,
    apply_llm_config,
    llm_config_from_env,
    provider_preset,
    save_llm_config,
    test_llm_connection,
    plan_task_with_llm,
)
from material_ai_workbench.logging_config import get_logger
from material_ai_workbench.rve_visualization import (
    plot_oriented_fiber_rve_3d,
    plot_rve_3d_from_run,
    plot_rve_3d,
)
from material_ai_workbench.material_library import (
    MaterialPreset,
    delete_material_preset,
    load_material_presets,
    preset_from_training_state,
    preset_to_training_state,
    preset_to_workbench_config,
    save_material_preset,
)
from material_ai_workbench.job_queue import JobQueue
from material_ai_workbench.multi_fidelity import train_multi_fidelity
from material_ai_workbench.nl_tasks import (
    parse_natural_language_task,
    task_from_dict,
    task_to_workbench_config,
)
from material_ai_workbench.odb_postprocess import (
    DEFAULT_FRAME_SERIES_FIELDS,
    DEFAULT_ODB_FIELDS,
    run_case_odb_extraction,
    run_case_odb_frame_series_extraction,
)
from material_ai_workbench.param_recommender import recommend_parameters
from material_ai_workbench.pipeline import WorkbenchConfig, run_material_workbench
from material_ai_workbench.plate_hole_acceptance import (
    PlateHoleAcceptanceConfig,
    resume_plate_hole_acceptance,
    run_plate_hole_acceptance,
)
from material_ai_workbench.plate_hole_batch import (
    PlateHoleBatchConfig,
    batch_table_rows as plate_hole_batch_table_rows,
    create_plate_hole_batch_plan,
    list_plate_hole_batch_plans,
    load_plate_hole_batch_plan,
    run_plate_hole_batch_plan,
)
from material_ai_workbench.task_schema import (
    build_executable_plan,
    dry_run_summary,
    merge_with_defaults,
    validate_task_payload,
)
from material_ai_workbench.surrogate_model import (
    DEFAULT_TARGET,
    SURROGATES_ROOT,
    compare_all_models,
    list_dataset_exports,
    list_surrogate_runs,
    surrogate_comparison_rows,
    train_surrogate_from_dataset,
)
from material_ai_workbench.time_series_surrogate import train_time_series_surrogate

LOGGER = get_logger(__name__)
HILL_RATIO_DEFAULTS = (1.2, 1.0, 0.8, 1.0, 1.0, 1.0)
BARLAT_ALPHA_DEFAULTS = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
MIN_HILL_RATIO = 0.05
SURROGATE_TARGET_OPTIONS = [
    DEFAULT_TARGET,
    "latest_odb_max_displacement",
    "latest_odb_max_peeq",
    "latest_odb_max_reaction_force",
]


def _load_page_icon() -> Image.Image | None:
    icon_path = Path(__file__).resolve().parent / "resources" / "app_icon.png"
    try:
        with Image.open(icon_path) as icon:
            return icon.copy()
    except OSError:
        return None


def main() -> None:
    st.set_page_config(
        page_title="MaterialAI Workbench",
        page_icon=_load_page_icon(),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_style()

    st.title("MaterialAI Workbench")
    st.caption("材料建模 · Abaqus 验证 · 仿真数据管理")

    with st.sidebar:
        st.subheader("运行目录")
        st.caption(f"`{RUNS_ROOT}`")
        st.divider()
        selected_run = _run_selector("全局选择")
        st.divider()
        _llm_sidebar_status()

    page_labels = {
        "ai": "仿真任务",
        "train": "材料训练",
        "import": "数据导入",
        "case": "案例库",
        "diagnostics": "系统诊断",
        "mcp": "Abaqus MCP",
        "abaqus": "Abaqus 验算",
        "acceptance": "带孔板验证",
        "plate_batch": "带孔板批量",
        "composite": "复合材料 RVE",
        "batch": "批量仿真",
        "results": "结果浏览",
        "surrogate": "代理模型",
        "manage": "模型管理",
    }
    page_key = st.sidebar.radio(
        "功能导航",
        list(page_labels),
        format_func=lambda key: page_labels[key],
        key="main_page",
    )

    if page_key == "ai":
        _ai_task_panel()
    elif page_key == "train":
        _training_panel()
    elif page_key == "import":
        _data_import_panel(selected_run)
    elif page_key == "case":
        _case_library_panel()
    elif page_key == "diagnostics":
        _system_diagnostics_panel()
    elif page_key == "mcp":
        _abaqus_mcp_panel(selected_run)
    elif page_key == "abaqus":
        _abaqus_panel(selected_run)
    elif page_key == "acceptance":
        _plate_hole_acceptance_panel()
    elif page_key == "plate_batch":
        _plate_hole_batch_panel()
    elif page_key == "composite":
        _composite_panel()
    elif page_key == "batch":
        _batch_panel()
    elif page_key == "results":
        _results_panel(selected_run)
    elif page_key == "surrogate":
        _surrogate_panel()
    elif page_key == "manage":
        _management_panel(selected_run)


def _run_material_training_with_feedback(config: WorkbenchConfig, message: str):
    try:
        with st.spinner(message):
            return run_material_workbench(config)
    except Exception as exc:
        st.error(f"训练失败: {type(exc).__name__}: {exc}")
        return None


def _llm_sidebar_status() -> None:
    cfg = llm_config_from_env()
    configured = bool(
        cfg.base_url.strip()
        and cfg.model.strip()
        and (not cfg.require_api_key or cfg.api_key)
    )
    with st.expander("自然语言服务", expanded=False):
        if st.session_state.get("llm_last_connection_ok"):
            st.success("连接已验证")
        elif configured:
            st.info("已配置，未测试")
        else:
            st.caption("未配置；规则解析仍可使用")
        if cfg.model:
            st.caption(f"`{cfg.model}`")


def _ensure_llm_ui_defaults() -> None:
    if st.session_state.get("llm_ui_initialized"):
        return
    cfg = llm_config_from_env()
    st.session_state["llm_provider"] = (
        cfg.provider_name if cfg.provider_name in LLM_PROVIDER_PRESETS else "custom"
    )
    st.session_state["llm_base_url"] = cfg.base_url
    st.session_state["llm_model"] = cfg.model
    st.session_state["llm_api_key_env"] = cfg.api_key_env
    st.session_state["llm_require_key"] = cfg.require_api_key
    st.session_state["llm_timeout"] = int(cfg.timeout_seconds)
    st.session_state["llm_ui_initialized"] = True


def _llm_config_wizard() -> tuple[LlmChatConfig, str, bool, bool]:
    _ensure_llm_ui_defaults()
    provider_key = st.selectbox(
        "提供商",
        list(LLM_PROVIDER_PRESETS),
        format_func=lambda key: str(LLM_PROVIDER_PRESETS[key]["label"]),
        key="llm_provider",
    )
    c0, c1 = st.columns(2)
    apply_preset_clicked = c0.button(
        "套用提供商预设", use_container_width=True, key="llm_apply_provider"
    )
    test_clicked = c1.button(
        "测试连接", use_container_width=True, key="llm_test_connection"
    )
    if apply_preset_clicked:
        preset = provider_preset(provider_key)
        st.session_state["llm_base_url"] = str(preset.get("base_url", ""))
        st.session_state["llm_model"] = str(preset.get("model", ""))
        st.session_state["llm_api_key_env"] = str(
            preset.get("api_key_env", "MATERIALAI_LLM_API_KEY")
        )
        st.session_state["llm_require_key"] = bool(preset.get("require_api_key", True))
        st.session_state["llm_last_connection_ok"] = False
        st.rerun()

    llm_base_url = st.text_input(
        "Base URL", placeholder="例如 https://api.openai.com/v1", key="llm_base_url"
    )
    llm_model = st.text_input(
        "模型",
        placeholder="例如 gpt-4.1-mini / deepseek-chat / qwen-plus",
        key="llm_model",
    )
    c2, c3 = st.columns([0.55, 0.45])
    llm_api_key_env = c2.text_input("API Key 环境变量", key="llm_api_key_env")
    llm_require_key = c3.checkbox("需要 API Key", key="llm_require_key")
    llm_api_key_value = st.text_input(
        "API Key（可选：填写后可保存到本地 .env）",
        value="",
        type="password",
        key="llm_api_key_value",
    )
    llm_timeout = st.number_input(
        "服务超时(秒)", min_value=10, max_value=300, step=10, key="llm_timeout"
    )
    allow_llm = st.checkbox(
        "允许本次调用外部模型服务", value=False, key="allow_llm_call"
    )

    cfg = LlmChatConfig(
        provider_name=provider_key,
        base_url=str(llm_base_url).strip(),
        model=str(llm_model).strip(),
        api_key_env=str(llm_api_key_env).strip(),
        timeout_seconds=float(llm_timeout),
        require_api_key=bool(llm_require_key),
    )
    b1, b2 = st.columns(2)
    save_clicked = b1.button(
        "保存服务配置", use_container_width=True, key="llm_save_config"
    )
    llm_clicked = b2.button(
        "使用模型解析", use_container_width=True, key="ai_llm_parse"
    )

    if save_clicked:
        try:
            save_llm_config(cfg, api_key_value=llm_api_key_value or None)
            st.success(f"已保存到 `{ENV_FILE}`")
        except Exception as exc:
            st.error(f"保存失败：{exc}")

    if test_clicked:
        with st.spinner("正在测试连接并验证任务 JSON..."):
            result = test_llm_connection(cfg, api_key_value=llm_api_key_value or None)
        st.session_state["llm_last_connection_ok"] = bool(result.ok)
        if result.ok:
            st.success(result.message)
            with st.expander("连接测试返回的任务 JSON", expanded=False):
                st.json(result.task_payload or {})
        else:
            st.error(f"连接测试失败：{result.message}")

    return cfg, llm_api_key_value, allow_llm, llm_clicked


def _ai_task_panel() -> None:
    st.subheader("仿真任务")
    left, right = st.columns([0.46, 0.54], gap="large")

    default_prompt = (
        "用 Hill 各向异性材料，E=200000 MPa，nu=0.3，屈服 60 MPa，"
        "r1=1.2 r2=1.0 r3=0.8 r4=1.0 r5=1.0 r6=1.0，"
        "SVC C=1.0 gamma=1.0，训练材料模型，并跑 1 个 Abaqus 单元验算。"
    )

    with left:
        st.markdown("**自然语言输入**")
        prompt = st.text_area(
            "描述你的仿真任务", value=default_prompt, height=180, key="nl_task_prompt"
        )
        use_case_grounding = st.checkbox(
            "参考本地历史案例库",
            value=True,
            key="nl_use_case_grounding",
        )
        parse_clicked = st.button(
            "解析任务", type="primary", use_container_width=True, key="ai_parse_task"
        )
        with st.expander("外部语言模型（可选）", expanded=False):
            llm_config, llm_api_key_value, allow_llm, llm_clicked = _llm_config_wizard()
        allow_abaqus = st.checkbox("允许本次任务调用 Abaqus", value=False)
        execute_clicked = st.button(
            "执行任务", use_container_width=True, key="ai_execute_training"
        )

    with right:
        st.markdown("**结构化任务 JSON**")
        if parse_clicked:
            st.session_state.pop("nl_task_payload", None)
            st.session_state.pop("nl_task_payload_source", None)
            st.session_state.pop("nl_llm_raw_text", None)
            st.session_state.pop("nl_case_grounding", None)

        if llm_clicked:
            if not allow_llm:
                st.warning("请先勾选“允许本次调用外部模型服务”。")
            else:
                try:
                    apply_llm_config(
                        llm_config, api_key_value=llm_api_key_value or None
                    )
                    case_context = (
                        build_case_grounding_context(prompt, top_k=3)
                        if use_case_grounding
                        else None
                    )
                    llm_plan = plan_task_with_llm(
                        prompt,
                        llm_config,
                        case_context=case_context,
                    )
                except (LlmConfigError, LlmResponseError, Exception) as exc:
                    st.error(f"模型解析失败：{exc}")
                else:
                    st.session_state["nl_task_payload"] = llm_plan.task_payload
                    st.session_state["nl_task_payload_source"] = prompt
                    st.session_state["nl_llm_raw_text"] = llm_plan.raw_text
                    st.session_state["nl_case_grounding"] = case_context
                    st.success("模型任务 JSON 已生成")

        task_source = "规则解析"
        task_payload = st.session_state.get("nl_task_payload")
        task_payload_matches_prompt = bool(
            isinstance(task_payload, dict)
            and st.session_state.get("nl_task_payload_source") == prompt
        )
        if (
            task_payload_matches_prompt
            and str(task_payload.get("task_type", "")).strip()
            == "case_based_simulation"
        ):
            st.caption("当前解析来源：语言模型 + 本地案例检索")
            grounding = st.session_state.get("nl_case_grounding") or {}
            grounded_cases = grounding.get("cases", []) if grounding else []
            if grounded_cases:
                st.markdown("**本地检索证据**")
                st.dataframe(
                    [
                        {
                            "Case ID": item.get("case_id"),
                            "标题": item.get("title"),
                            "检索分": item.get("retrieval_score"),
                            "执行状态": item.get("execution_state"),
                            "可训练": "是" if item.get("training_eligible") else "否",
                            "单位制": (item.get("units") or {}).get("system", ""),
                        }
                        for item in grounded_cases
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning("本地案例库未检索到可引用案例，当前计划不能生成复用工作区。")
            st.json(task_payload)
            for warning in (
                task_payload.get("warnings", [])
                if isinstance(task_payload.get("warnings"), list)
                else []
            ):
                st.warning(str(warning))
            plan_preview = build_executable_plan(task_payload)
            st.dataframe(
                [
                    {
                        "步骤": step.index,
                        "动作": step.label,
                        "需要 Abaqus": "是" if step.requires_abaqus else "否",
                        "状态": step.status,
                    }
                    for step in plan_preview.steps
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.info(
                "执行该计划只会复制可编辑输入并生成差异审查单，不修改历史案例，也不提交 Abaqus。"
            )
            if execute_clicked:
                try:
                    prepared = prepare_case_based_plan(task_payload)
                except Exception as exc:
                    st.error(f"历史案例复用工作区生成失败：{exc}")
                else:
                    st.success(f"复用工作区已生成：{prepared.run_dir}")
                    st.caption(f"差异审查单：`{prepared.review_path}`")
                    st.caption(f"计划清单：`{prepared.manifest_path}`")
            return
        if (
            task_payload_matches_prompt
            and str(task_payload.get("task_type", "")).strip() == "composite_plate_hole"
        ):
            task_source = "语言模型解析"
            st.caption(f"当前解析来源：{task_source}")
            st.json(task_payload)
            raw_text = st.session_state.get("nl_llm_raw_text")
            if raw_text:
                with st.expander("模型原始返回", expanded=False):
                    st.code(str(raw_text), language="json")
            for warning in (
                task_payload.get("warnings", [])
                if isinstance(task_payload.get("warnings"), list)
                else []
            ):
                st.warning(str(warning))
            plan_preview = build_executable_plan(task_payload)
            st.dataframe(
                [
                    {
                        "步骤": step.index,
                        "动作": step.label,
                        "需要 Abaqus": "是" if step.requires_abaqus else "否",
                        "状态": step.status,
                    }
                    for step in plan_preview.steps
                ],
                use_container_width=True,
                hide_index=True,
                height=min(260, 42 + 30 * max(1, len(plan_preview.steps))),
            )
            abaqus_payload = (
                task_payload.get("abaqus")
                if isinstance(task_payload.get("abaqus"), dict)
                else {}
            )
            wants_abaqus = bool(
                abaqus_payload.get("run_check") or abaqus_payload.get("submit_job")
            )
            if wants_abaqus and not allow_abaqus:
                st.info(
                    "语言模型已生成 Abaqus 建模/求解任务。勾选“允许本次任务调用 Abaqus”后才会真正启动 Abaqus；否则只生成模型脚本和报告。"
                )
            if execute_clicked:
                _execute_composite_ai_task(
                    task_payload, allow_abaqus=bool(allow_abaqus)
                )
            return

        special_task_types = {
            "batch_parameter_sweep",
            "case_library_query",
            "surrogate_training",
            "odb_extraction",
            "closed_loop_report",
        }
        if (
            task_payload_matches_prompt
            and str(task_payload.get("task_type", "")).strip() in special_task_types
        ):
            _render_special_ai_task(
                task_payload,
                source_text=prompt,
                execute_clicked=bool(execute_clicked),
            )
            return

        if task_payload and st.session_state.get("nl_task_payload_source") == prompt:
            task = task_from_dict(task_payload, source_text=prompt)
            task_source = "语言模型解析"
        else:
            task = parse_natural_language_task(prompt)

        if parse_clicked or llm_clicked or "nl_task_json" not in st.session_state:
            st.session_state["nl_task_json"] = task.to_json()
        st.caption(f"当前解析来源：{task_source}")
        st.json(task.to_dict())

        raw_text = st.session_state.get("nl_llm_raw_text")
        if task_source == "语言模型解析" and raw_text:
            with st.expander("模型原始返回", expanded=False):
                st.code(str(raw_text), language="json")

        if task.warnings:
            for warning in task.warnings:
                st.warning(warning)
        if task.abaqus.run_check and not allow_abaqus:
            st.info(
                "已识别到 Abaqus 验算需求。勾选“允许本次任务调用 Abaqus”后，执行任务才会真正提交 Abaqus。"
            )

        # Dry-run preview
        with st.expander("Dry-Run 预览（执行前检查）", expanded=True):
            dry_payload = merge_with_defaults(task.to_dict())
            schema_result = validate_task_payload(dry_payload)
            st.markdown(dry_run_summary(dry_payload, schema_result))
            plan_preview = build_executable_plan(dry_payload)
            st.dataframe(
                [
                    {
                        "步骤": step.index,
                        "动作": step.label,
                        "需要 Abaqus": "是" if step.requires_abaqus else "否",
                        "状态": step.status,
                    }
                    for step in plan_preview.steps
                ],
                use_container_width=True,
                hide_index=True,
                height=min(260, 42 + 30 * max(1, len(plan_preview.steps))),
            )
            if not schema_result.valid:
                st.caption("以上缺失字段已使用默认值填充，执行不受影响。")

        if execute_clicked:
            config = task_to_workbench_config(task, RUNS_ROOT)
            with st.spinner("正在执行自然语言任务：材料训练..."):
                result = _run_material_training_with_feedback(
                    config, "正在训练材料模型..."
                )
            if result is None:
                return
            st.session_state["selected_run_dir"] = str(result.run_dir)
            st.success("材料训练完成")
            _show_run_summary(result.run_dir)

            if task.abaqus.run_check:
                if allow_abaqus:
                    bridge_config = AbaqusBridgeConfig(
                        run_dir=result.run_dir,
                        abaqus_bat=DEFAULT_ABAQUS_BAT,
                        max_load_cases=task.abaqus.max_load_cases,
                        timeout_seconds=task.abaqus.timeout_seconds,
                    )
                    with st.spinner("正在调用 Abaqus 做单元验算..."):
                        bridge_result = run_abaqus_verification(bridge_config)
                    if bridge_result.status == "completed":
                        st.success("Abaqus 验算完成")
                    elif bridge_result.status in {"failed", "timeout"}:
                        st.error(f"Abaqus 状态：{bridge_result.status}")
                    else:
                        st.warning(f"Abaqus 状态：{bridge_result.status}")
                    _show_abaqus_summary(bridge_result.work_dir)
                else:
                    st.info("任务已完成材料训练；Abaqus 验算未执行，因为尚未勾选确认。")


def _render_special_ai_task(
    payload: dict[str, Any], *, source_text: str, execute_clicked: bool
) -> None:
    """Render and safely dispatch non-material tasks emitted by an LLM."""

    task_type = str(payload.get("task_type", "")).strip()
    st.caption("当前解析来源：语言模型解析")
    st.json(payload)
    for warning in (
        payload.get("warnings", []) if isinstance(payload.get("warnings"), list) else []
    ):
        st.warning(str(warning))

    dry_payload = merge_with_defaults(payload)
    schema_result = validate_task_payload(dry_payload)
    with st.expander("Dry-Run 预览（执行前检查）", expanded=True):
        st.markdown(dry_run_summary(dry_payload, schema_result))
        plan = build_executable_plan(dry_payload)
        st.dataframe(
            [
                {
                    "步骤": step.index,
                    "动作": step.label,
                    "需要 Abaqus": "是" if step.requires_abaqus else "否",
                    "状态": step.status,
                }
                for step in plan.steps
            ],
            use_container_width=True,
            hide_index=True,
            height=min(260, 42 + 30 * max(1, len(plan.steps))),
        )
    if not schema_result.valid:
        st.error("任务字段不完整，已阻止执行。请修改描述后重新解析。")
        return

    if task_type == "odb_extraction":
        st.info(
            "ODB 提取只允许从案例库中选择已归档文件，以保证 Case ID、单位和结果来源可追溯。"
        )
        if execute_clicked:
            st.warning("未读取任意路径。请进入“案例库”，选择案例后执行 ODB 提取。")
        return

    if not execute_clicked:
        return

    try:
        if task_type == "batch_parameter_sweep":
            _execute_ai_batch_plan(payload)
        elif task_type == "case_library_query":
            _execute_ai_case_query(payload, source_text=source_text)
        elif task_type == "surrogate_training":
            _execute_ai_surrogate_training(payload)
        elif task_type == "closed_loop_report":
            report = generate_closed_loop_report()
            st.session_state["selected_closed_loop_report"] = str(report.report_dir)
            st.success(f"闭环报告已生成：{report.report_dir}")
            st.caption(f"报告：`{report.report_path}`")
    except Exception as exc:
        st.error(f"任务执行失败：{type(exc).__name__}: {exc}")


def _execute_ai_batch_plan(payload: dict[str, Any]) -> None:
    batch = payload.get("batch") if isinstance(payload.get("batch"), dict) else {}
    raw_values = batch.get("yield_strengths", [])
    if not isinstance(raw_values, list):
        raise ValueError("yield_strengths 必须是数值列表。")
    yield_strengths = [float(value) for value in raw_values]
    if not yield_strengths:
        raise ValueError("yield_strengths 不能为空。")
    plan = create_parameter_sweep_plan(
        name=_payload_text(batch, "name", "ai_parameter_sweep"),
        material_type=_payload_text(batch, "material_type", "j2"),
        yield_strengths=yield_strengths,
    )
    st.session_state["selected_batch_plan"] = str(plan.plan_dir)
    st.success(f"批量计划已创建：{plan.plan_dir}")
    st.info("本次只创建计划，没有训练样本，也没有提交 Abaqus。")
    st.dataframe(
        batch_sample_table_rows(plan), use_container_width=True, hide_index=True
    )


def _execute_ai_case_query(payload: dict[str, Any], *, source_text: str) -> None:
    query_section = (
        payload.get("query") if isinstance(payload.get("query"), dict) else {}
    )
    filters = query_section.get("filters", {})
    filter_text = json.dumps(filters, ensure_ascii=False) if filters else ""
    rows = search_cases_by_text(
        f"{source_text} {filter_text}".strip(),
        top_k=10,
        training_eligible_only=bool(query_section.get("training_eligible_only", False)),
    )
    if not rows:
        st.warning("没有检索到匹配案例。")
        return
    st.success(f"检索到 {len(rows)} 个案例")
    st.dataframe(
        [
            {
                "Case ID": row["case_id"],
                "标题": row["title"],
                "相关度": round(float(row["score"]), 4),
                "命中词": ", ".join(row["matched_terms"]),
                "执行状态": row["execution_state"],
                "可训练": "是" if row["training_eligible"] else "否",
            }
            for row in rows
        ],
        use_container_width=True,
        hide_index=True,
    )


def _execute_ai_surrogate_training(payload: dict[str, Any]) -> None:
    surrogate = (
        payload.get("surrogate") if isinstance(payload.get("surrogate"), dict) else {}
    )
    requested = _payload_text(surrogate, "dataset_dir", "")
    exports = list_dataset_exports()
    allowed = {str(path.resolve()): path.resolve() for path in exports}
    requested_path = Path(requested).expanduser().resolve() if requested else None
    if requested_path is None or str(requested_path) not in allowed:
        raise ValueError(
            "dataset_dir 必须精确指向应用已登记的数据集导出目录；请先在“代理模型”页选择数据集。"
        )
    models = surrogate.get("models", ["random_forest", "mlp", "gbr"])
    if not isinstance(models, list):
        raise ValueError("models 必须是模型名称列表。")
    normalized_models = [str(value).strip().lower() for value in models]
    allowed_models = {"random_forest", "mlp", "gbr"}
    if not normalized_models or any(
        model not in allowed_models for model in normalized_models
    ):
        raise ValueError("models 仅支持 random_forest、mlp 和 gbr。")
    target = _payload_text(surrogate, "target_column", DEFAULT_TARGET)
    rows = []
    for model in dict.fromkeys(normalized_models):
        run = train_surrogate_from_dataset(
            requested_path,
            target_column=target,
            model_kind=model,
        )
        rows.append(
            {
                "模型": model,
                "MAE": run.metrics.get("mae"),
                "RMSE": run.metrics.get("rmse"),
                "R2": run.metrics.get("r2"),
                "运行目录": str(run.run_dir),
            }
        )
    st.success(f"已完成 {len(rows)} 个代理模型训练")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _execute_composite_ai_task(payload: dict[str, Any], *, allow_abaqus: bool) -> None:
    try:
        config = _composite_config_from_ai_payload(payload, allow_abaqus=allow_abaqus)
    except ValueError as exc:
        st.error(f"复合材料任务参数无效：{exc}")
        return

    with st.spinner("正在执行复合材料自然语言任务：生成 RVE、带孔板验证模型和报告..."):
        try:
            result = run_composite_plate_workflow(config)
        except Exception as exc:
            st.error(f"复合材料任务执行失败：{type(exc).__name__}: {exc}")
            return
    st.session_state["selected_composite_run"] = str(result.run_dir)
    st.success(f"复合材料仿真任务已完成：{result.run_dir.name}")

    cols = st.columns(5)
    cols[0].metric("Abaqus", result.abaqus_status)
    cols[1].metric("E1 MPa", _fmt_metric(result.effective_properties.get("E1")))
    cols[2].metric("E2 MPa", _fmt_metric(result.effective_properties.get("E2")))
    cols[3].metric("G12 MPa", _fmt_metric(result.effective_properties.get("G12")))
    cols[4].metric(
        "Kt 估算",
        _fmt_metric(
            result.engineering_estimates.get("stress_concentration_factor_estimate")
        ),
    )
    st.caption(f"Run: `{result.run_dir}`")
    st.caption(f"Report: `{result.report_path}`")
    if result.microstructure_png.exists() or result.plate_preview_png.exists():
        c1, c2 = st.columns(2)
        _show_image(c1, result.microstructure_png, "微观 RVE")
        _show_image(c2, result.plate_preview_png, "3D 带孔板")
    if result.report_path.exists():
        with st.expander("复合材料任务报告", expanded=False):
            st.markdown(result.report_path.read_text(encoding="utf-8"))


def _composite_config_from_ai_payload(
    payload: dict[str, Any], *, allow_abaqus: bool
) -> CompositePlateConfig:
    composite = (
        payload.get("composite") if isinstance(payload.get("composite"), dict) else {}
    )
    abaqus = payload.get("abaqus") if isinstance(payload.get("abaqus"), dict) else {}
    name = _payload_text(composite, "name", "ai_composite_plate_hole")
    run_abaqus = allow_abaqus and _payload_bool(abaqus, "run_check", False)
    submit_job = allow_abaqus and _payload_bool(abaqus, "submit_job", False)
    return CompositePlateConfig(
        name=name,
        output_dir=COMPOSITE_ROOT,
        fiber_volume_fraction=_payload_float(
            composite, "fiber_volume_fraction", 0.55, lower=0.05, upper=0.8
        ),
        fiber_e=_payload_float(composite, "fiber_e", 230_000.0, lower=1.0),
        fiber_nu=_payload_float(composite, "fiber_nu", 0.20, lower=0.0, upper=0.49),
        matrix_e=_payload_float(composite, "matrix_e", 3_500.0, lower=1.0),
        matrix_nu=_payload_float(composite, "matrix_nu", 0.35, lower=0.0, upper=0.49),
        interface_efficiency=_payload_float(
            composite, "interface_efficiency", 0.92, lower=0.1, upper=1.5
        ),
        interface_thickness_ratio=_payload_float(
            composite, "interface_thickness_ratio", 0.18, lower=0.0, upper=0.8
        ),
        length=_payload_float(composite, "length", 120.0, lower=1.0),
        width=_payload_float(composite, "width", 40.0, lower=1.0),
        thickness=_payload_float(composite, "thickness", 2.0, lower=0.01),
        hole_radius=_payload_float(composite, "hole_radius", 5.0, lower=0.01),
        applied_strain=_payload_float(composite, "applied_strain", 0.003, lower=1e-6),
        mesh_size=_payload_float(composite, "mesh_size", 2.0, lower=0.05),
        micro_fiber_count=_payload_int(
            composite, "micro_fiber_count", 16, lower=1, upper=200
        ),
        micro_nx=_payload_int(composite, "micro_nx", 8, lower=2, upper=80),
        micro_ny=_payload_int(composite, "micro_ny", 18, lower=2, upper=120),
        micro_nz=_payload_int(composite, "micro_nz", 18, lower=2, upper=120),
        random_seed=_payload_int(composite, "random_seed", 7, lower=1, upper=999_999),
        cpus=_payload_int(composite, "cpus", 4, lower=1, upper=64),
        run_abaqus=run_abaqus,
        submit_job=submit_job,
    )


def _payload_text(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    text = str(value).strip()
    return text or default


def _payload_bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "是", "需要"}


def _payload_float(
    data: dict[str, Any],
    key: str,
    default: float,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> float:
    try:
        value = float(data.get(key, default))
    except (TypeError, ValueError):
        value = float(default)
    if lower is not None and value < lower:
        value = float(default)
    if upper is not None and value > upper:
        value = float(default)
    return value


def _payload_int(
    data: dict[str, Any],
    key: str,
    default: int,
    *,
    lower: int | None = None,
    upper: int | None = None,
) -> int:
    value = int(round(_payload_float(data, key, float(default))))
    if lower is not None:
        value = max(lower, value)
    if upper is not None:
        value = min(upper, value)
    return value


def _training_panel() -> None:
    _ensure_training_defaults()
    _sanitize_training_state()
    left, right = st.columns([0.42, 0.58], gap="large")

    with left:
        st.subheader("材料与训练参数")
        _material_library_controls()
        with st.expander("材料参数建议（可选）", expanded=False):
            recommendation_text = st.text_area(
                "材料描述",
                value="6061 铝板，轧制方向存在各向异性，用于带孔板拉伸验证。",
                height=90,
                key="train_recommendation_text",
            )
            allow_recommendation = st.checkbox(
                "允许调用外部模型服务生成建议",
                value=False,
                key="train_allow_recommendation",
            )
            recommend_clicked = st.button(
                "生成并填入建议参数",
                use_container_width=True,
                key="train_recommend_parameters",
            )
            if recommend_clicked:
                if not allow_recommendation:
                    st.info(
                        "勾选允许调用外部模型服务后再生成建议；未配置服务时可继续手动填写参数。"
                    )
                else:
                    recommendation = recommend_parameters(recommendation_text)
                    if recommendation is None:
                        st.warning(
                            "未获得参数建议。请检查模型服务配置，或先手动设置材料参数。"
                        )
                    else:
                        params = recommendation.parameters
                        st.session_state["train_material_type"] = (
                            recommendation.material_type
                            if recommendation.material_type
                            in {"j2", "hill", "barlat", "neo_hookean", "mooney_rivlin"}
                            else "j2"
                        )
                        st.session_state["train_E"] = float(
                            params.get(
                                "youngs_modulus",
                                st.session_state.get("train_E", 200_000.0),
                            )
                        )
                        st.session_state["train_nu"] = float(
                            params.get(
                                "poisson_ratio", st.session_state.get("train_nu", 0.3)
                            )
                        )
                        st.session_state["train_sy"] = float(
                            params.get(
                                "yield_strength", st.session_state.get("train_sy", 60.0)
                            )
                        )
                        st.session_state["train_C"] = float(
                            params.get("c_value", st.session_state.get("train_C", 1.0))
                        )
                        st.session_state["train_gamma"] = float(
                            params.get(
                                "gamma", st.session_state.get("train_gamma", 1.0)
                            )
                        )
                        st.session_state["train_n_load_cases"] = int(
                            params.get(
                                "n_load_cases",
                                st.session_state.get("train_n_load_cases", 40),
                            )
                        )
                        st.session_state["train_n_sequence"] = int(
                            params.get(
                                "n_sequence",
                                st.session_state.get("train_n_sequence", 4),
                            )
                        )
                        ratios = params.get("hill_ratios") or []
                        if len(ratios) == 6:
                            for idx, value in enumerate(ratios):
                                st.session_state[f"train_hill_r{idx + 1}"] = max(
                                    MIN_HILL_RATIO, float(value)
                                )
                        st.success("参数建议已写入训练表单")
                        st.caption(recommendation.rationale)
                        if recommendation.caveats:
                            st.info(recommendation.caveats)
                        st.rerun()
        st.divider()
        material_type = st.segmented_control(
            "参考材料",
            options=["j2", "hill", "barlat", "neo_hookean", "mooney_rivlin"],
            format_func=lambda item: {
                "j2": "J2 isotropic",
                "hill": "Hill anisotropic",
                "barlat": "Barlat/Yld2000 experimental",
                "neo_hookean": "Neo-Hookean hyperelastic",
                "mooney_rivlin": "Mooney-Rivlin hyperelastic",
            }[item],
            key="train_material_type",
        )
        if material_type is None:
            material_type = "j2"
        name = st.text_input("模型名称", key="train_name")

        c1, c2, c3 = st.columns(3)
        youngs_modulus = c1.number_input(
            "E (MPa)", min_value=1.0, step=1000.0, key="train_E"
        )
        poisson_ratio = c2.number_input(
            "nu", min_value=0.0, max_value=0.49, step=0.01, key="train_nu"
        )
        yield_strength = c3.number_input(
            "sy (MPa)",
            min_value=1.0,
            step=5.0,
            key="train_sy",
        )

        st.divider()
        hill_ratios = tuple(
            st.session_state.get(f"train_hill_r{i + 1}", value)
            for i, value in enumerate(HILL_RATIO_DEFAULTS)
        )
        if material_type == "hill":
            with st.expander("Hill 各向异性比例", expanded=True):
                hcols = st.columns(6)
                hill_ratios = tuple(
                    hcols[i].number_input(
                        f"r{i + 1}",
                        min_value=MIN_HILL_RATIO,
                        max_value=10.0,
                        value=float(
                            st.session_state.get(
                                f"train_hill_r{i + 1}", HILL_RATIO_DEFAULTS[i]
                            )
                        ),
                        step=0.05,
                        key=f"train_hill_r{i + 1}",
                    )
                    for i in range(6)
                )
        barlat_alphas = tuple(
            st.session_state.get(f"train_barlat_a{i + 1}", value)
            for i, value in enumerate(BARLAT_ALPHA_DEFAULTS)
        )
        barlat_exponent = float(st.session_state.get("train_barlat_exponent", 8.0))
        if material_type == "barlat":
            st.info(
                "Barlat 当前是工程入口：App 接收 8 个 Yld2000-2D 风格 alpha，内部展开为 pyLabFEA 可用的 18 参数近似。"
                "它适合学习与快速对比，不是严格的 Yld2000-2D 实验标定器。正式材料卡仍需要用实验数据重新识别。"
                "中文说明见 docs/learning/BARLAT_YLD2000_TO_YLD2004_CN.md。"
            )
            with st.expander("Barlat/Yld2000-2D 参数", expanded=True):
                barlat_exponent = st.number_input(
                    "指数 m",
                    min_value=2.0,
                    max_value=20.0,
                    value=float(st.session_state.get("train_barlat_exponent", 8.0)),
                    step=1.0,
                    key="train_barlat_exponent",
                    help="通常铝合金 FCC 取 8，钢材 BCC 可从 6 起步。",
                )
                alpha_cols = st.columns(4)
                alpha_values = []
                for i, default in enumerate(BARLAT_ALPHA_DEFAULTS):
                    alpha_values.append(
                        alpha_cols[i % 4].number_input(
                            f"a{i + 1}",
                            min_value=0.05,
                            max_value=5.0,
                            value=float(
                                st.session_state.get(f"train_barlat_a{i + 1}", default)
                            ),
                            step=0.05,
                            key=f"train_barlat_a{i + 1}",
                        )
                    )
                barlat_alphas = tuple(float(value) for value in alpha_values)

        hyperelastic_c10 = float(st.session_state.get("train_hyperelastic_c10", 0.5))
        hyperelastic_c01 = float(st.session_state.get("train_hyperelastic_c01", 0.2))
        hyperelastic_d1 = float(st.session_state.get("train_hyperelastic_d1", 0.0))
        if material_type in {"neo_hookean", "mooney_rivlin"}:
            with st.expander("超弹性参数", expanded=True):
                h1, h2, h3 = st.columns(3)
                hyperelastic_c10 = h1.number_input(
                    "C10 (MPa)",
                    min_value=1.0e-6,
                    value=hyperelastic_c10,
                    step=0.1,
                    key="train_hyperelastic_c10",
                )
                hyperelastic_c01 = h2.number_input(
                    "C01 (MPa)",
                    min_value=0.0,
                    value=hyperelastic_c01,
                    step=0.1,
                    key="train_hyperelastic_c01",
                    disabled=material_type == "neo_hookean",
                )
                hyperelastic_d1 = h3.number_input(
                    "D1",
                    min_value=0.0,
                    value=hyperelastic_d1,
                    step=0.001,
                    format="%.6f",
                    key="train_hyperelastic_d1",
                )
                st.caption(
                    "超弹性分支生成应力-应变曲线和 Abaqus *HYPERELASTIC 材料卡，不走 SVC 屈服面训练。"
                )

        st.divider()
        with st.expander("训练设置", expanded=True):
            c1, c2 = st.columns(2)
            c_value = c1.number_input("SVC C", min_value=0.01, step=0.5, key="train_C")
            gamma = c2.number_input(
                "SVC gamma", min_value=0.01, step=0.25, key="train_gamma"
            )

            c3, c4, c5 = st.columns(3)
            n_load_cases = c3.number_input(
                "载荷方向数", min_value=8, step=8, key="train_n_load_cases"
            )
            n_sequence = c4.number_input(
                "采样序列", min_value=2, step=1, key="train_n_sequence"
            )
            test_size = c5.number_input(
                "测试点数", min_value=20, step=20, key="train_test_size"
            )

            c6, c7 = st.columns(2)
            plot_mesh = c6.number_input(
                "屈服面网格", min_value=20, step=10, key="train_plot_mesh"
            )
            calculate_curves = c7.checkbox(
                "同时计算 pyLabFEA 曲线", key="train_calculate_curves"
            )

        run_clicked = st.button(
            "开始训练", type="primary", use_container_width=True, key="train_run"
        )

    with right:
        st.subheader("本次任务")
        st.write(
            "训练完成后会生成 `summary.json`、屈服面图、UMAT 参数 CSV/JSON 和 Markdown 报告。"
        )
        if run_clicked:
            if material_type == "hill" and any(
                float(value) <= 0 for value in hill_ratios
            ):
                st.error(
                    "Hill 各向异性比例必须全部为正数。请使用默认模板或输入大于 0 的比例。"
                )
                return
            if material_type == "barlat" and any(
                float(value) <= 0 for value in barlat_alphas
            ):
                st.error("Barlat alpha 参数必须全部为正数。")
                return
            config = WorkbenchConfig(
                material_type=material_type,
                name=name.strip() or f"app_{material_type}",
                output_dir=RUNS_ROOT,
                youngs_modulus=float(youngs_modulus),
                poisson_ratio=float(poisson_ratio),
                yield_strength=float(yield_strength),
                hill_ratios=tuple(float(v) for v in hill_ratios),
                barlat_alphas=tuple(float(v) for v in barlat_alphas),
                barlat_exponent=float(barlat_exponent),
                hyperelastic_c10=float(hyperelastic_c10),
                hyperelastic_c01=float(hyperelastic_c01),
                hyperelastic_d1=float(hyperelastic_d1),
                c_value=float(c_value),
                gamma=float(gamma),
                n_load_cases=int(n_load_cases),
                n_sequence=int(n_sequence),
                calculate_curves=bool(calculate_curves),
                test_size=int(test_size),
                plot_mesh=int(plot_mesh),
            )
            with st.spinner("正在训练材料模型并生成报告..."):
                result = _run_material_training_with_feedback(
                    config, "正在训练材料模型..."
                )
            if result is None:
                return
            st.session_state["selected_run_dir"] = str(result.run_dir)
            st.success("训练完成")
            _show_run_summary(result.run_dir)
        else:
            st.info("设置参数后点击“开始训练”。")


def _data_import_panel(selected_run: Path | None) -> None:
    st.subheader("数据导入")
    left, right = st.columns([0.42, 0.58], gap="large")

    with left:
        st.markdown("**导入设置**")
        source_kind = st.selectbox(
            "数据类型",
            ["experiment_curve", "abaqus_batch_result"],
            format_func=lambda item: (
                "实验应力-应变曲线"
                if item == "experiment_curve"
                else "Abaqus 批量结果 CSV"
            ),
        )
        material_name = st.text_input("材料/数据集名称", value="imported_material")
        uploaded = st.file_uploader("上传 CSV", type=["csv", "txt"])
        import_upload_clicked = st.button(
            "导入上传文件",
            type="primary",
            use_container_width=True,
            key="import_upload",
        )

        st.divider()
        st.markdown("**从当前 Abaqus 结果导入**")
        abaqus_csv = _find_abaqus_result_csv(selected_run)
        if abaqus_csv:
            st.caption(f"`{abaqus_csv}`")
            import_abaqus_clicked = st.button(
                "导入当前 Abaqus CSV",
                use_container_width=True,
                key="import_current_abaqus_csv",
            )
        else:
            st.info("当前选择的 run 没有 Abaqus 结果 CSV。")
            import_abaqus_clicked = False

    with right:
        st.markdown("**导入结果**")
        result_dir: Path | None = None
        if import_upload_clicked:
            if uploaded is None:
                st.warning("请先选择一个 CSV 文件。")
            else:
                with st.spinner("正在解析并归档 CSV..."):
                    result = import_csv_dataset(
                        source_bytes=uploaded.getvalue(),
                        source_name=uploaded.name,
                        source_kind=source_kind,
                        material_name=material_name.strip() or "imported_material",
                    )
                result_dir = result.import_dir
                st.session_state["selected_import_dir"] = str(result_dir)
                st.success("导入完成")

        if import_abaqus_clicked and abaqus_csv:
            with st.spinner("正在导入当前 Abaqus 结果 CSV..."):
                result = import_csv_dataset(
                    source_path=abaqus_csv,
                    source_name=abaqus_csv.name,
                    source_kind="abaqus_batch_result",
                    material_name=(
                        selected_run.name
                        if selected_run
                        else material_name.strip() or "abaqus_result"
                    ),
                )
            result_dir = result.import_dir
            st.session_state["selected_import_dir"] = str(result_dir)
            st.success("Abaqus CSV 已导入")

        imports = list_imports()
        if imports:
            options = [str(path) for path in imports]
            default_index = 0
            selected_import = st.session_state.get("selected_import_dir")
            if selected_import in options:
                default_index = options.index(selected_import)
            chosen = st.selectbox(
                "选择已导入数据",
                options,
                index=default_index,
                format_func=lambda item: Path(item).name,
            )
            chosen_dir = Path(chosen)
            _show_import_summary(chosen_dir)
            st.divider()
            st.markdown("**从实验曲线训练材料**")
            curve_config = imported_curve_to_config(chosen_dir, output_dir=RUNS_ROOT)
            if curve_config is None:
                st.info("该导入目录暂不能转换为材料训练配置。")
            else:
                cols = st.columns(3)
                cols[0].metric("估算 E (MPa)", _fmt_metric(curve_config.youngs_modulus))
                cols[1].metric(
                    "估算 sy (MPa)", _fmt_metric(curve_config.yield_strength)
                )
                cols[2].metric("模型", curve_config.material_type.upper())
                confirm_curve_train = st.checkbox(
                    "确认使用该曲线估算参数训练材料模型",
                    value=False,
                    key="import_confirm_train_curve",
                )
                train_from_import_clicked = st.button(
                    "从该曲线训练材料模型",
                    type="primary",
                    use_container_width=True,
                    disabled=not confirm_curve_train,
                    key="import_train_curve",
                )
                if train_from_import_clicked:
                    result = _run_material_training_with_feedback(
                        curve_config, "正在根据导入曲线训练材料模型..."
                    )
                    if result is not None:
                        st.session_state["selected_run_dir"] = str(result.run_dir)
                        st.success(f"材料模型训练完成：{result.run_dir.name}")
                        _show_run_summary(result.run_dir)
                st.markdown("**实验曲线闭环验证**")
                validation_cols = st.columns([0.5, 0.25, 0.25])
                validation_material = validation_cols[0].selectbox(
                    "验证材料模型",
                    ["j2", "hill", "barlat"],
                    format_func=lambda item: {
                        "j2": "J2 各向同性",
                        "hill": "Hill 各向异性",
                        "barlat": "Barlat 近似",
                    }[item],
                    key="import_validation_material",
                )
                validation_cases = validation_cols[1].number_input(
                    "训练载荷数",
                    min_value=8,
                    max_value=120,
                    value=24,
                    step=4,
                    key="import_validation_cases",
                )
                validation_tests = validation_cols[2].number_input(
                    "测试点数",
                    min_value=20,
                    max_value=300,
                    value=40,
                    step=10,
                    key="import_validation_tests",
                )
                validate_curve_clicked = st.button(
                    "训练并验证实验曲线",
                    use_container_width=True,
                    key="import_validate_curve",
                )
                if validate_curve_clicked:
                    try:
                        with st.spinner("正在训练材料并生成实验/Workbench 曲线对比..."):
                            validation = validate_imported_curve_with_workbench(
                                chosen_dir,
                                material_type=validation_material,
                                output_dir=RUNS_ROOT,
                                n_load_cases=int(validation_cases),
                                test_size=int(validation_tests),
                            )
                        st.success(f"验证完成：{validation.workbench_run_dir.name}")
                        metric_cols = st.columns(3)
                        metric_cols[0].metric("R²", _fmt_metric(validation.r2))
                        metric_cols[1].metric(
                            "MAE (MPa)", _fmt_metric(validation.mean_abs_error_mpa)
                        )
                        metric_cols[2].metric(
                            "Max Error (MPa)", _fmt_metric(validation.max_abs_error_mpa)
                        )
                        st.image(
                            str(validation.overlay_plot),
                            caption="实验曲线 vs Workbench 生成曲线",
                        )
                        st.caption(f"验证报告：`{validation.report_path}`")
                    except Exception as exc:
                        st.error(f"实验曲线验证失败：{exc}")
        elif result_dir is None:
            st.info("还没有导入数据。")


def _case_library_panel() -> None:
    st.subheader("案例库")
    st.caption("把每天完成的 Abaqus 仿真案例沉淀成可检索、可训练、可复用的工程资产。")
    left, right = st.columns([0.38, 0.62], gap="large")

    with left:
        st.markdown("**录入新案例**")
        default_folder = str(RUNS_ROOT)
        source_folder = st.text_input(
            "Abaqus 案例文件夹或单个 .inp 文件",
            value=default_folder,
            key="case_source_folder",
        )
        title = st.text_input("案例标题", value="Abaqus 仿真案例", key="case_title")
        tags = st.text_input("标签", value="Abaqus, 成功案例", key="case_tags")
        status = st.selectbox(
            "人工状态",
            ["success", "candidate", "failed", "needs_review"],
            index=0,
            key="case_status",
        )
        unit_option = st.selectbox(
            "Abaqus 单位制",
            ["mm-N-s-MPa", "SI-m-kg-s-Pa", "未声明（仅归档）", "自定义"],
            index=0,
            key="case_unit_system",
        )
        custom_unit_system = ""
        if unit_option == "自定义":
            custom_unit_system = st.text_input(
                "自定义单位制名称",
                value="",
                placeholder="例如 mm-kN-s-GPa",
                key="case_custom_unit_system",
            )
        solver_version = st.text_input(
            "Abaqus 版本（可选）",
            value="",
            placeholder="例如 2024",
            key="case_solver_version",
        )
        description = st.text_area(
            "案例说明",
            value="记录模型目的、边界条件、材料、载荷、求解结果和工程结论。",
            height=90,
            key="case_description",
        )
        lessons = st.text_area("经验记录", value="", height=80, key="case_lessons")
        next_actions = st.text_area(
            "后续动作", value="", height=70, key="case_next_actions"
        )
        scan_clicked = st.button(
            "扫描并归档案例",
            type="primary",
            use_container_width=True,
            key="case_scan_archive",
        )

        if scan_clicked:
            try:
                declared_units = _selected_case_units(unit_option, custom_unit_system)
                with st.spinner("正在扫描案例并生成案例摘要..."):
                    summary = scan_case_folder(
                        source_folder,
                        title=title,
                        tags=tags,
                        description=description,
                        status=status,
                        lessons_learned=lessons,
                        next_actions=next_actions,
                        units=declared_units,
                        solver_version=solver_version,
                    )
                st.session_state["selected_case_dir"] = summary.case_dir
                st.success(f"案例已归档：{summary.case_id}")
                quality = getattr(summary, "quality", {}) or evaluate_case_quality(
                    summary
                )
                if quality.get("training_eligible"):
                    st.success("质量门通过：该案例可进入训练数据集。")
                else:
                    blockers = ", ".join(quality.get("blocking_reasons", []))
                    st.warning(f"案例仅完成归档，暂不可训练：{blockers}")
                st.write(summary.case_dir)
            except Exception as exc:
                st.error(f"案例归档失败：{exc}")

        with st.expander("批量导入 + 重复检测", expanded=False):
            st.caption("扫描整个父目录，自动导入所有子文件夹为案例。")
            batch_parent = st.text_input(
                "父目录",
                value="",
                placeholder="包含多个 Abaqus 案例的目录",
                key="case_batch_parent",
            )
            skip_dup = st.checkbox(
                "跳过已有案例", value=True, key="case_batch_skip_dup"
            )
            batch_tags = st.text_input(
                "批量标签",
                value="",
                placeholder="逗号分隔，例如 j2, 批量导入",
                key="case_batch_tags",
            )
            if st.button("批量导入", use_container_width=True, key="case_batch_import"):
                if not batch_parent.strip():
                    st.warning("请输入父目录路径。")
                else:
                    with st.spinner(f"正在批量扫描 {batch_parent} ..."):
                        try:
                            dup_check = find_duplicate_cases(batch_parent)
                            if dup_check:
                                st.warning(
                                    f"检测到 {len(dup_check)} 个可能重复的案例（精确路径或文件名/大小匹配）"
                                )
                                with st.expander("重复详情", expanded=True):
                                    st.dataframe(
                                        [
                                            {
                                                "Case ID": d["case_id"],
                                                "Title": d["title"],
                                                "Match": d["match_type"],
                                                "Status": d["status"],
                                            }
                                            for d in dup_check
                                        ],
                                        use_container_width=True,
                                        hide_index=True,
                                        height=200,
                                    )
                            tag_list = [
                                t.strip() for t in batch_tags.split(",") if t.strip()
                            ]
                            result = batch_import_cases(
                                batch_parent,
                                tags=tag_list,
                                skip_existing=bool(skip_dup),
                                units=_selected_case_units(
                                    unit_option, custom_unit_system
                                ),
                                solver_version=solver_version,
                            )
                            st.success(
                                f"导入完成：{result['imported']} 新增, {result['skipped']} 跳过, {result['failed']} 失败"
                            )
                            if result["failed_details"]:
                                st.warning(f"失败详情：{result['failed_details']}")
                        except Exception as exc:
                            st.error(f"批量导入失败：{exc}")

        st.divider()
        st.markdown("**训练数据集**")
        dataset_name = st.text_input(
            "数据集名称", value="case_dataset", key="case_dataset_name"
        )
        training_only = st.checkbox(
            "仅导出质量门合格案例",
            value=True,
            key="case_dataset_training_only",
        )
        export_dataset_clicked = st.button(
            "导出案例库训练数据集", use_container_width=True, key="case_export_dataset"
        )
        if export_dataset_clicked:
            try:
                export = export_case_dataset(
                    name=dataset_name, training_only=training_only
                )
                if export.case_count:
                    st.success(f"训练数据集已导出：{export.export_dir}")
                else:
                    st.warning("没有案例通过训练质量门，已生成空数据集与排除原因清单。")
                st.caption(
                    f"候选 {export.source_case_count}，导出 {export.case_count}，排除 {export.skipped_case_count}"
                )
                st.caption(f"`{export.dataset_csv}`")
                st.caption(f"`{export.frame_series_index_csv}`")
            except Exception as exc:
                st.error(f"训练数据集导出失败：{exc}")
        with st.expander("批量导出向导", expanded=False):
            wizard_cases = list_cases()
            if not wizard_cases:
                st.info("暂无可筛选案例。")
            else:
                status_options = sorted(
                    {case.status for case in wizard_cases if case.status}
                )
                material_options = sorted(
                    {
                        str((case.parameters or {}).get("material_type", "")).strip()
                        for case in wizard_cases
                        if str((case.parameters or {}).get("material_type", "")).strip()
                    }
                )
                selected_statuses = st.multiselect(
                    "状态",
                    status_options,
                    default=status_options,
                    key="case_export_status_filter",
                )
                selected_materials = st.multiselect(
                    "材料模型",
                    material_options,
                    default=[],
                    key="case_export_material_filter",
                )
                selected_case_types = st.multiselect(
                    "案例类型",
                    ["metal", "composite", "unknown"],
                    default=[],
                    format_func=lambda item: {
                        "metal": "金属/塑性",
                        "composite": "复合材料/RVE",
                        "unknown": "未分类",
                    }[item],
                    key="case_export_type_filter",
                )
                tag_filter = st.text_input(
                    "标签/关键词", value="", key="case_export_tag_filter"
                )
                d1, d2 = st.columns(2)
                date_from = d1.text_input(
                    "起始日期",
                    value="",
                    placeholder="YYYY-MM-DD",
                    key="case_export_date_from",
                )
                date_to = d2.text_input(
                    "结束日期",
                    value="",
                    placeholder="YYYY-MM-DD",
                    key="case_export_date_to",
                )
                matched_cases = filter_cases(
                    wizard_cases,
                    tags=tag_filter,
                    statuses=selected_statuses,
                    material_types=selected_materials,
                    case_types=selected_case_types,
                    date_from=date_from,
                    date_to=date_to,
                )
                st.metric("匹配案例数", len(matched_cases))
                if matched_cases:
                    preview_rows = case_table_rows(matched_cases)
                    for row, case in zip(preview_rows, matched_cases):
                        row["类型"] = infer_case_type(case)
                    st.dataframe(
                        preview_rows,
                        use_container_width=True,
                        hide_index=True,
                        height=260,
                    )
                filtered_export_name = st.text_input(
                    "筛选数据集名称",
                    value=f"{dataset_name}_filtered",
                    key="case_filtered_dataset_name",
                )
                export_filtered_clicked = st.button(
                    "导出筛选案例数据集",
                    use_container_width=True,
                    disabled=not matched_cases,
                    key="case_export_filtered_dataset",
                )
                if export_filtered_clicked:
                    try:
                        export = export_case_dataset(
                            name=filtered_export_name.strip()
                            or "case_dataset_filtered",
                            case_dirs=[case.case_dir for case in matched_cases],
                            training_only=training_only,
                        )
                        st.success(f"筛选数据集已导出：{export.export_dir}")
                        st.caption(f"`{export.dataset_csv}`")
                        st.caption(f"`{export.frame_series_index_csv}`")
                    except Exception as exc:
                        st.error(f"筛选数据集导出失败：{exc}")

    with right:
        st.markdown("**已归档案例**")
        cases = list_cases()
        if not cases:
            st.info("还没有案例。先在左侧录入一个 Abaqus 案例文件夹或单个 .inp 文件。")
            return

        st.dataframe(
            case_table_rows(cases),
            use_container_width=True,
            hide_index=True,
            height=400,
        )
        options = [case.case_dir for case in cases]
        default_index = 0
        selected_case_dir = st.session_state.get("selected_case_dir")
        if selected_case_dir in options:
            default_index = options.index(selected_case_dir)
        chosen_dir = st.selectbox(
            "选择案例",
            options,
            index=default_index,
            format_func=lambda item: Path(item).name,
            key="case_selector",
        )
        summary = load_case_summary(chosen_dir)
        st.session_state["selected_case_dir"] = chosen_dir
        _show_case_summary(summary)


def _show_case_summary(summary: Any) -> None:
    st.markdown(f"**{summary.title}**")
    quality = getattr(summary, "quality", {}) or evaluate_case_quality(summary)
    cols = st.columns(6)
    cols[0].metric("人工状态", summary.status)
    cols[1].metric("执行状态", quality.get("execution_state", "unknown"))
    cols[2].metric("质量分", quality.get("score", 0))
    cols[3].metric("可训练", "是" if quality.get("training_eligible") else "否")
    cols[4].metric("模型", summary.file_counts.get("model", 0))
    cols[5].metric("结果", summary.file_counts.get("result", 0))

    if quality.get("training_eligible"):
        st.success("质量门通过：求解、单位、材料、网格和数值标签证据完整。")
    elif quality.get("status") == "fail":
        st.error("质量门失败：该案例不能作为机器学习真值。")
    else:
        st.warning("案例已归档，但证据尚不完整，暂不进入训练白名单。")
    with st.expander("案例质量体检", expanded=not quality.get("training_eligible")):
        st.dataframe(
            quality_table_rows(quality),
            use_container_width=True,
            hide_index=True,
        )
        if quality.get("recommended_actions"):
            st.markdown("**建议补齐**")
            for action in quality["recommended_actions"]:
                st.write(f"- {action}")

    st.write(f"来源目录：`{summary.source_folder}`")
    if summary.tags:
        st.write("标签：" + " / ".join(summary.tags))
    if summary.description:
        st.markdown("**说明**")
        st.write(summary.description)
    if summary.lessons_learned:
        st.markdown("**经验记录**")
        st.write(summary.lessons_learned)

    inp_rows = inp_feature_table_rows(summary)
    if inp_rows:
        st.markdown("**INP 特征摘要**")
        aggregate = (summary.inp_features or {}).get("summary", {})
        feature_cols = st.columns(4)
        feature_cols[0].metric("INP", aggregate.get("inp_file_count", 0))
        feature_cols[1].metric("节点(估算)", aggregate.get("estimated_node_count", 0))
        feature_cols[2].metric(
            "单元(估算)", aggregate.get("estimated_element_count", 0)
        )
        feature_cols[3].metric("材料数", len(aggregate.get("materials", [])))
        st.dataframe(inp_rows, use_container_width=True, hide_index=True, height=400)
        with st.expander("INP 特征 JSON", expanded=False):
            st.json(summary.inp_features)

    result_rows = result_feature_table_rows(summary)
    if result_rows:
        st.markdown("**结果特征摘要**")
        aggregate = (summary.result_features or {}).get("summary", {})
        result_cols = st.columns(5)
        result_cols[0].metric("CSV", aggregate.get("csv_file_count", 0))
        result_cols[1].metric("ODB", aggregate.get("odb_file_count", 0))
        result_cols[2].metric("结果行数", aggregate.get("csv_row_count", 0))
        result_cols[3].metric("Warnings", aggregate.get("warning_count", 0))
        result_cols[4].metric("Errors", aggregate.get("error_count", 0))
        st.dataframe(result_rows, use_container_width=True, hide_index=True, height=400)
        with st.expander("结果特征 JSON", expanded=False):
            st.json(summary.result_features)

    _case_odb_extraction_panel(summary)

    similar_rows = find_similar_cases(summary, top_k=5)
    if similar_rows:
        st.markdown("**相似案例推荐**")
        display_rows = []
        for row in similar_rows:
            display_rows.append(
                {
                    "case": row.get("case_id"),
                    "标题": row.get("title"),
                    "状态": row.get("status"),
                    "标签": row.get("tags"),
                    "相似度": round(float(row.get("similarity", 0.0)), 4),
                    "可信状态": row.get("execution_state", "unknown"),
                    "可训练": "是" if row.get("training_eligible") else "否",
                    "相似原因": "；".join(row.get("explanations", [])),
                    "关键匹配": "；".join(row.get("matched_features", [])[:3]),
                    "关键差异": "；".join(row.get("differing_features", [])[:3]),
                    "目录": row.get("case_dir"),
                }
            )
        st.dataframe(
            display_rows, use_container_width=True, hide_index=True, height=260
        )
        with st.expander("相似度分项证据", expanded=False):
            for row in similar_rows:
                st.markdown(
                    f"**{row.get('title')}** · 相似度 {float(row.get('similarity', 0.0)):.3f}"
                )
                st.json(row.get("component_scores", {}))

    category = st.selectbox(
        "文件类别",
        ["all", "model", "result", "data", "image", "report", "script", "other"],
        format_func=lambda item: "全部" if item == "all" else item,
        key="case_file_category",
    )
    rows = file_table_rows(summary, category)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True, height=400)
    else:
        st.info("该类别暂无文件。")

    report_path = Path(summary.case_dir) / "case_report.md"
    if report_path.exists():
        with st.expander("案例报告", expanded=False):
            st.markdown(report_path.read_text(encoding="utf-8"))

    with st.expander("case_summary.json", expanded=False):
        st.json(_load_json(Path(summary.case_dir) / "case_summary.json"))
    package_path = Path(summary.case_dir) / "case_package.json"
    if package_path.exists():
        with st.expander("case_package.json v2", expanded=False):
            st.json(_load_json(package_path))


def _selected_case_units(option: str, custom_value: str = "") -> str | None:
    if option == "未声明（仅归档）":
        return None
    if option == "自定义":
        return custom_value.strip() or None
    return option


def _case_odb_extraction_panel(summary: Any) -> None:
    extraction_rows = odb_extraction_table_rows(summary)
    if extraction_rows:
        st.markdown("**ODB 深度后处理记录**")
        st.dataframe(
            extraction_rows, use_container_width=True, hide_index=True, height=400
        )
    series_rows = odb_frame_series_table_rows(summary)
    if series_rows:
        st.markdown("**ODB 帧曲线记录**")
        st.dataframe(series_rows, use_container_width=True, hide_index=True, height=400)

    odb_options = _case_odb_options(summary)
    if not odb_options:
        return

    with st.expander("提取 ODB 场变量", expanded=False):
        selected_odb = st.selectbox(
            "选择 ODB",
            odb_options,
            format_func=lambda item: Path(item).name,
            key=f"case_odb_select_{summary.case_id}",
        )
        backend = st.selectbox(
            "提取方式",
            ["auto", "mcp", "abaqus_python"],
            format_func=lambda item: {
                "auto": "自动：先 MCP，失败后用 Abaqus Python",
                "mcp": "实时 MCP：可联动视口云图",
                "abaqus_python": "Abaqus Python：批处理读取 ODB",
            }[item],
            key=f"case_odb_backend_{summary.case_id}",
        )
        fields_text = st.text_input(
            "字段",
            value=", ".join(DEFAULT_ODB_FIELDS),
            key=f"case_odb_fields_{summary.case_id}",
        )
        batch_python = st.text_input(
            "SMAPython.exe",
            value=str(DEFAULT_SMAPYTHON),
            key=f"case_odb_smapython_{summary.case_id}",
        )
        c1, c2, c3 = st.columns(3)
        host = c1.text_input(
            "MCP host",
            value=str(st.session_state.get("mcp_host", "127.0.0.1")),
            key=f"case_mcp_host_{summary.case_id}",
        )
        port = c2.number_input(
            "MCP port",
            min_value=1,
            max_value=65535,
            value=int(st.session_state.get("mcp_port", 48152)),
            step=1,
            key=f"case_mcp_port_{summary.case_id}",
        )
        timeout_seconds = c3.number_input(
            "超时(秒)",
            min_value=5.0,
            max_value=300.0,
            value=30.0,
            step=5.0,
            key=f"case_mcp_timeout_{summary.case_id}",
        )
        c4, c5 = st.columns(2)
        max_values = c4.number_input(
            "每个字段最多扫描值数",
            min_value=1_000,
            max_value=5_000_000,
            value=500_000,
            step=50_000,
            key=f"case_odb_max_values_{summary.case_id}",
        )
        capture_contour = c5.checkbox(
            "提取后抓取 S-Mises 云图",
            value=True,
            key=f"case_odb_capture_{summary.case_id}",
        )
        skip_existing = st.checkbox(
            "批量时跳过已有 ODB 提取记录",
            value=True,
            key=f"case_odb_skip_existing_{summary.case_id}",
        )
        b1, b2 = st.columns(2)
        extract_clicked = b1.button(
            "提取当前 ODB",
            type="primary",
            use_container_width=True,
            key=f"case_odb_extract_{summary.case_id}",
        )
        batch_extract_clicked = b2.button(
            "批量提取全部 ODB",
            use_container_width=True,
            key=f"case_odb_batch_extract_{summary.case_id}",
        )

        if extract_clicked or batch_extract_clicked:
            fields = [
                item.strip()
                for item in fields_text.replace("，", ",").split(",")
                if item.strip()
            ]
            config = AbaqusMcpConfig(
                host=host.strip() or "127.0.0.1",
                port=int(port),
                timeout_seconds=float(timeout_seconds),
            )
            batch_config = AbaqusBatchConfig(
                abaqus_python=Path(batch_python),
                timeout_seconds=float(timeout_seconds) * 10,
            )
            targets = list(odb_options) if batch_extract_clicked else [selected_odb]
            if batch_extract_clicked and skip_existing:
                existing_paths = {
                    str(Path(item.get("odb_path", "")).expanduser().resolve())
                    for item in summary.odb_extractions
                    if item.get("odb_path")
                }
                targets = [
                    path
                    for path in targets
                    if str(Path(path).expanduser().resolve()) not in existing_paths
                ]
            if not targets:
                st.info("没有需要新增提取的 ODB。")
                return
            try:
                with st.spinner("正在读取 ODB 最后一帧场变量..."):
                    completed = []
                    for target_odb in targets:
                        extraction = run_case_odb_extraction(
                            summary,
                            target_odb,
                            fields=fields,
                            max_values_per_field=int(max_values),
                            capture_contour=bool(capture_contour)
                            and not batch_extract_clicked,
                            backend=backend,
                            config=config,
                            batch_config=batch_config,
                        )
                        append_odb_extraction(summary, extraction)
                        completed.append(extraction)
                st.success(f"ODB 场变量提取完成：{len(completed)} 个")
                st.json(
                    [
                        {
                            "odb": item.get("odb_name"),
                            "backend": item.get("backend_used"),
                            **item.get("aggregate", {}),
                        }
                        for item in completed
                    ]
                )
                first_image = next(
                    (
                        item.get("viewport_image")
                        for item in completed
                        if item.get("viewport_image")
                    ),
                    None,
                )
                if first_image and Path(first_image).exists():
                    st.image(
                        first_image,
                        caption="ODB S-Mises 云图",
                        use_container_width=True,
                    )
                st.rerun()
            except Exception as exc:
                st.error(f"ODB 场变量提取失败：{exc}")
                st.info(
                    "实时 MCP 需要 Abaqus/CAE 已打开并启动 Socket Bridge；批处理方式需要本机 SMAPython.exe 路径有效。"
                )

    with st.expander("提取 ODB 帧曲线", expanded=False):
        selected_series_odb = st.selectbox(
            "选择 ODB",
            odb_options,
            format_func=lambda item: Path(item).name,
            key=f"case_odb_series_select_{summary.case_id}",
        )
        series_fields_text = st.text_input(
            "曲线字段",
            value=", ".join(DEFAULT_FRAME_SERIES_FIELDS),
            key=f"case_odb_series_fields_{summary.case_id}",
        )
        series_regions_text = st.text_input(
            "命名节点/单元集（可选）",
            value="",
            placeholder="例如 FIXED, LOAD_NODE, EALL；留空则只提取全局曲线",
            key=f"case_odb_series_regions_{summary.case_id}",
        )
        series_python = st.text_input(
            "SMAPython.exe",
            value=str(DEFAULT_SMAPYTHON),
            key=f"case_odb_series_smapython_{summary.case_id}",
        )
        s1, s2, s3 = st.columns(3)
        series_max_values = s1.number_input(
            "每帧每字段最多扫描值数",
            min_value=1_000,
            max_value=2_000_000,
            value=200_000,
            step=50_000,
            key=f"case_odb_series_max_values_{summary.case_id}",
        )
        series_max_frames = s2.number_input(
            "每个 Step 最多帧数",
            min_value=1,
            max_value=5_000,
            value=500,
            step=50,
            key=f"case_odb_series_max_frames_{summary.case_id}",
        )
        series_skip_existing = s3.checkbox(
            "批量跳过已有曲线",
            value=True,
            key=f"case_odb_series_skip_existing_{summary.case_id}",
        )
        sb1, sb2 = st.columns(2)
        series_clicked = sb1.button(
            "提取当前 ODB 曲线",
            type="primary",
            use_container_width=True,
            key=f"case_odb_series_extract_{summary.case_id}",
        )
        series_batch_clicked = sb2.button(
            "批量提取全部 ODB 曲线",
            use_container_width=True,
            key=f"case_odb_series_batch_{summary.case_id}",
        )

        if series_clicked or series_batch_clicked:
            fields = [
                item.strip()
                for item in series_fields_text.replace("，", ",").split(",")
                if item.strip()
            ]
            region_names = [
                item.strip()
                for item in series_regions_text.replace("，", ",").split(",")
                if item.strip()
            ]
            batch_config = AbaqusBatchConfig(
                abaqus_python=Path(series_python),
                timeout_seconds=max(float(series_max_frames), 60.0) * 5,
            )
            targets = (
                list(odb_options) if series_batch_clicked else [selected_series_odb]
            )
            if series_batch_clicked and series_skip_existing:
                existing_paths = {
                    str(Path(item.get("odb_path", "")).expanduser().resolve())
                    for item in summary.odb_frame_series
                    if item.get("odb_path")
                }
                targets = [
                    path
                    for path in targets
                    if str(Path(path).expanduser().resolve()) not in existing_paths
                ]
            if not targets:
                st.info("没有需要新增提取帧曲线的 ODB。")
                return
            try:
                with st.spinner("正在提取 ODB 帧曲线..."):
                    completed = []
                    for target_odb in targets:
                        series = run_case_odb_frame_series_extraction(
                            summary,
                            target_odb,
                            fields=fields,
                            region_names=region_names,
                            max_values_per_field=int(series_max_values),
                            max_frames_per_step=int(series_max_frames),
                            batch_config=batch_config,
                        )
                        append_odb_frame_series(summary, series)
                        completed.append(series)
                st.success(f"ODB 帧曲线提取完成：{len(completed)} 个")
                st.json(
                    [
                        {
                            "odb": item.get("odb_name"),
                            "rows": item.get("row_count"),
                            "regions_found": item.get("regions_found", []),
                            "csv": item.get("csv_path"),
                        }
                        for item in completed
                    ]
                )
                st.rerun()
            except Exception as exc:
                st.error(f"ODB 帧曲线提取失败：{exc}")
                st.info(
                    "帧曲线使用 Abaqus SMAPython.exe 批处理读取 ODB，请确认路径有效且 ODB 未被其他进程锁定。"
                )


def _case_odb_options(summary: Any) -> list[str]:
    options: list[str] = []
    for item in (summary.result_features or {}).get("odb_files", []):
        path = item.get("path") if isinstance(item, dict) else item
        if path and Path(path).exists():
            options.append(str(Path(path)))
    for path in ((summary.result_features or {}).get("summary", {}) or {}).get(
        "odb_files", []
    ):
        if path and Path(path).exists():
            text = str(Path(path))
            if text not in options:
                options.append(text)

    source = Path(summary.source_folder)
    if source.is_dir():
        for path in sorted(
            source.rglob("*.odb"), key=lambda item: item.stat().st_mtime, reverse=True
        ):
            text = str(path)
            if text not in options:
                options.append(text)
    elif source.suffix.lower() == ".odb" and source.exists():
        text = str(source)
        if text not in options:
            options.append(text)
    return options


def _material_library_controls() -> None:
    presets = load_material_presets()
    with st.expander("材料库", expanded=False):
        if presets:
            names = list(presets)
            selected = st.selectbox("加载材料模板", names, key="library_load_name")
            if st.button(
                "加载到训练页", use_container_width=True, key="library_load_to_training"
            ):
                for key, value in preset_to_training_state(presets[selected]).items():
                    st.session_state[key] = value
                st.rerun()
        else:
            st.info("材料库为空，可以先保存当前训练参数。")

        st.text_input("保存为模板名", key="library_save_name")
        st.text_area("备注", key="library_notes", height=70)
        if st.button(
            "保存当前参数", use_container_width=True, key="library_save_current"
        ):
            preset_name = st.session_state.get(
                "library_save_name"
            ) or st.session_state.get("train_name", "material_preset")
            preset = preset_from_training_state(
                preset_name,
                st.session_state,
                notes=st.session_state.get("library_notes", ""),
            )
            save_material_preset(preset)
            st.success(f"已保存：{preset.name}")


def _system_diagnostics_panel() -> None:
    st.subheader("系统诊断")
    st.caption("检查桌面工作区、Abaqus 批处理运行时与 MCP 实时桥接，并生成可追溯报告。")
    left, right = st.columns([0.42, 0.58], gap="large")

    with left:
        abaqus_bat = st.text_input(
            "Abaqus 命令",
            value=str(DEFAULT_ABAQUS_BAT),
            key="diagnostics_abaqus_bat",
        )
        smapython = st.text_input(
            "SMAPython",
            value=str(DEFAULT_SMAPYTHON),
            key="diagnostics_smapython",
        )
        host = st.text_input("MCP 主机", value="127.0.0.1", key="diagnostics_mcp_host")
        port = st.number_input(
            "MCP 端口",
            min_value=1,
            max_value=65535,
            value=48152,
            step=1,
            key="diagnostics_mcp_port",
        )
        probe_commands = st.checkbox(
            "执行版本探测",
            value=False,
            help="只查询 Abaqus 与 SMAPython 版本，不提交求解任务。",
            key="diagnostics_probe_commands",
        )
        include_live_context = st.checkbox(
            "读取当前模型与 Job 上下文",
            value=True,
            key="diagnostics_live_context",
        )
        run_clicked = st.button(
            "运行诊断",
            type="primary",
            use_container_width=True,
            key="diagnostics_run",
        )

    if run_clicked:
        with st.spinner("正在检查 Abaqus 环境..."):
            report = run_abaqus_diagnostics(
                AbaqusDiagnosticConfig(
                    abaqus_bat=abaqus_bat,
                    smapython=smapython,
                    workspace_root=WORKSPACE_ROOT,
                    output_root=DIAGNOSTICS_ROOT,
                    mcp=AbaqusMcpConfig(
                        host=host.strip() or "127.0.0.1",
                        port=int(port),
                        timeout_seconds=10.0,
                    ),
                    probe_commands=probe_commands,
                    include_live_context=include_live_context,
                )
            )
        st.session_state["system_diagnostics_report"] = report.to_dict()

    with right:
        payload = st.session_state.get("system_diagnostics_report")
        if not payload:
            st.info("运行诊断后，这里会显示批处理、MCP 与工作区的独立就绪状态。")
            return

        overall = payload.get("overall_status", "unknown")
        if overall == "ready":
            st.success("Abaqus 批处理与 MCP 实时桥接均已就绪。")
        elif overall == "partial":
            st.warning("部分能力可用，请按检查项处理未就绪部分。")
        else:
            st.error("当前环境存在阻断项。")

        metrics = st.columns(3)
        metrics[0].metric("总体状态", overall)
        metrics[1].metric("批处理", "就绪" if payload.get("batch_ready") else "未就绪")
        metrics[2].metric("MCP", "已连接" if payload.get("mcp_ready") else "未连接")
        rows = [
            {
                "检查项": item.get("label"),
                "状态": item.get("status"),
                "结论": item.get("message"),
            }
            for item in payload.get("checks", [])
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True, height=330)
        with st.expander("后续动作", expanded=overall != "ready"):
            for index, action in enumerate(payload.get("next_actions", []), 1):
                st.write(f"{index}. {action}")
        artifacts = payload.get("artifacts") or {}
        st.caption(f"诊断报告：`{artifacts.get('markdown', '')}`")


def _plate_hole_acceptance_panel() -> None:
    st.subheader("三维带孔板验证")
    st.caption(
        "用统一的三维模型验证材料参数、Abaqus 求解、ODB 特征提取和案例归档闭环。"
    )
    notice = st.session_state.pop("acceptance_notice", None)
    if notice:
        if notice.get("level") == "success":
            st.success(notice.get("message", "操作完成"))
        else:
            st.warning(notice.get("message", "操作完成，请检查状态。"))
    left, right = st.columns([0.43, 0.57], gap="large")

    with left:
        name = st.text_input(
            "算例名称", value="plate_hole_acceptance", key="acceptance_name"
        )
        dims = st.columns(3)
        length = dims[0].number_input(
            "长度 mm", min_value=10.0, value=100.0, step=5.0, key="acceptance_length"
        )
        width = dims[1].number_input(
            "宽度 mm", min_value=10.0, value=50.0, step=5.0, key="acceptance_width"
        )
        thickness = dims[2].number_input(
            "厚度 mm", min_value=0.5, value=5.0, step=0.5, key="acceptance_thickness"
        )
        hole_radius = st.number_input(
            "孔半径 mm",
            min_value=0.5,
            value=5.0,
            step=0.5,
            key="acceptance_hole_radius",
        )

        st.markdown("**J2 双线性材料**")
        material_cols = st.columns(2)
        youngs_modulus = material_cols[0].number_input(
            "弹性模量 MPa",
            min_value=1.0,
            value=210000.0,
            step=1000.0,
            key="acceptance_e",
        )
        poisson_ratio = material_cols[1].number_input(
            "泊松比",
            min_value=-0.9,
            max_value=0.49,
            value=0.30,
            step=0.01,
            key="acceptance_nu",
        )
        yield_strength = material_cols[0].number_input(
            "屈服强度 MPa",
            min_value=1.0,
            value=250.0,
            step=10.0,
            key="acceptance_yield",
        )
        tangent_modulus = material_cols[1].number_input(
            "切线模量 MPa",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            key="acceptance_tangent",
        )
        solve_cols = st.columns(3)
        displacement = solve_cols[0].number_input(
            "位移 mm",
            min_value=0.001,
            value=0.35,
            step=0.05,
            key="acceptance_displacement",
        )
        mesh_size = solve_cols[1].number_input(
            "网格 mm", min_value=0.2, value=2.5, step=0.25, key="acceptance_mesh"
        )
        cpus = solve_cols[2].number_input(
            "CPU", min_value=1, max_value=32, value=4, step=1, key="acceptance_cpus"
        )
        backend_label = st.selectbox(
            "执行后端",
            ["Abaqus 批处理", "Abaqus MCP"],
            key="acceptance_backend",
        )
        archive_case = st.checkbox(
            "求解通过后加入案例库", value=True, key="acceptance_archive"
        )
        confirm_solver = st.checkbox(
            "确认允许创建并提交此 Abaqus Job",
            value=False,
            key="acceptance_confirm_solver",
        )

        config = PlateHoleAcceptanceConfig(
            name=name,
            length=float(length),
            width=float(width),
            thickness=float(thickness),
            hole_radius=float(hole_radius),
            youngs_modulus=float(youngs_modulus),
            poisson_ratio=float(poisson_ratio),
            yield_strength=float(yield_strength),
            tangent_modulus=float(tangent_modulus),
            displacement=float(displacement),
            mesh_size=float(mesh_size),
            cpus=int(cpus),
            backend="mcp" if backend_label == "Abaqus MCP" else "batch",
            submit_job=True,
            archive_case=archive_case,
        )
        button_cols = st.columns(2)
        prepare_clicked = button_cols[0].button(
            "仅准备文件",
            use_container_width=True,
            key="acceptance_prepare",
        )
        solve_clicked = button_cols[1].button(
            "执行完整闭环",
            type="primary",
            disabled=not confirm_solver,
            use_container_width=True,
            key="acceptance_solve",
        )

        if prepare_clicked:
            try:
                result = run_plate_hole_acceptance(config, execute=False)
            except Exception as exc:
                st.error(f"准备失败：{type(exc).__name__}: {exc}")
            else:
                st.session_state["acceptance_run_dir"] = str(result.run_dir)
                st.session_state["acceptance_selected_run"] = str(result.run_dir)
                st.session_state["acceptance_notice"] = {
                    "level": "success",
                    "message": "验收文件已准备，尚未提交求解。",
                }
                st.rerun()
        if solve_clicked:
            try:
                with st.spinner("正在执行 Abaqus 建模、求解、ODB 提取与验收..."):
                    result = run_plate_hole_acceptance(config, execute=True)
            except Exception as exc:
                st.error(f"闭环执行失败：{type(exc).__name__}: {exc}")
            else:
                st.session_state["acceptance_run_dir"] = str(result.run_dir)
                st.session_state["acceptance_selected_run"] = str(result.run_dir)
                st.session_state["acceptance_notice"] = {
                    "level": (
                        "success"
                        if result.status in {"validated", "archived"}
                        else "warning"
                    ),
                    "message": (
                        f"闭环通过：{result.status}"
                        if result.status in {"validated", "archived"}
                        else f"闭环停止于：{result.status}"
                    ),
                }
                st.rerun()

    with right:
        run_dirs = _plate_hole_run_dirs()
        current = st.session_state.get("acceptance_run_dir", "")
        options = [str(path) for path in run_dirs]
        if current and current not in options:
            options.insert(0, current)
        selected = st.selectbox(
            "运行记录",
            options or [""],
            format_func=lambda item: Path(item).name if item else "暂无运行记录",
            key="acceptance_selected_run",
        )
        resume_confirm = st.checkbox(
            "确认恢复并提交选中运行",
            value=False,
            key="acceptance_resume_confirm",
        )
        if st.button(
            "恢复选中运行",
            disabled=not bool(selected and resume_confirm),
            use_container_width=True,
            key="acceptance_resume",
        ):
            try:
                with st.spinner("正在从已有状态恢复闭环..."):
                    result = resume_plate_hole_acceptance(
                        selected,
                        execute=True,
                        submit_job=True,
                        archive_case=archive_case,
                        backend="mcp" if backend_label == "Abaqus MCP" else "batch",
                    )
            except Exception as exc:
                st.error(f"恢复失败：{type(exc).__name__}: {exc}")
            else:
                st.session_state["acceptance_run_dir"] = str(result.run_dir)
                st.session_state["acceptance_selected_run"] = str(result.run_dir)
                st.session_state["acceptance_notice"] = {
                    "level": (
                        "success"
                        if result.status in {"validated", "archived"}
                        else "warning"
                    ),
                    "message": f"恢复完成：{result.status}",
                }
                st.rerun()

        manifest_path = (
            Path(selected) / "acceptance_manifest.json" if selected else None
        )
        if not manifest_path or not manifest_path.is_file():
            st.info("创建或选择一个运行记录后，这里会显示每个闭环阶段的真实证据。")
            return
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        status = manifest.get("status", "unknown")
        if status in {"validated", "archived"}:
            st.success(f"总体状态：{status}")
        elif status == "failed":
            st.error("总体状态：failed")
        else:
            st.info(f"总体状态：{status}")
        stage_rows = [
            {
                "阶段": key,
                "状态": value.get("status"),
                "结论": value.get("message"),
            }
            for key, value in (manifest.get("stages") or {}).items()
        ]
        st.dataframe(stage_rows, use_container_width=True, hide_index=True, height=300)

        results = manifest.get("results") or {}
        if results:
            metrics = st.columns(4)
            metrics[0].metric("Mises MPa", _format_number(results.get("max_mises_mpa")))
            metrics[1].metric(
                "位移 mm", _format_number(results.get("max_displacement_mm"))
            )
            metrics[2].metric("反力 N", _format_number(results.get("reaction_force_n")))
            metrics[3].metric("孔区 PEEQ", _format_number(results.get("max_peeq")))
            with st.expander("完整 ODB 特征", expanded=False):
                st.json(results)
        st.caption(f"验收报告：`{Path(selected) / 'acceptance_report.md'}`")


def _plate_hole_run_dirs() -> list[Path]:
    if not ACCEPTANCE_ROOT.exists():
        return []
    manifests = sorted(
        ACCEPTANCE_ROOT.glob("*/acceptance_manifest.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return [item.parent for item in manifests]


def _format_number(value: Any) -> str:
    try:
        return f"{float(value):.5g}"
    except (TypeError, ValueError):
        return "N/A"


def _plate_hole_batch_panel() -> None:
    st.subheader("3D 带孔板批量仿真与代理模型")
    st.caption(
        "批量改变孔径、屈服强度和位移，生成真实 Abaqus 样本；通过质量门后训练 RF、MLP 神经网络和 GBR 代理模型。"
    )
    left, right = st.columns([0.38, 0.62], gap="large")

    with left:
        st.markdown("**创建参数计划**")
        name = st.text_input(
            "批次名称", value="plate_hole_ml_batch", key="plate_batch_name"
        )
        hole_text = st.text_input(
            "孔半径 mm",
            value="4, 5, 6",
            key="plate_batch_hole_radii",
        )
        yield_text = st.text_input(
            "屈服强度 MPa",
            value="250, 300, 350",
            key="plate_batch_yield_strengths",
        )
        displacement_text = st.text_input(
            "加载位移 mm",
            value="0.25, 0.35",
            key="plate_batch_displacements",
        )
        dims = st.columns(3)
        length = dims[0].number_input(
            "长度", min_value=10.0, value=100.0, step=5.0, key="plate_batch_length"
        )
        width = dims[1].number_input(
            "宽度", min_value=10.0, value=50.0, step=5.0, key="plate_batch_width"
        )
        thickness = dims[2].number_input(
            "厚度", min_value=0.5, value=5.0, step=0.5, key="plate_batch_thickness"
        )
        material = st.columns(3)
        youngs_modulus = material[0].number_input(
            "E MPa",
            min_value=1.0,
            value=210000.0,
            step=1000.0,
            key="plate_batch_e",
        )
        poisson_ratio = material[1].number_input(
            "泊松比",
            min_value=-0.9,
            max_value=0.49,
            value=0.3,
            step=0.01,
            key="plate_batch_nu",
        )
        tangent_modulus = material[2].number_input(
            "切线模量",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            key="plate_batch_tangent",
        )
        run_settings = st.columns(3)
        mesh_size = run_settings[0].number_input(
            "网格 mm",
            min_value=0.1,
            value=2.5,
            step=0.25,
            key="plate_batch_mesh",
        )
        cpus = run_settings[1].number_input(
            "CPU", min_value=1, max_value=32, value=4, key="plate_batch_cpus"
        )
        backend_label = run_settings[2].selectbox(
            "后端",
            ["批处理", "MCP"],
            key="plate_batch_backend",
        )
        create_clicked = st.button(
            "创建批量计划",
            type="primary",
            use_container_width=True,
            key="plate_batch_create",
        )
        if create_clicked:
            try:
                config = PlateHoleBatchConfig(
                    name=name,
                    hole_radii=tuple(_parse_float_list(hole_text)),
                    yield_strengths=tuple(_parse_float_list(yield_text)),
                    displacements=tuple(_parse_float_list(displacement_text)),
                    length=float(length),
                    width=float(width),
                    thickness=float(thickness),
                    youngs_modulus=float(youngs_modulus),
                    poisson_ratio=float(poisson_ratio),
                    tangent_modulus=float(tangent_modulus),
                    mesh_size=float(mesh_size),
                    cpus=int(cpus),
                    backend="mcp" if backend_label == "MCP" else "batch",
                )
                plan = create_plate_hole_batch_plan(config)
            except Exception as exc:
                st.error(f"批量计划创建失败：{exc}")
            else:
                st.session_state["plate_batch_selected"] = str(plan.plan_dir)
                st.success(f"已创建 {len(plan.samples)} 个样本：{plan.plan_dir.name}")

    with right:
        plans = list_plate_hole_batch_plans()
        if not plans:
            st.info("还没有 3D 带孔板批量计划。")
            return
        options = [str(path) for path in plans]
        selected_state = st.session_state.get("plate_batch_selected")
        default_index = (
            options.index(selected_state) if selected_state in options else 0
        )
        selected = st.selectbox(
            "选择批量计划",
            options,
            index=default_index,
            format_func=lambda value: Path(value).name,
            key="plate_batch_selector",
        )
        st.session_state["plate_batch_selected"] = selected
        plan = load_plate_hole_batch_plan(selected)
        controls = st.columns(4)
        max_samples = controls[0].number_input(
            "本次样本数",
            min_value=1,
            max_value=max(1, len(plan.samples)),
            value=min(1, max(1, len(plan.samples))),
            key="plate_batch_max_samples",
        )
        archive_cases = controls[1].checkbox(
            "归档案例", value=True, key="plate_batch_archive"
        )
        export_after = controls[2].checkbox(
            "更新数据集", value=True, key="plate_batch_export"
        )
        train_after = controls[3].checkbox(
            "训练代理模型", value=False, key="plate_batch_train"
        )
        confirm_submit = st.checkbox(
            "确认允许本次提交 Abaqus Jobs",
            value=False,
            key="plate_batch_confirm_submit",
        )
        buttons = st.columns(3)
        prepare_clicked = buttons[0].button(
            "批量准备脚本", use_container_width=True, key="plate_batch_prepare"
        )
        solve_clicked = buttons[1].button(
            "运行真实求解",
            type="primary",
            disabled=not confirm_submit,
            use_container_width=True,
            key="plate_batch_solve",
        )
        refresh_clicked = buttons[2].button(
            "刷新数据集/模型",
            use_container_width=True,
            key="plate_batch_refresh_ml",
        )

        try:
            if prepare_clicked:
                with st.spinner("正在为批量样本生成确定性 Abaqus 脚本..."):
                    plan = run_plate_hole_batch_plan(
                        selected,
                        execute=False,
                        max_samples=int(max_samples),
                    )
                st.success("批量脚本已准备，尚未提交求解。")
            elif solve_clicked:
                with st.spinner("正在逐个执行 Abaqus、ODB 后处理与案例归档..."):
                    plan = run_plate_hole_batch_plan(
                        selected,
                        execute=True,
                        submit_jobs=True,
                        archive_cases=archive_cases,
                        export_dataset_after=export_after,
                        train_models_after=train_after,
                        max_samples=int(max_samples),
                    )
                st.success("本轮真实求解已结束，请检查每个样本状态。")
            elif refresh_clicked:
                plan = run_plate_hole_batch_plan(
                    selected,
                    execute=False,
                    export_dataset_after=True,
                    train_models_after=train_after,
                    max_samples=0,
                )
                st.success("数据集与代理模型状态已刷新。")
        except Exception as exc:
            st.error(f"批量流水线失败：{type(exc).__name__}: {exc}")
            plan = load_plate_hole_batch_plan(selected)

        rows = plate_hole_batch_table_rows(plan)
        counts: dict[str, int] = {}
        for row in rows:
            status = str(row.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
        metric_cols = st.columns(4)
        metric_cols[0].metric("样本总数", len(rows))
        metric_cols[1].metric("已归档", counts.get("archived", 0))
        metric_cols[2].metric(
            "失败/阻断", counts.get("failed", 0) + counts.get("blocked", 0)
        )
        metric_cols[3].metric(
            "训练样本",
            (plan.data.get("outputs", {}) or {}).get("dataset_case_count", 0),
        )
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            height=min(480, 42 + 30 * max(1, len(rows))),
        )
        outputs = plan.data.get("outputs", {}) or {}
        if outputs:
            with st.expander("数据集与代理模型输出", expanded=True):
                st.json(outputs)
        st.caption(f"批量报告：`{plan.report_path}`")


def _abaqus_mcp_panel(selected_run: Path | None) -> None:
    st.subheader("Abaqus MCP 工作台")
    st.caption("连接当前打开的 Abaqus/CAE 会话，用于查询模型、管理 Job 和读取结果。")
    left, right = st.columns([0.38, 0.62], gap="large")

    with left:
        st.markdown("**连接设置**")
        host = st.text_input("Bridge 主机地址", value="127.0.0.1", key="mcp_host")
        port = st.number_input(
            "Bridge 端口",
            min_value=1,
            max_value=65535,
            value=48152,
            step=1,
            key="mcp_port",
        )
        timeout_seconds = st.number_input(
            "请求超时 (秒)",
            min_value=0.5,
            max_value=120.0,
            value=5.0,
            step=0.5,
            key="mcp_timeout",
        )
        config = AbaqusMcpConfig(
            host=host.strip() or "127.0.0.1",
            port=int(port),
            timeout_seconds=float(timeout_seconds),
        )

        c0, c1 = st.columns(2)
        check_clicked = c0.button(
            "检查连接", type="primary", use_container_width=True, key="mcp_check"
        )
        stop_clicked = c1.button(
            "停止 Bridge", use_container_width=True, key="mcp_stop"
        )
        snapshot_clicked = st.button(
            "生成会话快照", use_container_width=True, key="mcp_snapshot"
        )

        st.divider()
        st.markdown("**工作目录**")
        default_workdir = (
            selected_run / "abaqus_verification" if selected_run else REPO_ROOT
        )
        workdir_text = st.text_input(
            "Abaqus 当前工作目录", value=str(default_workdir), key="mcp_workdir"
        )
        set_workdir_clicked = st.button(
            "设置 Abaqus 工作目录", use_container_width=True, key="mcp_set_workdir"
        )

        st.divider()
        st.markdown("**启动提示**")
        st.info(
            "新版 Abaqus MCP 通过本地 socket bridge 直接连接 Abaqus/CAE，"
            "正常情况下短脚本交互不会冻结 Abaqus 窗口。"
            "如果连接失败，在 Abaqus/CAE 里执行：Plug-ins > Abaqus MCP > Start Socket Bridge。"
        )

    with right:
        st.markdown("**连接状态**")
        if stop_clicked:
            try:
                result = stop_bridge(config)
            except Exception as exc:
                st.error(f"停止 Bridge 失败：{exc}")
            else:
                st.session_state.pop("mcp_last_status", None)
                st.success(
                    "Bridge 停止请求已发送。重新加载插件或重启 Abaqus/CAE 后，再启动 Socket Bridge。"
                )
                st.json(result)

        if check_clicked or "mcp_last_status" not in st.session_state:
            with st.spinner("正在检查 Abaqus MCP bridge..."):
                status = ping_bridge(config)
            st.session_state["mcp_last_status"] = status.__dict__

        status_data = st.session_state.get("mcp_last_status")
        if status_data:
            if status_data.get("connected"):
                st.success(status_data.get("message", "Abaqus MCP 已连接"))
                telemetry = status_data.get("telemetry") or {}
                cols = st.columns(4)
                cols[0].metric("Endpoint", status_data.get("endpoint", "N/A"))
                cols[1].metric("Models", len(telemetry.get("models") or []))
                cols[2].metric("Viewports", len(telemetry.get("viewports") or []))
                cols[3].metric(
                    "Processed", (telemetry.get("bridge") or {}).get("processed", "N/A")
                )
                with st.expander("连接 telemetry", expanded=False):
                    st.json(telemetry)
            else:
                st.error(status_data.get("message", "Abaqus MCP 未连接"))
                error_text = status_data.get("error", "No error detail.")
                st.code(error_text, language="text")
                if (
                    "command arg must be a string or sequence of strings" in error_text
                    or "__traceback__" in error_text
                ):
                    st.warning(
                        "检测到旧版 Abaqus MCP 插件的 sendCommand 兼容性问题。"
                        "本机插件源码已升级到 v5.0.3，当前已打开的 Abaqus/CAE 需要重新加载插件或重启后再启动 Socket Bridge。"
                    )

        if set_workdir_clicked:
            try:
                data = set_workdir(Path(workdir_text), config)
            except Exception as exc:
                st.error(f"设置工作目录失败：{exc}")
            else:
                st.success(f"工作目录已设置：{data.get('current')}")
                st.json(data)

        st.divider()
        st.markdown("**模型与 Job**")
        c1, c2, c3 = st.columns(3)
        model_clicked = c1.button(
            "读取模型", use_container_width=True, key="mcp_read_model"
        )
        jobs_clicked = c2.button(
            "读取 Job", use_container_width=True, key="mcp_read_jobs"
        )
        monitor_clicked = c3.button(
            "监控 Job", use_container_width=True, key="mcp_monitor_job"
        )

        if model_clicked:
            try:
                st.session_state["mcp_model_info"] = get_model_info(config)
            except Exception as exc:
                st.error(f"读取模型失败：{exc}")
        if jobs_clicked:
            try:
                st.session_state["mcp_jobs"] = list_jobs(config)
            except Exception as exc:
                st.error(f"读取 Job 失败：{exc}")

        jobs = st.session_state.get("mcp_jobs") or []
        job_names = [job.get("name") for job in jobs if job.get("name")]
        selected_job = st.selectbox(
            "选择 Job", job_names or [""], format_func=lambda item: item or "暂无 Job"
        )
        confirm_submit = st.checkbox("确认允许提交选中的 Abaqus Job", value=False)
        submit_clicked = st.button(
            "提交并等待 Job 完成",
            disabled=not bool(selected_job and confirm_submit),
            use_container_width=True,
            key="mcp_submit_job",
        )

        if monitor_clicked:
            try:
                st.json(
                    monitor_job_status(selected_job if selected_job else "", config)
                )
            except Exception as exc:
                st.error(f"监控 Job 失败：{exc}")
        if submit_clicked and selected_job:
            try:
                with st.spinner(f"正在提交 Job：{selected_job}"):
                    st.json(submit_job(selected_job, config))
                st.success("Job 提交完成")
            except Exception as exc:
                st.error(f"提交 Job 失败：{exc}")

        if st.session_state.get("mcp_model_info"):
            with st.expander("模型信息 JSON", expanded=False):
                st.json(st.session_state["mcp_model_info"])
        if jobs:
            st.dataframe(jobs, use_container_width=True, hide_index=True, height=400)

        st.divider()
        st.markdown("**ODB 与视口**")
        odb_candidates = _find_odb_candidates(selected_run)
        odb_options = [str(path) for path in odb_candidates]
        default_odb = odb_options[0] if odb_options else ""
        selected_odb = st.selectbox(
            "本地 ODB",
            odb_options or [""],
            format_func=lambda item: Path(item).name if item else "暂无 ODB",
        )
        odb_path = st.text_input(
            "ODB 路径", value=selected_odb or default_odb, key="mcp_odb_path"
        )
        c4, c5 = st.columns(2)
        inspect_odb_clicked = c4.button(
            "读取 ODB 元数据", use_container_width=True, key="mcp_inspect_odb"
        )
        capture_clicked = c5.button(
            "抓取当前视口", use_container_width=True, key="mcp_capture_viewport"
        )

        if inspect_odb_clicked:
            if not odb_path.strip():
                st.warning("请先选择或输入 ODB 路径。")
            else:
                try:
                    st.session_state["mcp_odb_info"] = inspect_odb(
                        Path(odb_path), config
                    )
                except Exception as exc:
                    st.error(f"读取 ODB 失败：{exc}")
        if st.session_state.get("mcp_odb_info"):
            with st.expander("ODB 元数据 JSON", expanded=False):
                st.json(st.session_state["mcp_odb_info"])

        if capture_clicked:
            output_dir = (
                (selected_run / "abaqus_verification" / "mcp_viewports")
                if selected_run
                else (REPO_ROOT / "material_ai_workbench" / "mcp_sessions")
            )
            try:
                image_path = capture_viewport(output_dir, config=config)
                st.session_state["mcp_last_viewport"] = str(image_path)
                st.success(f"视口截图已保存：{image_path}")
            except Exception as exc:
                st.error(f"抓取视口失败：{exc}")
        viewport = st.session_state.get("mcp_last_viewport")
        if viewport and Path(viewport).exists():
            st.image(viewport, caption="Abaqus 当前视口", use_container_width=True)

        if snapshot_clicked:
            with st.spinner("正在生成 Abaqus MCP 会话快照..."):
                snapshot = create_session_snapshot(
                    selected_run=selected_run, config=config, capture_image=True
                )
            st.success("快照已生成")
            st.caption(f"目录: `{snapshot.snapshot_dir}`")
            if snapshot.viewport_path and snapshot.viewport_path.exists():
                st.image(
                    str(snapshot.viewport_path),
                    caption="会话快照视口",
                    use_container_width=True,
                )


def _abaqus_panel(selected_run: Path | None) -> None:
    left, right = st.columns([0.5, 0.5], gap="large")
    with left:
        st.subheader("验算设置")
        run_dir = _run_selector("选择训练 run", selected_run)
        max_load_cases = st.number_input(
            "载荷工况数", min_value=0, max_value=9, value=1, step=1
        )
        timeout_seconds = st.number_input(
            "超时 (秒)", min_value=60, max_value=7200, value=1200, step=60
        )

        abaqus_bat_raw = st.text_input(
            "Abaqus 命令",
            value=str(DEFAULT_ABAQUS_BAT),
            help="Abaqus.bat 的完整路径，例如 D:\\ABAQUS\\2023\\Commands\\abaqus.bat",
        )
        abaqus_bat_stripped = abaqus_bat_raw.strip()
        abaqus_bat_path = Path(abaqus_bat_stripped) if abaqus_bat_stripped else None
        if abaqus_bat_stripped and abaqus_bat_stripped != str(DEFAULT_ABAQUS_BAT):
            st.caption(f"当前路径: `{abaqus_bat_stripped}`")

        c1, c2 = st.columns(2)
        prepare_clicked = c1.button(
            "准备目录", use_container_width=True, key="abaqus_prepare"
        )
        run_clicked = c2.button(
            "运行 Abaqus", type="primary", use_container_width=True, key="abaqus_run"
        )
        st.divider()
        _abaqus_job_queue_panel(run_dir)

    with right:
        st.subheader("Abaqus 状态")
        if not run_dir:
            st.info("先选择一个训练 run。")
            return

        if (prepare_clicked or run_clicked) and (
            abaqus_bat_path is None
            or str(abaqus_bat_path) == "."
            or not abaqus_bat_path.exists()
        ):
            st.error("Abaqus 可执行文件不存在")
            st.caption(f"输入的路径: `{abaqus_bat_raw or '(空)'}`")
            return

        config = AbaqusBridgeConfig(
            run_dir=run_dir,
            abaqus_bat=abaqus_bat_path or DEFAULT_ABAQUS_BAT,
            max_load_cases=int(max_load_cases),
            timeout_seconds=int(timeout_seconds),
        )

        if prepare_clicked:
            with st.spinner("正在准备 Abaqus 验算目录..."):
                result = prepare_abaqus_verification(config)
            st.success("验算目录已准备")
            st.caption(f"工作目录: `{result.work_dir}`")

        if run_clicked:
            with st.spinner("正在调用 Abaqus，可能需要几十秒..."):
                result = run_abaqus_verification(config)
            if result.status == "completed":
                st.success("Abaqus 验算完成")
            elif result.status == "failed":
                st.error(f"Abaqus 运行失败")
            elif result.status == "timeout":
                st.error("Abaqus 运行超时")
            else:
                st.warning(f"Abaqus 状态：{result.status}")

        _show_abaqus_summary(run_dir / "abaqus_verification")


def _abaqus_job_queue_panel(default_run_dir: Path | None) -> None:
    st.markdown("**Abaqus Job 队列**")
    inp_candidates = _find_inp_candidates(default_run_dir)
    default_input = str(inp_candidates[0]) if inp_candidates else ""
    default_work_dir = str(
        (
            Path(default_input).parent
            if default_input
            else (default_run_dir or REPO_ROOT)
        ).resolve()
    )

    queue_abaqus = st.text_input(
        "队列 Abaqus 命令",
        value=str(DEFAULT_ABAQUS_BAT),
        key="queue_abaqus_bat",
        help="用于按队列提交 inp/job 的 Abaqus.bat 路径。",
    )
    input_options = [str(path) for path in inp_candidates]
    if input_options:
        selected_input = st.selectbox(
            "候选 INP",
            input_options,
            index=0,
            format_func=lambda item: Path(item).name,
            key="queue_input_select",
        )
    else:
        selected_input = ""
    input_file = st.text_input(
        "Input File (.inp)",
        value=selected_input or default_input,
        key="queue_input_file",
    )
    work_dir = st.text_input("工作目录", value=default_work_dir, key="queue_work_dir")
    q1, q2 = st.columns(2)
    default_job_name = (
        Path(input_file).stem if input_file and input_file.strip() else ""
    ) or "queued_abaqus_job"
    job_name = q1.text_input(
        "Job 名称",
        value=default_job_name,
        key="queue_job_name",
    )
    cpus = q2.number_input(
        "CPUs", min_value=1, max_value=64, value=4, step=1, key="queue_cpus"
    )
    timeout_seconds = st.number_input(
        "单个 Job 超时 (秒)",
        min_value=60,
        max_value=86400,
        value=7200,
        step=300,
        key="queue_timeout",
    )

    queue = JobQueue(abaqus_bat=Path(queue_abaqus))
    b1, b2, b3 = st.columns(3)
    submit_clicked = b1.button(
        "加入队列", type="primary", use_container_width=True, key="queue_submit"
    )
    process_clicked = b2.button(
        "处理下一个", use_container_width=True, key="queue_process_next"
    )
    clear_clicked = b3.button(
        "清理已完成", use_container_width=True, key="queue_clear_completed"
    )

    if submit_clicked:
        input_path = Path(input_file).expanduser()
        work_path = Path(work_dir).expanduser()
        if not input_path.exists() or input_path.suffix.lower() != ".inp":
            st.error("请提供存在的 .inp 文件。")
        elif not work_path.exists():
            st.error("工作目录不存在。")
        elif not Path(queue_abaqus).exists():
            st.error("Abaqus 命令路径不存在。")
        else:
            job = queue.submit(job_name, input_path, work_path, cpus=int(cpus))
            st.success(f"已加入队列：{job.name}")

    if process_clicked:
        if not Path(queue_abaqus).exists():
            st.error("Abaqus 命令路径不存在。")
        else:
            with st.spinner("正在处理队列中的下一个 Abaqus Job..."):
                processed = queue.process_next(timeout_seconds=int(timeout_seconds))
            if processed:
                st.success("队列处理完成，状态已更新。")
            else:
                st.info("当前没有排队中的 Job。")

    if clear_clicked:
        queue.clear_completed()
        st.success("已清理 completed Job，失败和排队中任务会保留。")

    status = queue.statistics()
    cols = st.columns(5)
    cols[0].metric("总数", status.get("total", 0))
    cols[1].metric("排队", status.get("queued", 0))
    cols[2].metric("运行", status.get("running", 0))
    cols[3].metric("完成", status.get("completed", 0))
    cols[4].metric("失败", status.get("failed", 0))
    stat_cols = st.columns(3)
    stat_cols[0].metric("历史提交", status.get("history_total", 0))
    stat_cols[1].metric("成功率", _fmt_metric(status.get("success_rate")))
    stat_cols[2].metric(
        "平均耗时(s)", _fmt_metric(status.get("average_duration_seconds"))
    )
    rows = []
    for job in queue.list_jobs():
        rows.append(
            {
                "id": job.job_id,
                "job": job.name,
                "status": job.status,
                "cpus": job.cpus,
                "input": job.input_file,
                "work_dir": job.work_dir,
                "return": job.return_code,
                "log": job.log_path,
                "error": job.error_message,
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True, height=260)
        for job in queue.list_jobs():
            with st.expander(f"{job.name} / {job.status}", expanded=False):
                c1, c2 = st.columns(2)
                retry_clicked = c1.button(
                    "重试失败 Job",
                    use_container_width=True,
                    disabled=job.status != "failed",
                    key=f"queue_retry_{job.job_id}",
                )
                if retry_clicked:
                    try:
                        retried = queue.retry(job.job_id)
                        st.success(f"已重新加入队列：{retried.name}")
                    except Exception as exc:
                        st.error(f"重试失败：{exc}")
                if c2.button(
                    "查看日志", use_container_width=True, key=f"queue_log_{job.job_id}"
                ):
                    st.session_state["queue_log_job_id"] = job.job_id
                if st.session_state.get("queue_log_job_id") == job.job_id:
                    log_text = queue.log_text(job.job_id)
                    if log_text:
                        st.code(log_text, language="text")
                    else:
                        st.info("暂无日志文件。")
    else:
        st.caption("队列为空。")
    history = queue.history()
    if history:
        with st.expander("历史记录", expanded=False):
            st.dataframe(
                [
                    {
                        "job": row.get("name"),
                        "status": row.get("status"),
                        "return": row.get("return_code"),
                        "started": row.get("started_at"),
                        "finished": row.get("finished_at"),
                        "retry_of": row.get("retry_of"),
                        "log": row.get("log_path"),
                    }
                    for row in reversed(history[-50:])
                ],
                use_container_width=True,
                hide_index=True,
                height=320,
            )


def _composite_panel() -> None:
    st.subheader("复合材料 RVE + 带孔板验证")
    st.caption(
        "生成 Fiber/Interface/Matrix 三相微观体素 RVE、机器学习 phase map、pyLabFEA 材料摘要和 Abaqus 3D 带孔板验证脚本。"
    )
    composite_root = REPO_ROOT / COMPOSITE_ROOT
    left, right = st.columns([0.38, 0.62], gap="large")

    with left:
        st.markdown("**微观材料与 RVE**")
        name = st.text_input(
            "案例名称", value="micro_rve_plate_hole", key="composite_name"
        )
        st.caption("纤维属性")
        c1, c2 = st.columns(2)
        vf = c1.number_input(
            "纤维体积分数",
            min_value=0.05,
            max_value=0.8,
            value=0.55,
            step=0.01,
            key="composite_vf",
        )
        interface_efficiency = c2.number_input(
            "界面效率",
            min_value=0.1,
            max_value=1.5,
            value=0.92,
            step=0.01,
            key="composite_eta",
        )
        c3, c4 = st.columns(2)
        fiber_e = c3.number_input(
            "纤维 E (MPa)",
            min_value=1_000.0,
            value=230_000.0,
            step=5_000.0,
            key="composite_fiber_e",
        )
        fiber_nu = c4.number_input(
            "纤维 nu",
            min_value=0.0,
            max_value=0.49,
            value=0.20,
            step=0.01,
            key="composite_fiber_nu",
        )
        st.caption("基体属性")
        c5, c6 = st.columns(2)
        matrix_e = c5.number_input(
            "基体 E (MPa)",
            min_value=100.0,
            value=3_500.0,
            step=100.0,
            key="composite_matrix_e",
        )
        matrix_nu = c6.number_input(
            "基体 nu",
            min_value=0.0,
            max_value=0.49,
            value=0.35,
            step=0.01,
            key="composite_matrix_nu",
        )
        st.caption("界面与 RVE 网格")
        c7, c8 = st.columns(2)
        interface_ratio = c7.number_input(
            "界面厚度/纤维半径",
            min_value=0.0,
            max_value=0.8,
            value=0.18,
            step=0.02,
            key="composite_interface_ratio",
        )
        micro_fibers = c8.number_input(
            "RVE 纤维数",
            min_value=1,
            max_value=100,
            value=16,
            step=1,
            key="composite_micro_fibers",
        )
        c9, c10, c11 = st.columns(3)
        micro_nx = c9.number_input(
            "nx", min_value=2, max_value=40, value=8, step=1, key="composite_micro_nx"
        )
        micro_ny = c10.number_input(
            "ny", min_value=2, max_value=80, value=18, step=1, key="composite_micro_ny"
        )
        micro_nz = c11.number_input(
            "nz", min_value=2, max_value=80, value=18, step=1, key="composite_micro_nz"
        )

        st.divider()
        st.markdown("**纤维取向与几何**")
        fo1, fo2 = st.columns(2)
        fiber_theta = fo1.number_input(
            "纤维角度 θ (°)",
            min_value=0.0,
            max_value=90.0,
            value=0.0,
            step=1.0,
            key="composite_theta",
            help="纤维绕 Z 轴的主方向角，0 = 沿 X 方向",
        )
        fiber_spread = fo2.number_input(
            "取向分散 (°)",
            min_value=0.0,
            max_value=30.0,
            value=8.0,
            step=0.5,
            key="composite_spread",
            help="纤维角度的标准差，越大纤维越随机",
        )
        fo3, fo4 = st.columns(2)
        fiber_len = fo3.number_input(
            "纤维长度 (相对 RVE)",
            min_value=0.3,
            max_value=3.0,
            value=1.2,
            step=0.1,
            key="composite_fiber_len",
        )
        fiber_diam = fo4.number_input(
            "纤维直径 (相对 RVE)",
            min_value=0.01,
            max_value=0.3,
            value=0.12,
            step=0.01,
            key="composite_fiber_diam",
            help="0 表示由 Vf 自动校准",
        )

        st.divider()
        st.markdown("**3D 带孔板验证模型**")
        st.caption("宏观几何与加载")
        p1, p2 = st.columns(2)
        length = p1.number_input(
            "长度 L (mm)", min_value=10.0, value=120.0, step=5.0, key="composite_length"
        )
        width = p2.number_input(
            "宽度 W (mm)", min_value=5.0, value=40.0, step=2.0, key="composite_width"
        )
        p3, p4 = st.columns(2)
        thickness = p3.number_input(
            "厚度 T (mm)", min_value=0.1, value=2.0, step=0.1, key="composite_thickness"
        )
        hole_radius = p4.number_input(
            "孔半径 R (mm)", min_value=0.1, value=5.0, step=0.5, key="composite_hole"
        )
        p5, p6 = st.columns(2)
        applied_strain = p5.number_input(
            "拉伸应变",
            min_value=0.0001,
            value=0.003,
            step=0.0005,
            format="%.5f",
            key="composite_strain",
        )
        mesh_size = p6.number_input(
            "宏观网格尺寸", min_value=0.2, value=2.0, step=0.2, key="composite_mesh"
        )
        st.caption("Abaqus 与随机设置")
        p7, p8 = st.columns(2)
        cpus = p7.number_input(
            "Abaqus CPUs",
            min_value=1,
            max_value=32,
            value=4,
            step=1,
            key="composite_cpus",
        )
        random_seed = p8.number_input(
            "随机种子",
            min_value=1,
            max_value=99999,
            value=7,
            step=1,
            key="composite_seed",
        )
        run_abaqus = st.checkbox(
            "生成后立即调用 Abaqus 建模", value=False, key="composite_run_abaqus"
        )
        submit_job_now = st.checkbox(
            "Abaqus 建模后提交求解 Job",
            value=False,
            key="composite_submit_job",
            disabled=not run_abaqus,
        )
        create_clicked = st.button(
            "生成复合材料闭环案例",
            type="primary",
            use_container_width=True,
            key="composite_create_case",
        )
        st.caption(f"`{composite_root}`")

    with right:
        with st.expander("微观纤维取向 3D 预览 (可旋转/缩放)", expanded=True):
            preview_key = (
                f"rve_fiber_{int(vf*100)}_{int(micro_fibers)}_{int(fiber_theta)}_{int(fiber_spread)}"
                f"_{int(fiber_len*10)}_{int(fiber_diam*1000)}_{int(interface_ratio*100)}_{int(random_seed)}"
            )
            if (
                "rve_preview_key" not in st.session_state
                or preview_key != st.session_state.get("rve_preview_key")
            ):
                with st.spinner("正在生成纤维 RVE 3D 预览..."):
                    preview_config = CompositePlateConfig(
                        fiber_volume_fraction=float(vf),
                        interface_efficiency=float(interface_efficiency),
                        interface_thickness_ratio=float(interface_ratio),
                        fiber_e=float(fiber_e),
                        fiber_nu=float(fiber_nu),
                        matrix_e=float(matrix_e),
                        matrix_nu=float(matrix_nu),
                        micro_fiber_count=int(micro_fibers),
                        micro_nx=int(micro_nx),
                        micro_ny=int(micro_ny),
                        micro_nz=int(micro_nz),
                        random_seed=int(random_seed),
                        fiber_orientation_theta_deg=float(fiber_theta),
                        fiber_orientation_spread_deg=float(fiber_spread),
                        fiber_length_normalized=float(fiber_len),
                        fiber_diameter_normalized=(
                            float(fiber_diam) if float(fiber_diam) > 0 else None
                        ),
                    )
                    try:
                        layout = preview_config if False else None  # just a marker
                        st.session_state["rve_preview_fig"] = (
                            plot_oriented_fiber_rve_3d(
                                config=preview_config,
                                width=700,
                                height=550,
                            )
                        )
                        st.session_state["rve_preview_key"] = preview_key
                    except Exception:
                        st.info(
                            "plotly 未安装。运行 `pip install plotly` 后即可查看 3D 纤维微观结构。"
                        )
                        st.session_state["rve_preview_fig"] = None
                        st.session_state["rve_preview_key"] = preview_key
            if st.session_state.get("rve_preview_fig") is not None:
                st.plotly_chart(
                    st.session_state["rve_preview_fig"],
                    use_container_width=True,
                    key="rve_3d_chart",
                )

        if create_clicked:
            try:
                config = CompositePlateConfig(
                    name=name,
                    output_dir=composite_root,
                    fiber_volume_fraction=float(vf),
                    fiber_e=float(fiber_e),
                    fiber_nu=float(fiber_nu),
                    matrix_e=float(matrix_e),
                    matrix_nu=float(matrix_nu),
                    interface_efficiency=float(interface_efficiency),
                    interface_thickness_ratio=float(interface_ratio),
                    length=float(length),
                    width=float(width),
                    thickness=float(thickness),
                    hole_radius=float(hole_radius),
                    applied_strain=float(applied_strain),
                    mesh_size=float(mesh_size),
                    micro_fiber_count=int(micro_fibers),
                    micro_nx=int(micro_nx),
                    micro_ny=int(micro_ny),
                    micro_nz=int(micro_nz),
                    random_seed=int(random_seed),
                    fiber_orientation_theta_deg=float(fiber_theta),
                    fiber_orientation_spread_deg=float(fiber_spread),
                    fiber_length_normalized=float(fiber_len),
                    fiber_diameter_normalized=(
                        float(fiber_diam) if float(fiber_diam) > 0 else None
                    ),
                    cpus=int(cpus),
                    run_abaqus=bool(run_abaqus),
                    submit_job=bool(submit_job_now),
                )
                with st.spinner(
                    "正在生成微观 RVE、phase map、pyLabFEA 摘要和 Abaqus 脚本..."
                ):
                    result = run_composite_plate_workflow(config)
                st.session_state["selected_composite_run"] = str(result.run_dir)
                st.success(f"已生成：{result.run_dir.name}")
            except Exception as exc:
                st.error(f"复合材料案例生成失败：{exc}")

        runs = list_composite_runs(composite_root)
        if not runs:
            st.info("还没有复合材料案例。先在左侧生成一个。")
            return

        options = [str(path) for path in runs]
        default_index = 0
        selected = st.session_state.get("selected_composite_run")
        if selected in options:
            default_index = options.index(selected)
        chosen = st.selectbox(
            "选择复合材料案例",
            options,
            index=default_index,
            format_func=lambda item: Path(item).name,
            key="composite_run_selector",
        )
        st.session_state["selected_composite_run"] = chosen
        manifest = load_composite_manifest(chosen)
        props = manifest.get("effective_properties", {})
        estimates = manifest.get("engineering_estimates", {})
        micro = manifest.get("microstructure_metrics", {})
        paths = manifest.get("paths", {})

        cols = st.columns(5)
        cols[0].metric("E1 MPa", _fmt_metric(props.get("E1")))
        cols[1].metric("E2 MPa", _fmt_metric(props.get("E2")))
        cols[2].metric(
            "Kt 估算",
            _fmt_metric(estimates.get("stress_concentration_factor_estimate")),
        )
        cols[3].metric("RVE 单元", _fmt_metric(micro.get("micro_voxel_elements")))
        cols[4].metric(
            "界面单元", _fmt_metric(micro.get("micro_rve_interface_elements"))
        )

        img_left, img_right = st.columns(2)
        _show_image(
            img_left,
            _resolve_output_path(paths.get("microstructure_png")),
            "三相微观 RVE 预览",
        )
        _show_image(
            img_right,
            _resolve_output_path(paths.get("plate_preview_png")),
            "3D 带孔板验证模型预览",
        )

        st.markdown("**机器学习数据与 Abaqus 文件**")
        file_rows = [
            {"artifact": "phase_map.csv", "path": paths.get("micro_phase_map")},
            {"artifact": "micro_rve_voxel.inp", "path": paths.get("micro_rve_inp")},
            {"artifact": "six PBC loadcase plan", "path": paths.get("micro_pbc_plan")},
            {
                "artifact": "six PBC run script",
                "path": paths.get("micro_pbc_run_script"),
            },
            {
                "artifact": "RVE stiffness postprocess",
                "path": paths.get("micro_pbc_postprocess_script"),
            },
            {
                "artifact": "pyLabFEA material summary",
                "path": paths.get("pylabfea_material_summary"),
            },
            {"artifact": "effective material card", "path": paths.get("material_card")},
            {"artifact": "plate Abaqus script", "path": paths.get("abaqus_script")},
            {"artifact": "run script", "path": paths.get("run_script")},
            {"artifact": "dataset row", "path": paths.get("dataset_csv")},
        ]
        st.dataframe(file_rows, use_container_width=True, hide_index=True, height=400)

        dataset_csv = _resolve_output_path(paths.get("dataset_csv"))
        if dataset_csv and dataset_csv.exists():
            with st.expander("训练数据行预览", expanded=False):
                st.dataframe(
                    _read_csv_preview(dataset_csv),
                    use_container_width=True,
                    hide_index=True,
                    height=400,
                )

        report_path = _resolve_output_path(paths.get("report"))
        if report_path and report_path.exists():
            with st.expander("复合材料闭环报告", expanded=True):
                st.markdown(report_path.read_text(encoding="utf-8"))

        with st.expander("manifest.json", expanded=False):
            st.json(manifest)

        st.divider()
        with st.expander("复合材料批量数据", expanded=False):
            b1, b2, b3 = st.columns(3)
            batch_name = b1.text_input(
                "批量计划名", value="composite_rve_sweep", key="composite_batch_name"
            )
            sample_count = b2.number_input(
                "样本数",
                min_value=1,
                max_value=200,
                value=6,
                step=1,
                key="composite_batch_samples",
            )
            max_run_samples = b3.number_input(
                "本次运行样本",
                min_value=1,
                max_value=50,
                value=2,
                step=1,
                key="composite_batch_max_run",
            )
            r1, r2 = st.columns(2)
            vf_min = r1.number_input(
                "Vf min",
                min_value=0.05,
                max_value=0.8,
                value=0.35,
                step=0.01,
                key="composite_batch_vf_min",
            )
            vf_max = r2.number_input(
                "Vf max",
                min_value=0.05,
                max_value=0.8,
                value=0.65,
                step=0.01,
                key="composite_batch_vf_max",
            )
            create_batch_clicked = st.button(
                "创建复合材料批量计划",
                use_container_width=True,
                key="create_composite_batch",
            )

            if create_batch_clicked:
                try:
                    plan = create_composite_batch_plan(
                        CompositeBatchConfig(
                            name=batch_name,
                            output_dir=REPO_ROOT / COMPOSITE_BATCH_ROOT,
                            sample_count=int(sample_count),
                            vf_min=float(vf_min),
                            vf_max=float(vf_max),
                            micro_nx=int(micro_nx),
                            micro_ny=int(micro_ny),
                            micro_nz=int(micro_nz),
                            micro_fiber_count=int(micro_fibers),
                        )
                    )
                    st.session_state["selected_composite_batch"] = str(plan.plan_dir)
                    st.success(f"批量计划已创建：{plan.plan_dir.name}")
                except Exception as exc:
                    st.error(f"创建批量计划失败：{exc}")

            plans = list_composite_batch_plans(REPO_ROOT / COMPOSITE_BATCH_ROOT)
            if plans:
                plan_options = [str(path) for path in plans]
                plan_index = 0
                selected_plan = st.session_state.get("selected_composite_batch")
                if selected_plan in plan_options:
                    plan_index = plan_options.index(selected_plan)
                chosen_plan = st.selectbox(
                    "选择复合材料批量计划",
                    plan_options,
                    index=plan_index,
                    format_func=lambda item: Path(item).name,
                    key="composite_batch_selector",
                )
                st.session_state["selected_composite_batch"] = chosen_plan
                run_batch_clicked = st.button(
                    "运行批量样本", use_container_width=True, key="run_composite_batch"
                )
                if run_batch_clicked:
                    try:
                        with st.spinner("正在生成复合材料批量样本..."):
                            plan = run_composite_batch_plan(
                                chosen_plan, max_samples=int(max_run_samples)
                            )
                        st.success("批量样本生成完成")
                    except Exception as exc:
                        st.error(f"运行批量计划失败：{exc}")
                        plan = load_composite_batch_plan(chosen_plan)
                else:
                    plan = load_composite_batch_plan(chosen_plan)
                st.dataframe(
                    plan.data.get("samples", []),
                    use_container_width=True,
                    hide_index=True,
                    height=400,
                )
                if plan.dataset_csv.exists() and plan.dataset_csv.stat().st_size > 0:
                    st.caption(f"`{plan.dataset_csv}`")
                    st.dataframe(
                        _read_csv_preview(plan.dataset_csv),
                        use_container_width=True,
                        hide_index=True,
                        height=400,
                    )
            else:
                st.info("还没有复合材料批量计划。")

        with st.expander("复合材料代理模型", expanded=False):
            plans = list_composite_batch_plans(REPO_ROOT / COMPOSITE_BATCH_ROOT)
            dataset_options = [
                str(load_composite_batch_plan(path).dataset_csv)
                for path in plans
                if load_composite_batch_plan(path).dataset_csv.exists()
            ]
            dataset_options = [
                path for path in dataset_options if Path(path).stat().st_size > 0
            ]
            if dataset_options:
                selected_dataset = st.selectbox(
                    "选择复合材料数据集",
                    dataset_options,
                    format_func=lambda item: Path(item).parent.name,
                    key="composite_surrogate_dataset",
                )
                target_column = st.selectbox(
                    "预测目标",
                    [
                        "max_stress_near_hole_estimate_mpa",
                        "E1",
                        "E2",
                        "G12",
                        "stress_concentration_factor_estimate",
                    ],
                    key="composite_surrogate_target",
                )
                model_kind = st.segmented_control(
                    "模型类型",
                    options=["random_forest", "mlp"],
                    format_func=lambda item: (
                        "随机森林" if item == "random_forest" else "神经网络 MLP"
                    ),
                    key="composite_surrogate_model_kind",
                )
                train_composite_clicked = st.button(
                    "训练复合材料代理模型",
                    use_container_width=True,
                    key="train_composite_surrogate",
                )
                if train_composite_clicked:
                    try:
                        with st.spinner("正在训练复合材料代理模型..."):
                            surrogate = train_composite_surrogate(
                                selected_dataset,
                                target_column=target_column,
                                model_kind=model_kind,
                            )
                        st.success(f"代理模型已生成：{surrogate.run_dir.name}")
                        st.json(surrogate.metrics)
                    except Exception as exc:
                        st.error(f"训练复合材料代理模型失败：{exc}")
                composite_comparison = composite_surrogate_comparison_rows(
                    dataset_csv=selected_dataset, target_column=target_column
                )
                _show_surrogate_comparison(
                    composite_comparison, title="复合材料代理模型对比"
                )
                all_composite_runs = list_composite_surrogate_runs()
                if all_composite_runs:
                    st.caption(
                        f"复合材料代理模型历史：`{len(all_composite_runs)}` 个 run"
                    )
                st.caption(f"`{COMPOSITE_SURROGATE_ROOT}`")
            else:
                st.info("先运行批量计划，生成 composite_dataset.csv 后再训练代理模型。")


def _batch_panel() -> None:
    st.subheader("批量仿真")
    st.caption(
        "把单个闭环样本扩展为多样本训练集。第一版先做材料参数扫描和串行队列，Abaqus 求解保持显式确认。"
    )
    left, right = st.columns([0.38, 0.62], gap="large")

    with left:
        st.markdown("**创建参数扫描计划**")
        batch_name = st.text_input("计划名称", value="batch_j2_sweep", key="batch_name")
        material_type = st.segmented_control(
            "材料类型",
            options=["j2", "hill"],
            format_func=lambda item: (
                "J2 isotropic" if item == "j2" else "Hill anisotropic"
            ),
            key="batch_material_type",
        )
        sy_text = st.text_input(
            "屈服强度列表 MPa", value="50,60,70", key="batch_sy_values"
        )
        c1, c2 = st.columns(2)
        youngs_modulus = c1.number_input(
            "E (MPa)", min_value=1.0, value=200_000.0, step=1000.0, key="batch_E"
        )
        poisson_ratio = c2.number_input(
            "nu", min_value=0.0, max_value=0.49, value=0.3, step=0.01, key="batch_nu"
        )
        c3, c4 = st.columns(2)
        n_load_cases = c3.number_input(
            "训练载荷方向数", min_value=8, value=32, step=8, key="batch_n_load_cases"
        )
        n_sequence = c4.number_input(
            "采样序列", min_value=2, value=3, step=1, key="batch_n_sequence"
        )
        max_abaqus_load_cases = st.number_input(
            "每个样本 Abaqus 载荷工况",
            min_value=1,
            max_value=9,
            value=1,
            step=1,
            key="batch_abaqus_cases",
        )
        create_clicked = st.button(
            "创建批量计划",
            type="primary",
            use_container_width=True,
            key="batch_create_plan",
        )

        st.divider()
        st.markdown("**运行控制**")
        allow_abaqus = st.checkbox(
            "允许本次批量任务调用 Abaqus", value=False, key="batch_allow_abaqus"
        )
        archive_cases = st.checkbox(
            "运行后写入案例库", value=False, key="batch_archive_cases"
        )
        postprocess_odb = st.checkbox(
            "写入案例库后提取 ODB", value=False, key="batch_postprocess_odb"
        )
        max_samples = st.number_input(
            "本次最多处理样本数", min_value=1, value=1, step=1, key="batch_max_samples"
        )
        run_material_clicked = st.button(
            "只运行材料训练", use_container_width=True, key="batch_run_material"
        )
        run_abaqus_clicked = st.button(
            "运行材料训练 + Abaqus",
            disabled=not allow_abaqus,
            use_container_width=True,
            key="batch_run_abaqus",
        )

        st.divider()
        st.markdown("**批量目录**")
        st.caption(f"`{BATCH_ROOT}`")

    with right:
        if create_clicked:
            try:
                sy_values = _parse_float_list(sy_text)
                plan = create_parameter_sweep_plan(
                    name=batch_name,
                    material_type=material_type,
                    yield_strengths=sy_values,
                    youngs_modulus=float(youngs_modulus),
                    poisson_ratio=float(poisson_ratio),
                    n_load_cases=int(n_load_cases),
                    n_sequence=int(n_sequence),
                    max_abaqus_load_cases=int(max_abaqus_load_cases),
                )
                st.session_state["selected_batch_plan"] = str(plan.plan_dir)
                st.success(f"批量计划已创建：{plan.plan_dir.name}")
            except Exception as exc:
                st.error(f"创建批量计划失败：{exc}")

        plans = list_batch_plans()
        if not plans:
            st.info("暂无批量计划。")
            return

        options = [str(path) for path in plans]
        default_index = 0
        selected = st.session_state.get("selected_batch_plan")
        if selected in options:
            default_index = options.index(selected)
        chosen = st.selectbox(
            "选择批量计划",
            options,
            index=default_index,
            format_func=lambda item: Path(item).name,
            key="batch_plan_selector",
        )
        st.session_state["selected_batch_plan"] = chosen

        if run_material_clicked or run_abaqus_clicked:
            try:
                with st.spinner("正在执行批量计划..."):
                    plan = run_batch_plan(
                        chosen,
                        run_abaqus=bool(run_abaqus_clicked),
                        archive_cases=bool(archive_cases),
                        postprocess_odb=bool(postprocess_odb and archive_cases),
                        max_samples=int(max_samples),
                    )
                st.success("批量计划执行完成")
            except Exception as exc:
                st.error(f"批量计划执行失败：{exc}")
                try:
                    plan = load_batch_plan(chosen)
                except Exception as load_exc:
                    st.error(f"加载批量计划也失败了: {load_exc}")
                    return
        else:
            try:
                plan = load_batch_plan(chosen)
            except Exception as load_exc:
                st.error(f"加载批量计划失败: {load_exc}")
                return

        _show_batch_plan(plan)


def _results_panel(selected_run: Path | None) -> None:
    st.subheader("结果浏览")
    run_dir = _run_selector("选择结果 run", selected_run)
    if not run_dir:
        st.info("暂无可浏览 run。")
        return
    _show_run_summary(run_dir)
    st.divider()
    _show_abaqus_summary(run_dir / "abaqus_verification")


def _surrogate_panel() -> None:
    st.subheader("代理模型")
    st.caption(
        "把案例库导出的 Abaqus/ODB 特征表训练成快速预测模型，用于后续自然语言仿真的初筛和抽样回验。"
    )
    left, right = st.columns([0.38, 0.62], gap="large")

    with left:
        st.markdown("**训练设置**")
        datasets = list_dataset_exports()
        if datasets:
            dataset_options = [str(path) for path in datasets]
            selected_dataset = st.selectbox(
                "案例库训练数据集",
                dataset_options,
                format_func=lambda item: Path(item).name,
                key="surrogate_dataset",
            )
            target_column = st.selectbox(
                "预测目标",
                SURROGATE_TARGET_OPTIONS,
                index=0,
                format_func=_surrogate_target_label,
                key="surrogate_target",
            )
            model_kind = st.segmented_control(
                "模型类型",
                options=["random_forest", "mlp", "gbr"],
                format_func=lambda item: {
                    "random_forest": "随机森林",
                    "mlp": "神经网络 MLP",
                    "gbr": "梯度提升 GBR",
                }[item],
                default="random_forest",
                key="surrogate_model_kind",
            )
            uncertainty = st.selectbox(
                "预测不确定性",
                ["none", "ensemble"],
                index=0,
                key="surrogate_uncertainty",
            )
            train_clicked = st.button(
                "训练代理模型",
                type="primary",
                use_container_width=True,
                key="surrogate_train",
            )
            compare_clicked = st.button(
                "多模型对比 (RF vs MLP vs GBR)",
                use_container_width=True,
                key="surrogate_compare_all",
            )
            st.caption(
                "样本量很少时，这一步主要验证流程；真正的预测能力来自后续持续积累的 Abaqus 案例库。"
            )

            if compare_clicked:
                with st.spinner("正在训练三种模型并生成对比报告..."):
                    try:
                        comparison = compare_all_models(
                            selected_dataset, target_column=target_column
                        )
                        _show_surrogate_comparison(
                            comparison, title="多模型对比 (同数据集)"
                        )
                        st.success("三种模型训练完成，对比表如上。")
                    except Exception as exc:
                        st.error(f"多模型对比失败：{exc}")

            with st.expander("ODB 帧曲线时序代理", expanded=False):
                default_frame_index = str(
                    Path(selected_dataset) / "frame_series_index.csv"
                )
                ts_case_dataset = st.text_input(
                    "case_dataset.csv", value=selected_dataset, key="ts_case_dataset"
                )
                ts_frame_index = st.text_input(
                    "frame_series_index.csv",
                    value=default_frame_index,
                    key="ts_frame_index",
                )
                t1, t2, t3 = st.columns(3)
                ts_field = t1.text_input("场变量", value="S", key="ts_target_field")
                ts_metric = t2.selectbox(
                    "曲线指标", ["max", "mean", "min"], key="ts_target_metric"
                )
                ts_model_kind = t3.selectbox(
                    "模型", ["random_forest", "mlp"], key="ts_model_kind"
                )
                ts_train_clicked = st.button(
                    "训练时序代理模型",
                    use_container_width=True,
                    key="ts_train_surrogate",
                )
            with st.expander("多保真代理模型", expanded=False):
                low_dataset = st.selectbox(
                    "低保真数据集",
                    dataset_options,
                    format_func=lambda item: Path(item).name,
                    key="mf_low_dataset",
                )
                high_dataset = st.selectbox(
                    "高保真数据集",
                    dataset_options,
                    index=0,
                    format_func=lambda item: Path(item).name,
                    key="mf_high_dataset",
                )
                mf_target = st.selectbox(
                    "多保真目标",
                    SURROGATE_TARGET_OPTIONS,
                    index=0,
                    format_func=_surrogate_target_label,
                    key="mf_target",
                )
                mf_train_clicked = st.button(
                    "训练多保真代理模型",
                    use_container_width=True,
                    key="mf_train_surrogate",
                )
        else:
            selected_dataset = ""
            target_column = DEFAULT_TARGET
            model_kind = "random_forest"
            uncertainty = "none"
            train_clicked = False
            ts_train_clicked = False
            ts_case_dataset = ""
            ts_frame_index = ""
            ts_field = "S"
            ts_metric = "max"
            ts_model_kind = "random_forest"
            low_dataset = ""
            high_dataset = ""
            mf_target = DEFAULT_TARGET
            mf_train_clicked = False
            st.info("还没有案例库训练数据集。先到“案例库”页导出训练数据集。")

        st.divider()
        st.markdown("**当前产物目录**")
        st.caption(f"`{SURROGATES_ROOT}`")

        st.divider()
        st.markdown("**闭环报告**")
        st.caption(f"`{CLOSED_LOOP_ROOT}`")
        closed_loop_clicked = st.button(
            "生成最新闭环报告",
            use_container_width=True,
            key="surrogate_closed_loop_report",
        )

    with right:
        if train_clicked:
            try:
                with st.spinner("正在训练代理模型并生成报告..."):
                    run = train_surrogate_from_dataset(
                        selected_dataset,
                        target_column=target_column,
                        model_kind=model_kind,
                        uncertainty=uncertainty,
                    )
                st.session_state["selected_surrogate_run"] = str(run.run_dir)
                st.success(f"代理模型训练完成：{run.run_dir.name}")
            except Exception as exc:
                st.error(f"代理模型训练失败：{exc}")

        if closed_loop_clicked:
            try:
                with st.spinner(
                    "正在汇总材料训练、Abaqus、案例库、数据集和代理模型..."
                ):
                    report = generate_closed_loop_report()
                st.session_state["selected_closed_loop_report"] = str(report.report_dir)
                st.success(f"闭环报告已生成：{report.report_dir.name}")
            except Exception as exc:
                st.error(f"闭环报告生成失败：{exc}")

        if ts_train_clicked:
            try:
                with st.spinner("正在训练 ODB 帧曲线时序代理模型..."):
                    ts_result = train_time_series_surrogate(
                        ts_frame_index,
                        ts_case_dataset,
                        target_field=ts_field.strip() or "S",
                        target_metric=ts_metric,
                        model_kind=ts_model_kind,
                    )
                if ts_result.get("error"):
                    st.warning(ts_result["error"])
                else:
                    st.success(f"时序代理模型已生成：{Path(ts_result['run_dir']).name}")
                    st.json(ts_result.get("metrics", {}))
                    plot_path = Path(ts_result.get("plot_path", ""))
                    if plot_path.exists():
                        st.image(
                            str(plot_path),
                            caption="时序曲线预测对比",
                            use_container_width=True,
                        )
            except Exception as exc:
                st.error(f"时序代理模型训练失败：{exc}")

        if mf_train_clicked:
            try:
                X_low, y_low, features = _dataset_to_xy(Path(low_dataset), mf_target)
                X_high, y_high, high_features = _dataset_to_xy(
                    Path(high_dataset), mf_target, feature_names=features
                )
                if features != high_features:
                    st.info("已按低保真数据集的数值特征列对高保真数据集做对齐。")
                with st.spinner("正在训练多保真代理模型..."):
                    mf_result = train_multi_fidelity(
                        X_low,
                        y_low,
                        X_high,
                        y_high,
                        name=f"mf_{Path(low_dataset).name}_{Path(high_dataset).name}_{mf_target}",
                    )
                st.success(f"多保真代理模型已生成：{mf_result.run_dir.name}")
                st.json(mf_result.metrics)
                if mf_result.plot_path.exists():
                    st.image(
                        str(mf_result.plot_path),
                        caption="多保真 vs 单保真",
                        use_container_width=True,
                    )
            except Exception as exc:
                st.error(f"多保真代理模型训练失败：{exc}")

        if datasets:
            comparison = surrogate_comparison_rows(
                dataset_dir=selected_dataset, target_column=target_column
            )
            _show_surrogate_comparison(comparison, title="同数据集模型对比")

        st.markdown("**训练历史**")
        runs = _list_surrogate_runs()
        if not runs:
            st.info("暂无代理模型训练记录。")
            _show_closed_loop_reports()
            return

        run_options = [str(path) for path in runs]
        default_index = 0
        selected = st.session_state.get("selected_surrogate_run")
        if selected in run_options:
            default_index = run_options.index(selected)
        chosen = st.selectbox(
            "选择代理模型 run",
            run_options,
            index=default_index,
            format_func=lambda item: Path(item).name,
            key="surrogate_run_selector",
        )
        st.session_state["selected_surrogate_run"] = chosen
        _show_surrogate_run(Path(chosen))
        st.divider()
        _show_closed_loop_reports()


def _management_panel(selected_run: Path | None) -> None:
    st.subheader("模型管理")
    material_col, run_col = st.columns([0.38, 0.62], gap="large")

    with material_col:
        st.markdown("**材料库**")
        presets = load_material_presets()
        if presets:
            st.dataframe(
                _material_table_rows(presets),
                use_container_width=True,
                hide_index=True,
                height=400,
            )
            selected = st.selectbox(
                "选择材料模板", list(presets), key="manager_material_name"
            )
            c1, c2 = st.columns(2)
            if c1.button(
                "加载到训练页", use_container_width=True, key="manager_load_material"
            ):
                for key, value in preset_to_training_state(presets[selected]).items():
                    st.session_state[key] = value
                st.success(f"已加载：{selected}")
            if c2.button(
                "删除模板", use_container_width=True, key="manager_delete_material"
            ):
                delete_material_preset(selected)
                st.success(f"已删除：{selected}")
                st.rerun()
            st.divider()
            st.markdown("**一键 Abaqus 验算**")
            allow_library_abaqus = st.checkbox(
                "允许本次调用 Abaqus", value=False, key="manager_allow_library_abaqus"
            )
            load_cases = st.number_input(
                "验算载荷工况数",
                min_value=1,
                max_value=9,
                value=1,
                step=1,
                key="manager_library_abaqus_cases",
            )
            quick_verify_clicked = st.button(
                "快速训练并验算",
                use_container_width=True,
                disabled=not allow_library_abaqus,
                key="manager_quick_verify_material",
            )
            if quick_verify_clicked:
                preset = presets[selected]
                try:
                    config = preset_to_workbench_config(
                        preset,
                        output_dir=RUNS_ROOT,
                        name_suffix="_library_verify",
                        calculate_curves=True,
                    )
                    with st.spinner("正在从材料库模板训练材料模型..."):
                        trained = _run_material_training_with_feedback(
                            config, "正在从材料库模板训练材料模型..."
                        )
                    if trained is not None:
                        st.session_state["selected_run_dir"] = str(trained.run_dir)
                        bridge_config = AbaqusBridgeConfig(
                            run_dir=trained.run_dir,
                            abaqus_bat=DEFAULT_ABAQUS_BAT,
                            max_load_cases=int(load_cases),
                            timeout_seconds=1800,
                        )
                        with st.spinner("正在调用 Abaqus 做快速单元验算..."):
                            bridge_result = run_abaqus_verification(bridge_config)
                        if bridge_result.status == "completed":
                            st.success(f"材料库验算完成：{trained.run_dir.name}")
                        else:
                            st.warning(f"Abaqus 验算状态：{bridge_result.status}")
                        _show_abaqus_summary(bridge_result.work_dir)
                except Exception as exc:
                    st.error(f"材料库快速验算失败：{exc}")
        else:
            st.info("材料库为空。")

    with run_col:
        st.markdown("**模型历史**")
        rows = _run_table_rows()
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True, height=400)
        else:
            st.info("暂无训练记录。")

        if selected_run:
            st.markdown("**当前选择**")
            st.caption(f"`{selected_run}`")
            _show_abaqus_summary(selected_run / "abaqus_verification")


def _run_selector(label: str, default_run: Path | None = None) -> Path | None:
    runs = _list_runs()
    if not runs:
        st.caption("暂无训练 run")
        return None

    options = [str(path) for path in runs]
    if (
        "selected_run_dir" in st.session_state
        and st.session_state["selected_run_dir"] in options
    ):
        index = options.index(st.session_state["selected_run_dir"])
    elif default_run and str(default_run) in options:
        index = options.index(str(default_run))
    else:
        index = 0
    selected = st.selectbox(
        label, options, index=index, format_func=lambda item: Path(item).name
    )
    st.session_state["selected_run_dir"] = selected
    return Path(selected)


def _ensure_training_defaults() -> None:
    defaults = {
        "train_material_type": "j2",
        "train_name": "app_j2",
        "train_E": 200_000.0,
        "train_nu": 0.3,
        "train_sy": 60.0,
        "train_C": 1.0,
        "train_gamma": 1.0,
        "train_n_load_cases": 40,
        "train_n_sequence": 4,
        "train_test_size": 80,
        "train_plot_mesh": 50,
        "train_calculate_curves": False,
        "train_barlat_exponent": 8.0,
        "train_hyperelastic_c10": 0.5,
        "train_hyperelastic_c01": 0.2,
        "train_hyperelastic_d1": 0.0,
        "library_save_name": "custom_material",
        "library_notes": "",
    }
    defaults.update(
        {f"train_hill_r{i + 1}": value for i, value in enumerate(HILL_RATIO_DEFAULTS)}
    )
    defaults.update(
        {
            f"train_barlat_a{i + 1}": value
            for i, value in enumerate(BARLAT_ALPHA_DEFAULTS)
        }
    )
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _sanitize_training_state() -> None:
    values: list[float] = []
    for idx, default in enumerate(HILL_RATIO_DEFAULTS):
        key = f"train_hill_r{idx + 1}"
        try:
            value = float(st.session_state.get(key, default))
        except (TypeError, ValueError):
            value = default
        if value <= 0:
            value = default
        values.append(value)

    if values and max(values) <= MIN_HILL_RATIO:
        values = list(HILL_RATIO_DEFAULTS)

    for idx, value in enumerate(values):
        st.session_state[f"train_hill_r{idx + 1}"] = value


def _show_run_summary(run_dir: Path) -> None:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        st.warning(f"未找到 summary.json: {summary_path}")
        return

    summary = _load_json(summary_path)
    ml = summary.get("ml_material", {})
    metrics = summary.get("metrics", {})
    outputs = summary.get("outputs", {})

    st.markdown(f"**Run**: `{run_dir.name}`")
    cols = st.columns(5)
    cols[0].metric("材料模型", ml.get("name", "N/A"))
    cols[1].metric("支持向量", ml.get("support_vectors", "N/A"))
    cols[2].metric("Accuracy", _fmt_metric(metrics.get("accuracy")))
    cols[3].metric("F1", _fmt_metric(metrics.get("f1")))
    cols[4].metric("MCC", _fmt_metric(metrics.get("mcc")))

    fig_cols = st.columns(2)
    _show_image(
        fig_cols[0], _resolve_output_path(outputs.get("yield_locus_png")), "屈服面"
    )
    _show_image(
        fig_cols[1], _resolve_output_path(outputs.get("stress_strain_png")), "应力-应变"
    )

    report_path = run_dir / "reports" / "material_model_report.md"
    if report_path.exists():
        with st.expander("材料训练报告", expanded=False):
            st.markdown(report_path.read_text(encoding="utf-8"))

    with st.expander("summary.json", expanded=False):
        st.json(summary)


def _show_abaqus_summary(work_dir: Path) -> None:
    summary_path = work_dir / "bridge_summary.json"
    if not summary_path.exists():
        st.info("当前 run 还没有 Abaqus 验算结果。")
        return

    summary = _load_json(summary_path)
    stats = summary.get("result_stats") or {}
    cols = st.columns(4)
    cols[0].metric("Abaqus 状态", summary.get("status", "N/A"))
    cols[1].metric("结果行数", stats.get("row_count", "N/A"))
    cols[2].metric("Max Mises", _fmt_metric(stats.get("max_mises_mpa")))
    cols[3].metric("Max PEEQ", _fmt_metric(stats.get("max_peeq")))

    plot_path = _resolve_output_path(summary.get("result_plot_png"))
    if plot_path and plot_path.exists():
        st.image(
            str(plot_path), caption="Abaqus 单元验算曲线", use_container_width=True
        )

    report_path = work_dir / "abaqus_verification_report.md"
    if report_path.exists():
        with st.expander("Abaqus 验算报告", expanded=False):
            st.markdown(report_path.read_text(encoding="utf-8"))

    result_csv = _resolve_output_path(summary.get("result_csv"))
    if result_csv and result_csv.exists():
        with st.expander("结果 CSV 预览", expanded=False):
            st.dataframe(
                _read_csv_preview(result_csv),
                use_container_width=True,
                hide_index=True,
                height=400,
            )

    with st.expander("bridge_summary.json", expanded=False):
        st.json(summary)


def _show_import_summary(import_dir: Path) -> None:
    summary = load_import_summary(import_dir)
    stats = summary.get("stats", {})
    st.markdown(f"**导入目录**: `{import_dir.name}`")
    cols = st.columns(4)
    cols[0].metric("有效行数", summary.get("row_count", "N/A"))
    cols[1].metric("最大应力", _fmt_metric(stats.get("max_stress_mpa")))
    cols[2].metric("最大应变", _fmt_metric(stats.get("max_strain")))
    cols[3].metric("初始模量", _fmt_metric(stats.get("initial_modulus_mpa")))

    preview_plot = summary.get("preview_plot", "")
    if preview_plot:
        plot_path = Path(preview_plot)
        if plot_path.exists():
            st.image(str(plot_path), caption="导入曲线预览", use_container_width=True)

    normalized_csv = Path(summary.get("normalized_csv", ""))
    if normalized_csv.exists():
        with st.expander("标准化曲线预览", expanded=False):
            st.dataframe(
                read_normalized_preview(normalized_csv),
                use_container_width=True,
                hide_index=True,
                height=400,
            )

    report_path = import_dir / "import_report.md"
    if report_path.exists():
        with st.expander("导入报告", expanded=False):
            st.markdown(report_path.read_text(encoding="utf-8"))

    with st.expander("summary.json", expanded=False):
        st.json(summary)


def _list_runs() -> list[Path]:
    if not RUNS_ROOT.exists():
        return []
    runs = [
        path
        for path in RUNS_ROOT.iterdir()
        if path.is_dir() and (path / "summary.json").exists()
    ]
    return sorted(runs, key=lambda path: path.stat().st_mtime, reverse=True)


def _find_abaqus_result_csv(run_dir: Path | None) -> Path | None:
    if not run_dir:
        return None
    results_dir = run_dir / "abaqus_verification" / "results"
    if not results_dir.exists():
        return None
    candidates = sorted(
        results_dir.glob("*-res.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _find_odb_candidates(run_dir: Path | None) -> list[Path]:
    """Find ODB files from the selected run directory and nearby locations.

    Searches: 1) run_dir/abaqus_verification, 2) cases/ with ODB references,
    3) the entire runs/ tree (breadth-first, limited).
    """
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(paths: list[Path]) -> None:
        for p in paths:
            key = str(p.resolve())
            if key not in seen and p.exists():
                seen.add(key)
                candidates.append(p)

    # 1) Direct abaqus_verification under selected run
    if run_dir:
        abaqus_dir = run_dir / "abaqus_verification"
        if abaqus_dir.exists():
            _add(
                sorted(
                    abaqus_dir.rglob("*.odb"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            )

    # 2) Also search the entire runs/ tree (if run_dir is inside runs/)
    if run_dir:
        runs_root = run_dir.parent  # typically runs/
        if runs_root.name == "runs" and runs_root.exists():
            for odb_path in sorted(
                runs_root.rglob("*.odb"), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                key = str(odb_path.resolve())
                if key not in seen:
                    seen.add(key)
                    candidates.append(odb_path)

    # 3) Check all known cases for ODB files
    try:
        from material_ai_workbench.case_library import list_cases

        for case in list_cases():
            # Check source folder directly
            source = Path(case.source_folder)
            if source.is_dir():
                for odb_path in sorted(
                    source.rglob("*.odb"), key=lambda p: p.stat().st_mtime, reverse=True
                ):
                    key = str(odb_path.resolve())
                    if key not in seen:
                        seen.add(key)
                        candidates.append(odb_path)
            elif source.suffix.lower() == ".odb" and source.exists():
                key = str(source.resolve())
                if key not in seen:
                    seen.add(key)
                    candidates.append(source)
    except Exception:
        pass

    return candidates[:50]  # Limit dropdown to 50 entries


def _find_inp_candidates(run_dir: Path | None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    roots = [
        run_dir,
        RUNS_ROOT,
        COMPOSITE_ROOT,
    ]
    for root in roots:
        if root is None or not Path(root).exists():
            continue
        for inp_path in sorted(
            Path(root).rglob("*.inp"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            key = str(inp_path.resolve())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(inp_path)
            if len(candidates) >= 50:
                return candidates
    return candidates


def _material_table_rows(presets: dict[str, MaterialPreset]) -> list[dict[str, Any]]:
    rows = []
    for preset in presets.values():
        rows.append(
            {
                "名称": preset.name,
                "类型": preset.material_type.upper(),
                "E(MPa)": preset.youngs_modulus,
                "nu": preset.poisson_ratio,
                "sy(MPa)": preset.yield_strength,
                "C": preset.c_value,
                "gamma": preset.gamma,
                "更新": preset.updated_at,
            }
        )
    return rows


def _run_table_rows() -> list[dict[str, Any]]:
    rows = []
    for run_dir in _list_runs():
        summary_path = run_dir / "summary.json"
        try:
            summary = _load_json(summary_path)
        except Exception as exc:
            LOGGER.warning(
                "Skipping unreadable run summary: %s (%s)", summary_path, exc
            )
            continue
        config = summary.get("config", {})
        ml = summary.get("ml_material", {})
        metrics = summary.get("metrics", {})
        bridge_path = run_dir / "abaqus_verification" / "bridge_summary.json"
        abaqus_status = "not_run"
        max_mises = None
        if bridge_path.exists():
            try:
                bridge = _load_json(bridge_path)
                abaqus_status = bridge.get("status", "unknown")
                max_mises = (bridge.get("result_stats") or {}).get("max_mises_mpa")
            except Exception as exc:
                LOGGER.warning("Failed to read %s: %s", bridge_path, exc)
                abaqus_status = "read_error"
        rows.append(
            {
                "run": run_dir.name,
                "材料": ml.get("name", ""),
                "类型": str(config.get("material_type", "")).upper(),
                "支持向量": ml.get("support_vectors", ""),
                "Accuracy": _round_or_blank(metrics.get("accuracy")),
                "F1": _round_or_blank(metrics.get("f1")),
                "Abaqus": abaqus_status,
                "Max Mises": _round_or_blank(max_mises),
            }
        )
    return rows


def _list_surrogate_runs() -> list[Path]:
    return list_surrogate_runs(SURROGATES_ROOT)


def _surrogate_target_label(value: str) -> str:
    labels = {
        "latest_odb_max_mises": "最大 Mises 应力",
        "latest_odb_max_displacement": "最大位移",
        "latest_odb_max_peeq": "最大等效塑性应变 PEEQ",
        "latest_odb_max_reaction_force": "最大反力",
    }
    return labels.get(value, value)


def _dataset_to_xy(
    dataset_dir: Path, target_column: str, feature_names: list[str] | None = None
):
    dataset_csv = dataset_dir / "case_dataset.csv"
    if not dataset_csv.exists():
        raise FileNotFoundError(f"case_dataset.csv not found: {dataset_csv}")
    with dataset_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No rows found in {dataset_csv}")
    clean_rows = []
    for row in rows:
        target = _try_float_ui(row.get(target_column))
        if target is not None:
            clean_rows.append((row, target))
    if len(clean_rows) < 2:
        raise ValueError(
            f"At least two rows with numeric {target_column} are required."
        )

    excluded = {
        "case_id",
        "title",
        "status",
        "tags",
        "source_folder",
        "latest_frame_series_csv",
        "updated_at",
        target_column,
    }
    if feature_names is None:
        candidates: list[str] = []
        for key in clean_rows[0][0]:
            if key in excluded:
                continue
            values = [_try_float_ui(row.get(key)) for row, _ in clean_rows]
            if any(value is not None for value in values):
                candidates.append(key)
        feature_names = candidates
    if not feature_names:
        raise ValueError(
            "No numeric feature columns found for multi-fidelity training."
        )

    X = []
    y = []
    for row, target in clean_rows:
        X.append([_try_float_ui(row.get(name)) or 0.0 for name in feature_names])
        y.append(float(target))
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float), list(feature_names)


def _try_float_ui(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _show_surrogate_run(run_dir: Path) -> None:
    metrics_path = run_dir / "surrogate_metrics.json"
    if not metrics_path.exists():
        st.warning(f"未找到代理模型指标：{metrics_path}")
        return

    metrics = _load_json(metrics_path)
    st.markdown(f"**Run**: `{run_dir.name}`")
    cols = st.columns(5)
    cols[0].metric(
        "目标", _surrogate_target_label(str(metrics.get("target_column", "")))
    )
    cols[1].metric("模型", str(metrics.get("model_kind", "N/A")))
    cols[2].metric("样本", metrics.get("sample_count", "N/A"))
    cols[3].metric("MAE", _fmt_metric(metrics.get("mae")))
    cols[4].metric("RMSE", _fmt_metric(metrics.get("rmse")))

    note = metrics.get("quality_note")
    if note:
        st.info(note)

    plot_path = run_dir / "prediction_vs_truth.png"
    if plot_path.exists():
        st.image(
            str(plot_path), caption="预测值 vs Abaqus 真值", use_container_width=True
        )

    predictions_csv = run_dir / "predictions.csv"
    if predictions_csv.exists():
        with st.expander("预测明细 CSV", expanded=False):
            st.dataframe(
                _read_csv_preview(predictions_csv),
                use_container_width=True,
                hide_index=True,
                height=400,
            )

    report_path = run_dir / "surrogate_report.md"
    if report_path.exists():
        with st.expander("代理模型报告", expanded=False):
            st.markdown(report_path.read_text(encoding="utf-8"))

    with st.expander("surrogate_metrics.json", expanded=False):
        st.json(metrics)


def _show_surrogate_comparison(
    rows: list[dict[str, Any]], *, title: str = "代理模型对比"
) -> None:
    st.markdown(f"**{title}**")
    if not rows:
        st.info("当前筛选条件下暂无可对比的代理模型。")
        return
    display_rows = [
        {
            "模型": row.get("model_kind", ""),
            "目标": _surrogate_target_label(str(row.get("target_column", ""))),
            "样本": row.get("sample_count", ""),
            "评估": row.get("evaluation_mode", ""),
            "MAE": _round_or_blank(row.get("mae")),
            "RMSE": _round_or_blank(row.get("rmse")),
            "R2": _round_or_blank(row.get("r2")),
            "平均相对误差": _round_or_blank(row.get("mean_relative_error")),
            "不确定性": row.get("uncertainty", ""),
            "PI 半宽": _round_or_blank(row.get("prediction_interval_mean_half_width")),
            "PI 覆盖率": _round_or_blank(row.get("prediction_interval_coverage")),
            "run": row.get("run", ""),
        }
        for row in rows
    ]
    st.dataframe(display_rows, use_container_width=True, hide_index=True, height=400)
    best = rows[0]
    st.success(
        f"当前最佳：`{best.get('model_kind', '')}`，RMSE={_fmt_metric(best.get('rmse'))}，run：`{best.get('run', '')}`。"
    )
    chart_rows = [
        {"run": str(row.get("run", ""))[:38], "RMSE": _try_float_ui(row.get("rmse"))}
        for row in rows
        if _try_float_ui(row.get("rmse")) is not None
    ]
    if chart_rows:
        st.bar_chart(chart_rows, x="run", y="RMSE", use_container_width=True)


def _show_closed_loop_reports() -> None:
    st.markdown("**闭环报告历史**")
    reports = list_closed_loop_reports()
    if not reports:
        st.info("暂无闭环报告。")
        return

    options = [str(path) for path in reports]
    default_index = 0
    selected = st.session_state.get("selected_closed_loop_report")
    if selected in options:
        default_index = options.index(selected)
    chosen = st.selectbox(
        "选择闭环报告",
        options,
        index=default_index,
        format_func=lambda item: Path(item).name,
        key="closed_loop_report_selector",
    )
    st.session_state["selected_closed_loop_report"] = chosen
    report_dir = Path(chosen)

    report_path = report_dir / "closed_loop_validation_report.md"
    if report_path.exists():
        with st.expander("闭环报告正文", expanded=True):
            st.markdown(report_path.read_text(encoding="utf-8"))

    manifest_path = report_dir / "closed_loop_manifest.json"
    if manifest_path.exists():
        with st.expander("closed_loop_manifest.json", expanded=False):
            st.json(_load_json(manifest_path))


def _show_batch_plan(plan: Any) -> None:
    data = plan.data
    st.markdown(f"**Plan**: `{Path(data.get('plan_dir', plan.plan_dir)).name}`")
    samples = data.get("samples", [])
    counts: dict[str, int] = {}
    for sample in samples:
        counts[sample.get("status", "unknown")] = (
            counts.get(sample.get("status", "unknown"), 0) + 1
        )
    cols = st.columns(4)
    cols[0].metric("样本数", len(samples))
    cols[1].metric("Pending", counts.get("pending", 0))
    cols[2].metric("Material", counts.get("material_completed", 0))
    cols[3].metric("Postprocessed", counts.get("postprocessed", 0))

    st.dataframe(
        batch_sample_table_rows(plan),
        use_container_width=True,
        hide_index=True,
        height=400,
    )
    trend_path = _resolve_output_path(
        (data.get("outputs") or {}).get("batch_trend_png")
    )
    if trend_path and trend_path.exists():
        st.image(str(trend_path), caption="Batch trend", use_container_width=True)

    outputs = data.get("outputs") or {}
    surrogate_runs = outputs.get("surrogate_runs") or {}
    if surrogate_runs:
        comparison = surrogate_comparison_rows(surrogate_runs.values())
        _show_surrogate_comparison(comparison, title="本批次代理模型对比")

    if plan.report_path.exists():
        with st.expander("批量计划报告", expanded=False):
            st.markdown(plan.report_path.read_text(encoding="utf-8"))
    with st.expander("batch_plan.json", expanded=False):
        st.json(data)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_output_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _show_image(container: Any, path: Path | None, caption: str) -> None:
    if path and path.exists():
        container.image(str(path), caption=caption, use_container_width=True)
    else:
        container.info(f"{caption} 暂无输出")


def _read_csv_preview(path: Path) -> list[dict[str, str]]:
    import csv

    rows: list[dict[str, str]] = []
    truncated = False
    with path.open("r", encoding="utf-8") as handle:
        delimiter = ";" if ";" in handle.readline() else ","
        handle.seek(0)
        reader = csv.DictReader(handle, delimiter=delimiter)
        for idx, row in enumerate(reader):
            if idx >= 30:
                truncated = True
                break
            rows.append(dict(row))
    if truncated:
        rows.append({"__preview_note__": "仅显示前 30 行，完整文件请打开 CSV 查看。"})
    return rows


def _parse_float_list(text: str) -> list[float]:
    values: list[float] = []
    for part in str(text).replace(";", ",").replace("，", ",").split(","):
        item = part.strip()
        if not item:
            continue
        values.append(float(item))
    if not values:
        raise ValueError("至少输入一个数值。")
    return values


def _fmt_metric(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.4g}"
    return str(value)


def _round_or_blank(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return round(value, 5)
    return "" if value is None else value


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #d8dee6;
            border-radius: 6px;
            padding: 0.6rem 0.75rem;
            background: #fbfcfd;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.15rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
