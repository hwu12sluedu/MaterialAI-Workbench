"""Chinese engineering report generator for MaterialAI Workbench.

Generates a professional Chinese-language report from any closed-loop run,
covering model assumptions, material data, Abaqus job status, results,
warnings, and next validation actions.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_engineering_report(
    run_dir: Path | str,
    *,
    output_path: Path | str | None = None,
    report_type: str = "metal_closed_loop",
) -> Path:
    """Generate a Chinese engineering report from a completed run.

    Args:
        run_dir: Path to the run directory containing summary.json and optionally
                 abaqus_verification/ or manifest.json.
        output_path: Where to write the report. Default: run_dir/engineering_report.md.
        report_type: "metal_closed_loop" or "composite_closed_loop".

    Returns:
        Path to the generated report.
    """
    root = Path(run_dir)
    summary = _load_json(root / "summary.json")
    bridge = _load_json(root / "abaqus_verification" / "bridge_summary.json")
    manifest = _load_json(root / "manifest.json")
    dataset_row = _read_csv_row(root / "composite_plate_dataset_row.csv")

    lines = _build_report(
        run_name=root.name,
        report_type=report_type,
        summary=summary,
        bridge=bridge,
        manifest=manifest,
        dataset_row=dataset_row,
    )

    out = Path(output_path) if output_path else root / "engineering_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _load_json(path: Path) -> dict[str, Any] | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _read_csv_row(path: Path) -> dict[str, str] | None:
    import csv
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else None


def _build_report(
    *,
    run_name: str,
    report_type: str,
    summary: dict[str, Any] | None,
    bridge: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    dataset_row: dict[str, str] | None,
) -> list[str]:
    L: list[str] = []

    L.append(f"# MaterialAI Workbench 工程验证报告")
    L.append("")
    L.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    L.append(f"**运行标识：** `{run_name}`")
    L.append(f"**报告类型：** {_type_label(report_type)}")
    L.append("")

    # ---- 1. Model Assumptions ----
    L.append("## 1. 模型假设与输入")
    L.append("")

    if summary:
        cfg = summary.get("config", {})
        ref = summary.get("reference_material", {})
        ml = summary.get("ml_material", {})
        metrics = summary.get("metrics", {})

        L.append("### 材料参数")
        L.append("")
        L.append(f"| 参数 | 数值 |")
        L.append(f"|---|---|")
        L.append(f"| 材料类型 | `{cfg.get('material_type', 'N/A')}` |")
        L.append(f"| 弹性模量 E | {_fmt(ref.get('E_mpa'))} MPa |")
        L.append(f"| 泊松比 ν | {_fmt(ref.get('nu'))} |")
        L.append(f"| 屈服强度 σ<sub>y</sub> | {_fmt(ref.get('yield_strength_mpa'))} MPa |")
        if cfg.get("hill_ratios"):
            hr = cfg["hill_ratios"]
            if isinstance(hr, list) and len(hr) == 6:
                L.append(f"| Hill 各向异性比 r1..r6 | {hr[0]:.2f}, {hr[1]:.2f}, {hr[2]:.2f}, {hr[3]:.2f}, {hr[4]:.2f}, {hr[5]:.2f} |")
        L.append("")

        L.append("### SVC 训练参数")
        L.append("")
        L.append(f"| 参数 | 数值 |")
        L.append(f"|---|---|")
        L.append(f"| 正则化 C | {_fmt(ml.get('C'))} |")
        L.append(f"| 核宽度 γ | {_fmt(ml.get('gamma'))} |")
        L.append(f"| 训练载荷方向数 | {cfg.get('n_load_cases', 'N/A')} |")
        L.append(f"| 弹塑性采样序列 | {cfg.get('n_sequence', 'N/A')} |")
        L.append(f"| 支持向量数 | {ml.get('support_vectors', 'N/A')} |")
        L.append("")

        L.append("### 训练指标")
        L.append("")
        L.append(f"| 指标 | 数值 |")
        L.append(f"|---|---|")
        L.append(f"| MAE | {_fmt(metrics.get('mae'))} |")
        L.append(f"| Precision | {_fmt(metrics.get('precision'))} |")
        L.append(f"| Accuracy | {_fmt(metrics.get('accuracy'))} |")
        L.append(f"| Recall | {_fmt(metrics.get('recall'))} |")
        L.append(f"| F1 Score | {_fmt(metrics.get('f1'))} |")
        L.append(f"| MCC | {_fmt(metrics.get('mcc'))} |")
        L.append("")

    pbc: dict[str, Any] = {}
    plate: dict[str, Any] = {}
    micro: dict[str, Any] = {}
    if manifest:
        cfg = manifest.get("config", {})
        est = manifest.get("estimated_effective_properties", {})
        eff = manifest.get("effective_properties", {})
        pbc = manifest.get("pbc_homogenization", {}) or {}
        plate = manifest.get("plate_results", {}) or {}
        micro = manifest.get("microstructure_metrics", {}) or {}

        L.append("### 复合材料参数")
        L.append("")
        L.append(f"| 参数 | 数值 |")
        L.append(f"|---|---|")
        L.append(f"| 纤维体积分数 V<sub>f</sub> | {_fmt(cfg.get('fiber_volume_fraction'))} |")
        L.append(f"| 纤维 E<sub>f</sub> | {_fmt(cfg.get('fiber_e'))} MPa |")
        L.append(f"| 基体 E<sub>m</sub> | {_fmt(cfg.get('matrix_e'))} MPa |")
        L.append(f"| 界面效率 η | {_fmt(cfg.get('interface_efficiency'))} |")
        L.append(f"| 孔半径 R | {_fmt(cfg.get('hole_radius'))} mm |")
        L.append(f"| 板尺寸 L×W×T | {_fmt(cfg.get('length'))}×{_fmt(cfg.get('width'))}×{_fmt(cfg.get('thickness'))} mm |")
        L.append("")

        L.append("### 有效属性")
        L.append("")
        L.append(f"| 属性 | 混合律估算 | Abaqus 均匀化 |")
        L.append(f"|---|---|---|")
        for key, label in [("E1", "E₁"), ("E2", "E₂"), ("E3", "E₃"),
                          ("G12", "G₁₂"), ("G13", "G₁₃"), ("G23", "G₂₃")]:
            rom = _fmt(est.get(key))
            abq = _fmt(eff.get(key)) if eff.get(key) != est.get(key) else "—"
            L.append(f"| {label} | {rom} MPa | {abq} |")
        L.append("")

        if micro:
            L.append(f"- 实际纤维体积分数：{_fmt(micro.get('actual_vf'))}")
            L.append(f"- 目标 V<sub>f</sub>：{_fmt(micro.get('target_vf'))}")
            L.append(f"- 纤维数：{micro.get('fiber_count', 'N/A')}")
            L.append("")

    # ---- 2. Abaqus Job Status ----
    L.append("## 2. Abaqus 求解状态")
    L.append("")
    if bridge:
        L.append(f"| 项目 | 状态 |")
        L.append(f"|---|---|")
        L.append(f"| 验算状态 | `{bridge.get('status', 'N/A')}` |")
        stats = bridge.get("result_stats") or {}
        L.append(f"| 结果行数 | {stats.get('row_count', 'N/A')} |")
        L.append(f"| 最大 Mises 应力 | {_fmt(stats.get('max_mises_mpa'))} MPa |")
        L.append(f"| 最大 PEEQ | {_fmt(stats.get('max_peeq'))} |")

        result_csv = bridge.get("result_csv")
        if result_csv:
            L.append(f"| 结果 CSV | `{result_csv}` |")
        L.append("")

    if manifest:
        abaqus_status = manifest.get("abaqus_status", "N/A")
        pbc_status = "completed" if pbc else "not_run"
        L.append(f"| 项目 | 状态 |")
        L.append(f"|---|---|")
        L.append(f"| 带孔板 Abaqus | `{abaqus_status}` |")
        L.append(f"| PBC 均匀化 | `{pbc_status}` |")
        L.append("")

    if plate:
        L.append(f"- 板孔最大 Mises：**{_fmt(plate.get('max_mises_mpa'))} MPa**")
        L.append(f"- 最大位移：{_fmt(plate.get('max_displacement'))} mm")
        L.append(f"- 反力 ΣRF1：{_fmt(plate.get('sum_rf1'))} N")
        L.append("")

    # ---- 3. Dataset Row (if available) ----
    if dataset_row:
        L.append("## 3. 数据集记录")
        L.append("")
        L.append(f"| 字段 | 值 |")
        L.append(f"|---|---|")
        for key in ["fiber_volume_fraction", "actual_vf", "E1", "E2", "G12",
                     "max_stress_near_hole_estimate_mpa", "hole_radius"]:
            if key in dataset_row:
                L.append(f"| {key} | {_fmt(dataset_row.get(key))} |")
        L.append("")

    # ---- 4. Warnings & Cautions ----
    L.append("## 4. 注意事项与后续行动")
    L.append("")
    warnings = []
    if summary and summary.get("config", {}).get("calculate_curves") is False:
        warnings.append("- 本次未计算 pyLabFEA 应力-应变曲线（`calculate_curves=false`）。如需对比实验曲线，请重新运行并启用曲线计算。")
    if bridge is None and manifest is None:
        warnings.append("- 未检测到 Abaqus 验算结果。建议运行 Abaqus UMAT 单元验算以验证 ML 材料模型的力学行为。")
    if manifest and not manifest.get("pbc_homogenization"):
        warnings.append("- PBC 均匀化未执行。当前有效属性来自混合律估算，建议运行 6 工况 PBC 求解以获得 Abaqus 验证的刚度矩阵。")
    if manifest and manifest.get("abaqus_status") != "completed":
        warnings.append("- 带孔板 Abaqus 求解未完成或失败。请检查 Abaqus 日志确认原因。")
    if warnings:
        for w in warnings:
            L.append(w)
    else:
        L.append("- 未检测到明显问题。建议追加不同 V<sub>f</sub> 和孔半径的批量参数扫描以扩充训练数据。")
    L.append("")

    # ---- 5. Next Validation Actions ----
    L.append("## 5. 建议的下一步验证")
    L.append("")
    L.append("1. 将生成的 UMAT 参数 CSV 和 meta JSON 导入 Abaqus/Standard 进行独立验证。")
    L.append("2. 使用案例库积累至少 20 个不同参数的 Abaqus 运行结果。")
    L.append("3. 在代理模型面板进行 RF vs MLP vs GBR 多模型对比，选择最优模型。")
    L.append("4. 用自然语言仿真功能复现当前配置，验证 LLM→执行→入库的完整闭环。")
    L.append("5. 导出数据集并检查 `split_manifest.json` 中的特征/目标分类和泄漏警告。")
    L.append("")

    return L


def _fmt(value: Any) -> str:
    """Format a value for display in a report table."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        if abs(value) < 0.001 and value != 0:
            return f"{value:.4e}"
        return f"{value:.3f}"
    return str(value)


def _type_label(report_type: str) -> str:
    return {
        "metal_closed_loop": "金属塑性闭环验证",
        "composite_closed_loop": "复合材料微观-宏观闭环验证",
    }.get(report_type, report_type)
