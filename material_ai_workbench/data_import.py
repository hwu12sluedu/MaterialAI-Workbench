"""CSV import utilities for material curves and Abaqus batch results."""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np

from material_ai_workbench.config import IMPORTS_ROOT as DEFAULT_IMPORTS_ROOT
from material_ai_workbench.config import RUNS_ROOT
from material_ai_workbench.pipeline import WorkbenchConfig

IMPORTS_ROOT = DEFAULT_IMPORTS_ROOT


@dataclass
class DataImportResult:
    import_dir: Path
    summary_path: Path
    normalized_csv: Path
    preview_plot: Path
    report_path: Path
    row_count: int
    source_kind: str
    material_name: str
    stress_column: str
    strain_column: str
    max_stress_mpa: float | None
    max_strain: float | None
    initial_modulus_mpa: float | None
    offset_yield_mpa: float | None
    warnings: list[str]


@dataclass
class DataImportValidationResult:
    import_dir: Path
    workbench_run_dir: Path
    validation_json: Path
    overlay_plot: Path
    report_path: Path
    material_type: str
    sample_count: int
    r2: float | None
    mean_abs_error_mpa: float
    max_abs_error_mpa: float


def import_csv_dataset(
    *,
    source_path: Path | None = None,
    source_bytes: bytes | None = None,
    source_name: str = "uploaded.csv",
    source_kind: str = "experiment_curve",
    material_name: str = "imported_material",
    imports_root: Path = IMPORTS_ROOT,
) -> DataImportResult:
    if source_path is None and source_bytes is None:
        raise ValueError("source_path or source_bytes is required.")

    import_dir = _prepare_import_dir(imports_root, material_name, source_name)
    raw_dir = import_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / _safe_filename(source_name)

    if source_path is not None:
        shutil.copy2(source_path, raw_path)
    else:
        raw_path.write_bytes(source_bytes or b"")

    rows = _read_csv_rows(raw_path)
    stress_column, strain_column, warnings = _detect_columns(rows)
    if source_kind == "abaqus_batch_result":
        warnings.append("Abaqus 批量结果可能包含多个载荷路径，初始模量和屈服估计仅作为快速预览。")
    raw_strain, raw_stress = _raw_numeric_columns(rows, stress_column, strain_column)
    warnings.extend(_validate_stress_strain_curve(raw_strain, raw_stress))
    normalized = _normalize_curve_rows(rows, stress_column, strain_column)
    if not normalized:
        raise ValueError("No numeric stress-strain rows were found in the selected CSV.")
    warnings.extend(
        warning
        for warning in _validate_stress_strain_curve(
            [row["strain"] for row in normalized],
            [row["stress_mpa"] for row in normalized],
        )
        if warning not in warnings and "units may be percent" not in warning
    )
    warnings = _dedupe_curve_warnings(warnings)

    stats = _curve_stats(normalized)
    normalized_csv = import_dir / "normalized_curve.csv"
    _write_normalized_csv(normalized_csv, normalized)

    preview_plot = import_dir / "curve_preview.png"
    _plot_curve(preview_plot, normalized, material_name)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_kind": source_kind,
        "material_name": material_name,
        "source_name": source_name,
        "raw_csv": str(raw_path),
        "normalized_csv": str(normalized_csv),
        "preview_plot": str(preview_plot),
        "row_count": len(normalized),
        "stress_column": stress_column,
        "strain_column": strain_column,
        "stats": stats,
        "warnings": warnings,
    }
    summary_path = import_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report_path = import_dir / "import_report.md"
    report_path.write_text(_report_markdown(summary), encoding="utf-8")

    return DataImportResult(
        import_dir=import_dir,
        summary_path=summary_path,
        normalized_csv=normalized_csv,
        preview_plot=preview_plot,
        report_path=report_path,
        row_count=len(normalized),
        source_kind=source_kind,
        material_name=material_name,
        stress_column=stress_column,
        strain_column=strain_column,
        max_stress_mpa=stats.get("max_stress_mpa"),
        max_strain=stats.get("max_strain"),
        initial_modulus_mpa=stats.get("initial_modulus_mpa"),
        offset_yield_mpa=stats.get("offset_yield_mpa"),
        warnings=warnings,
    )


def validate_imported_curve_with_workbench(
    import_dir: Path | str,
    *,
    material_type: str = "j2",
    output_dir: Path | None = None,
    poisson_ratio: float = 0.3,
    n_load_cases: int = 24,
    test_size: int = 40,
) -> DataImportValidationResult:
    """Train a workbench material from an imported curve and compare curves.

    This gives the data-import workflow a closed loop: raw CSV -> normalized
    curve -> pyLabFEA/MaterialAI training -> generated uniaxial curve -> error
    metrics and overlay plot.
    """

    root = Path(import_dir)
    config = imported_curve_to_config(
        root,
        material_type=material_type,
        output_dir=output_dir or RUNS_ROOT,
        poisson_ratio=poisson_ratio,
    )
    if config is None:
        raise ValueError("Imported curve cannot be converted to a workbench training config.")

    experimental = _read_normalized_curve(root / "normalized_curve.csv")
    if len(experimental) < 3:
        raise ValueError("Need at least three normalized curve points for validation.")

    max_exp_strain = max(row["strain"] for row in experimental)
    config.calculate_curves = True
    config.n_load_cases = int(n_load_cases)
    config.test_size = int(test_size)
    config.strain_max = max(float(config.strain_max), float(max_exp_strain) * 1.05, 0.005)

    from material_ai_workbench.pipeline import run_material_workbench

    workbench_result = run_material_workbench(config)
    predicted = _read_workbench_uniaxial_curve(workbench_result.stress_strain_csv)
    metrics = _curve_validation_metrics(experimental, predicted)

    validation_dir = root / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    overlay_plot = validation_dir / "experiment_vs_workbench.png"
    validation_json = validation_dir / "validation_summary.json"
    report_path = validation_dir / "validation_report.md"
    _plot_validation_overlay(overlay_plot, experimental, predicted, metrics, root.name)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "import_dir": str(root),
        "material_type": material_type,
        "workbench_run_dir": str(workbench_result.run_dir),
        "workbench_summary": str(workbench_result.summary_path),
        "workbench_curve_csv": str(workbench_result.stress_strain_csv),
        "overlay_plot": str(overlay_plot),
        **metrics,
    }
    validation_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(_validation_report_markdown(payload), encoding="utf-8")
    _append_validation_to_import_report(root, report_path, overlay_plot, metrics)
    _update_import_summary_with_validation(root, payload)

    return DataImportValidationResult(
        import_dir=root,
        workbench_run_dir=workbench_result.run_dir,
        validation_json=validation_json,
        overlay_plot=overlay_plot,
        report_path=report_path,
        material_type=material_type,
        sample_count=int(metrics["sample_count"]),
        r2=metrics.get("r2"),
        mean_abs_error_mpa=float(metrics["mean_abs_error_mpa"]),
        max_abs_error_mpa=float(metrics["max_abs_error_mpa"]),
    )


def list_imports(imports_root: Path = IMPORTS_ROOT) -> list[Path]:
    if not imports_root.exists():
        return []
    return sorted(
        [path for path in imports_root.iterdir() if path.is_dir() and (path / "summary.json").exists()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def load_import_summary(import_dir: Path) -> dict[str, Any]:
    return json.loads((import_dir / "summary.json").read_text(encoding="utf-8"))


def workbench_config_from_import(
    import_dir: Path | str,
    *,
    material_type: str = "j2",
    output_dir: Path | None = None,
    name: str | None = None,
) -> WorkbenchConfig:
    """Create a starter WorkbenchConfig from a normalized experimental curve."""

    summary = load_import_summary(Path(import_dir))
    stats = summary.get("stats", {})
    youngs_modulus = _positive_or_default(stats.get("initial_modulus_mpa"), 200_000.0)
    yield_strength = _positive_or_default(stats.get("offset_yield_mpa") or stats.get("max_stress_mpa"), 60.0)
    material_name = name or f"{summary.get('material_name', 'imported')}_{material_type}"
    return WorkbenchConfig(
        material_type=material_type,
        name=material_name,
        output_dir=output_dir or RUNS_ROOT,
        youngs_modulus=youngs_modulus,
        poisson_ratio=0.3,
        yield_strength=yield_strength,
        calculate_curves=True,
    )


def imported_curve_to_config(
    import_dir: Path | str,
    *,
    material_type: str = "j2",
    output_dir: Path | None = None,
    poisson_ratio: float = 0.3,
) -> WorkbenchConfig | None:
    """Build a WorkbenchConfig from an imported experimental stress-strain curve.

    The initial modulus is estimated from the first 0.05% strain when enough
    points exist. Yield strength uses a 0.2% offset intersection.
    """

    root = Path(import_dir)
    summary_path = root / "summary.json"
    curve_csv = root / "normalized_curve.csv"
    if not summary_path.exists() or not curve_csv.exists():
        return None

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    strains: list[float] = []
    stresses: list[float] = []
    with curve_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            strain = _to_float(row.get("strain"))
            stress = _to_float(row.get("stress_mpa"))
            if strain is not None and stress is not None:
                strains.append(strain)
                stresses.append(stress)
    if len(strains) < 3:
        return None

    strain_arr = np.asarray(strains, dtype=float)
    stress_arr = np.asarray(stresses, dtype=float)
    order = np.argsort(strain_arr)
    strain_arr = strain_arr[order]
    stress_arr = stress_arr[order]

    elastic = strain_arr <= 0.0005
    if int(np.sum(elastic)) < 3:
        elastic = np.arange(len(strain_arr)) < max(3, int(len(strain_arr) * 0.1))
    try:
        youngs_modulus = float(np.polyfit(strain_arr[elastic], stress_arr[elastic], 1)[0])
    except Exception:
        youngs_modulus = 200_000.0
    if not math.isfinite(youngs_modulus) or youngs_modulus <= 0:
        youngs_modulus = 200_000.0

    yield_strength = _estimate_offset_yield(strain_arr, stress_arr, youngs_modulus)
    if yield_strength is None:
        yield_strength = float(np.nanmax(stress_arr)) if len(stress_arr) else 60.0
    yield_strength = _positive_or_default(yield_strength, 60.0)

    return WorkbenchConfig(
        material_type=material_type,
        name=f"exp_{_safe_label(str(summary.get('material_name') or root.name))}",
        output_dir=output_dir or RUNS_ROOT,
        youngs_modulus=float(youngs_modulus),
        poisson_ratio=float(poisson_ratio),
        yield_strength=float(yield_strength),
        calculate_curves=True,
    )


def read_normalized_preview(path: Path, limit: int = 30) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            if idx >= limit:
                break
            rows.append(dict(row))
    return rows


def _read_normalized_curve(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            strain = _to_float(row.get("strain"))
            stress = _to_float(row.get("stress_mpa"))
            if strain is not None and stress is not None:
                rows.append({"strain": strain, "stress_mpa": stress})
    return sorted(rows, key=lambda item: item["strain"])


def _read_workbench_uniaxial_curve(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            load_case = str(row.get("load_case", "")).lower()
            load_case_name = str(row.get("load_case_name", "")).lower()
            if load_case != "stx" and "uniax-x" not in load_case_name:
                continue
            strain_percent = _to_float(row.get("eq_strain_percent"))
            stress = _to_float(row.get("eq_stress_j2_mpa"))
            if strain_percent is None or stress is None:
                continue
            rows.append(
                {
                    "material": str(row.get("material", "")),
                    "strain": strain_percent / 100.0,
                    "stress_mpa": stress,
                }
            )
    if not rows:
        raise ValueError(f"No uniaxial workbench curve rows found in {path}")

    ml_rows = [row for row in rows if "ml" in row["material"].lower()]
    reference_rows = [row for row in rows if "reference" in row["material"].lower()]
    selected = ml_rows or reference_rows or rows
    return _deduplicate_curve_by_strain(
        [{"strain": float(row["strain"]), "stress_mpa": float(row["stress_mpa"])} for row in selected]
    )


def _deduplicate_curve_by_strain(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    grouped: dict[float, list[float]] = {}
    for row in sorted(rows, key=lambda item: item["strain"]):
        grouped.setdefault(float(row["strain"]), []).append(float(row["stress_mpa"]))
    return [{"strain": strain, "stress_mpa": float(np.mean(values))} for strain, values in grouped.items()]


def _curve_validation_metrics(experimental: list[dict[str, float]], predicted: list[dict[str, float]]) -> dict[str, Any]:
    exp_strain = np.asarray([row["strain"] for row in experimental], dtype=float)
    exp_stress = np.asarray([row["stress_mpa"] for row in experimental], dtype=float)
    pred_strain = np.asarray([row["strain"] for row in predicted], dtype=float)
    pred_stress = np.asarray([row["stress_mpa"] for row in predicted], dtype=float)
    order = np.argsort(pred_strain)
    pred_strain = pred_strain[order]
    pred_stress = pred_stress[order]
    mask = (
        np.isfinite(exp_strain)
        & np.isfinite(exp_stress)
        & (exp_strain >= float(np.nanmin(pred_strain)))
        & (exp_strain <= float(np.nanmax(pred_strain)))
    )
    if int(np.sum(mask)) < 2:
        raise ValueError("Experimental and workbench curves do not overlap enough for validation.")
    truth = exp_stress[mask]
    interp = np.interp(exp_strain[mask], pred_strain, pred_stress)
    error = interp - truth
    ss_res = float(np.sum(error**2))
    ss_tot = float(np.sum((truth - float(np.mean(truth))) ** 2))
    r2 = None if ss_tot < 1e-12 else float(1.0 - ss_res / ss_tot)
    return {
        "sample_count": int(len(truth)),
        "r2": r2,
        "mean_abs_error_mpa": float(np.mean(np.abs(error))),
        "max_abs_error_mpa": float(np.max(np.abs(error))),
        "max_exp_stress_mpa": float(np.max(truth)),
        "max_workbench_stress_mpa": float(np.max(interp)),
        "strain_min": float(np.min(exp_strain[mask])),
        "strain_max": float(np.max(exp_strain[mask])),
    }


def _plot_validation_overlay(
    path: Path,
    experimental: list[dict[str, float]],
    predicted: list[dict[str, float]],
    metrics: dict[str, Any],
    title: str,
) -> None:
    exp_strain = [row["strain"] for row in experimental]
    exp_stress = [row["stress_mpa"] for row in experimental]
    pred_strain = [row["strain"] for row in predicted]
    pred_stress = [row["stress_mpa"] for row in predicted]
    fig, ax = plt.subplots(figsize=(8, 5), dpi=160)
    ax.plot(exp_strain, exp_stress, color="#dc2626", linewidth=2.0, label="experiment")
    ax.plot(pred_strain, pred_stress, color="#2563eb", linewidth=1.8, linestyle="--", label="workbench")
    ax.set_title(f"Experiment vs Workbench: {title}")
    ax.set_xlabel("Strain")
    ax.set_ylabel("Stress (MPa)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    text = f"R2={_fmt(metrics.get('r2'))}\\nMAE={_fmt(metrics.get('mean_abs_error_mpa'))} MPa"
    ax.text(0.02, 0.98, text, transform=ax.transAxes, va="top", ha="left", fontsize=9, bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "#d1d5db"})
    fig.tight_layout()
    try:
        fig.savefig(str(path))
    except Exception:
        pass
    plt.close(fig)


def _validation_report_markdown(payload: dict[str, Any]) -> str:
    return f"""# Imported Curve Validation

## Inputs

- Import directory: `{payload['import_dir']}`
- Material type: `{payload['material_type']}`
- Workbench run: `{payload['workbench_run_dir']}`
- Workbench curve CSV: `{payload['workbench_curve_csv']}`

## Metrics

- Sample count: `{payload['sample_count']}`
- R2: `{_fmt(payload.get('r2'))}`
- Mean absolute error: `{_fmt(payload.get('mean_abs_error_mpa'))} MPa`
- Max absolute error: `{_fmt(payload.get('max_abs_error_mpa'))} MPa`
- Compared strain range: `{_fmt(payload.get('strain_min'))}` to `{_fmt(payload.get('strain_max'))}`

## Outputs

- Overlay plot: `{payload['overlay_plot']}`
- Validation JSON: `validation_summary.json`
"""


def _append_validation_to_import_report(root: Path, report_path: Path, overlay_plot: Path, metrics: dict[str, Any]) -> None:
    import_report = root / "import_report.md"
    if not import_report.exists():
        return
    text = import_report.read_text(encoding="utf-8")
    marker = "\n## Workbench Curve Validation\n"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n"
    text += f"""{marker}
- Validation report: `{report_path}`
- Overlay plot: `{overlay_plot}`
- R2: `{_fmt(metrics.get('r2'))}`
- Mean absolute error: `{_fmt(metrics.get('mean_abs_error_mpa'))} MPa`
- Max absolute error: `{_fmt(metrics.get('max_abs_error_mpa'))} MPa`
"""
    import_report.write_text(text, encoding="utf-8")


def _update_import_summary_with_validation(root: Path, payload: dict[str, Any]) -> None:
    summary_path = root / "summary.json"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["validation"] = payload
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _positive_or_default(value: Any, default: float) -> float:
    try:
        number = float(value)
        if math.isfinite(number) and number > 0:
            return number
    except (TypeError, ValueError):
        pass
    return float(default)


def _prepare_import_dir(root: Path, material_name: str, source_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = _safe_label(f"{material_name}_{Path(source_name).stem}")
    import_dir = root / f"{stamp}_{label}"
    import_dir.mkdir(parents=True, exist_ok=True)
    return import_dir


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows: list[dict[str, str]] = []
    for row in csv.DictReader(text.splitlines(), delimiter=delimiter):
        rows.append({str(key).strip(): str(value).strip() for key, value in row.items() if key is not None})
    if not rows:
        raise ValueError(f"No rows found in CSV: {path}")
    return rows


def _detect_columns(rows: list[dict[str, str]]) -> tuple[str, str, list[str]]:
    columns = list(rows[0].keys())
    normalized = {_norm_col(column): column for column in columns}
    stress_column = _first_matching(
        normalized,
        [
            "stress_mpa",
            "engineering_stress_mpa",
            "true_stress_mpa",
            "eq_stress_j2_mpa",
            "mises",
            "s11",
            "stress",
            "sigma",
            "sig",
        ],
    )
    strain_column = _first_matching(
        normalized,
        [
            "strain",
            "engineering_strain",
            "true_strain",
            "eq_strain_percent",
            "e11",
            "le11",
            "eps",
            "epsilon",
        ],
    )
    warnings: list[str] = []
    if stress_column is None:
        stress_column = _best_numeric_column(rows, prefer_large=True)
        warnings.append(f"未识别标准应力列，已尝试使用 `{stress_column}`。")
    if strain_column is None:
        strain_column = _best_numeric_column(rows, prefer_large=False, exclude={stress_column})
        warnings.append(f"未识别标准应变列，已尝试使用 `{strain_column}`。")
    if stress_column == strain_column:
        raise ValueError("Could not identify separate stress and strain columns.")
    return stress_column, strain_column, warnings


def _normalize_curve_rows(rows: list[dict[str, str]], stress_column: str, strain_column: str) -> list[dict[str, float]]:
    curve: list[dict[str, float]] = []
    strain_values: list[float] = []
    for idx, row in enumerate(rows):
        stress = _to_float(row.get(stress_column))
        strain = _to_float(row.get(strain_column))
        if stress is None or strain is None:
            continue
        strain_values.append(strain)
        curve.append({"source_row": float(idx + 1), "strain": strain, "stress_mpa": stress})

    if _looks_like_percent(strain_column, strain_values):
        for item in curve:
            item["strain"] = item["strain"] / 100.0
    return curve


def _raw_numeric_columns(rows: list[dict[str, str]], stress_column: str, strain_column: str) -> tuple[list[float], list[float]]:
    strain: list[float] = []
    stress: list[float] = []
    for row in rows:
        strain.append(_to_float_loose(row.get(strain_column)))
        stress.append(_to_float_loose(row.get(stress_column)))
    return strain, stress


def _validate_stress_strain_curve(strain: list[float], stress: list[float]) -> list[str]:
    """Return validation warnings for stress-strain input data."""

    warnings: list[str] = []
    if not strain or not stress:
        return ["No numeric stress-strain data detected"]
    s_strain = np.asarray(strain, dtype=float)
    s_stress = np.asarray(stress, dtype=float)

    if np.any(np.diff(s_strain) <= 0):
        warnings.append("Strain is not strictly monotonic increasing")
    if np.any(np.isnan(s_strain)) or np.any(np.isnan(s_stress)):
        warnings.append("NaN values detected")
    if np.any(np.isinf(s_strain)) or np.any(np.isinf(s_stress)):
        warnings.append("Inf values detected")

    finite = np.isfinite(s_strain) & np.isfinite(s_stress)
    if int(np.sum(finite)) >= 5:
        f_strain = s_strain[finite]
        f_stress = s_stress[finite]
        n_fit = max(3, int(len(f_strain) * 0.1))
        x, y = f_strain[:n_fit], f_stress[:n_fit]
        if np.std(x) > 1e-12:
            slope = float(np.polyfit(x, y, 1)[0])
            if slope <= 0:
                warnings.append(f"Initial modulus appears negative or zero ({slope:.1f})")
            elif slope > 500_000:
                warnings.append(f"Initial modulus unusually high ({slope:.0f} MPa)")

    finite_strain = s_strain[np.isfinite(s_strain)]
    if len(finite_strain):
        max_strain = float(np.max(np.abs(finite_strain)))
        if max_strain > 2:
            warnings.append(f"Strain range {max_strain:.2f} - units may be percent, not absolute")

    return warnings


def _dedupe_curve_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for warning in warnings:
        key = _warning_category(warning)
        if key in seen:
            continue
        seen.add(key)
        result.append(warning)
    return result


def _warning_category(warning: str) -> str:
    text = str(warning)
    if "units may be percent" in text:
        return "strain_percent_units"
    if "not strictly monotonic" in text:
        return "strain_monotonic"
    if "NaN values" in text:
        return "nan_values"
    if "Inf values" in text:
        return "inf_values"
    if "Initial modulus appears negative or zero" in text:
        return "initial_modulus_nonpositive"
    if "Initial modulus unusually high" in text:
        return "initial_modulus_high"
    return text


def _curve_stats(curve: list[dict[str, float]]) -> dict[str, float | None]:
    strain = np.array([row["strain"] for row in curve], dtype=float)
    stress = np.array([row["stress_mpa"] for row in curve], dtype=float)
    order = np.argsort(strain)
    strain = strain[order]
    stress = stress[order]

    modulus = _estimate_initial_modulus(strain, stress)
    offset_yield = _estimate_offset_yield(strain, stress, modulus)
    return {
        "min_strain": float(np.nanmin(strain)),
        "max_strain": float(np.nanmax(strain)),
        "min_stress_mpa": float(np.nanmin(stress)),
        "max_stress_mpa": float(np.nanmax(stress)),
        "initial_modulus_mpa": modulus,
        "offset_yield_mpa": offset_yield,
    }


def _estimate_initial_modulus(strain: np.ndarray, stress: np.ndarray) -> float | None:
    mask = np.isfinite(strain) & np.isfinite(stress) & (strain >= 0)
    strain = strain[mask]
    stress = stress[mask]
    if len(strain) < 3:
        return None
    limit = max(0.0015, float(np.nanmax(strain)) * 0.15)
    elastic = strain <= limit
    if int(np.sum(elastic)) < 3:
        elastic = np.arange(len(strain)) < min(5, len(strain))
    try:
        slope, _ = np.polyfit(strain[elastic], stress[elastic], 1)
    except Exception:
        return None
    if not math.isfinite(float(slope)) or slope <= 0:
        return None
    return float(slope)


def _estimate_offset_yield(strain: np.ndarray, stress: np.ndarray, modulus: float | None) -> float | None:
    if modulus is None or len(strain) < 5:
        return None
    offset_line = modulus * (strain - 0.002)
    diff = stress - offset_line
    valid = np.where((strain >= 0.002) & np.isfinite(diff))[0]
    if len(valid) == 0:
        return None
    for idx in valid:
        if diff[idx] <= 0:
            prev = max(0, int(idx) - 1)
            if prev == idx or not np.isfinite(diff[prev]):
                return float(stress[int(idx)])
            denom = diff[prev] - diff[idx]
            if abs(float(denom)) < 1e-12:
                return float(stress[int(idx)])
            ratio = float(diff[prev] / denom)
            return float(stress[prev] + ratio * (stress[idx] - stress[prev]))
    return float(np.nanmax(stress[valid]))


def _write_normalized_csv(path: Path, curve: list[dict[str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_row", "strain", "stress_mpa"])
        writer.writeheader()
        writer.writerows(curve)


def _plot_curve(path: Path, curve: list[dict[str, float]], material_name: str) -> None:
    strain = [row["strain"] for row in curve]
    stress = [row["stress_mpa"] for row in curve]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(strain, stress, color="#c43c3c", linewidth=1.8)
    ax.set_title(f"{material_name} stress-strain preview")
    ax.set_xlabel("Strain")
    ax.set_ylabel("Stress (MPa)")
    ax.grid(True, alpha=0.25)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.9, bottom=0.13)
    try:
        fig.savefig(str(path), dpi=180)
    except Exception:
        pass
    plt.close(fig)


def _report_markdown(summary: dict[str, Any]) -> str:
    stats = summary["stats"]
    warnings = summary.get("warnings") or []
    warning_text = "\n".join(f"- {item}" for item in warnings) if warnings else "- 无"
    return f"""# 数据导入报告

## 数据来源

- 类型：`{summary["source_kind"]}`
- 材料名：`{summary["material_name"]}`
- 原始文件：`{summary["raw_csv"]}`
- 标准化曲线：`{summary["normalized_csv"]}`

## 自动识别

- 应力列：`{summary["stress_column"]}`
- 应变列：`{summary["strain_column"]}`
- 有效数据行：`{summary["row_count"]}`

## 初步统计

- 最大应力：`{_fmt(stats.get("max_stress_mpa"))} MPa`
- 最大应变：`{_fmt(stats.get("max_strain"))}`
- 初始模量估计：`{_fmt(stats.get("initial_modulus_mpa"))} MPa`
- 0.2% offset 屈服估计：`{_fmt(stats.get("offset_yield_mpa"))} MPa`

## Validation

{warning_text}

## 后续用途

这份标准化曲线可作为后续真实材料数据入口，用于拟合材料参数、对比 Abaqus 验算曲线，或作为神经网络代理模型的数据来源。
"""


def _first_matching(normalized_columns: dict[str, str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in normalized_columns:
            return normalized_columns[candidate]
    for candidate in candidates:
        for normalized, original in normalized_columns.items():
            if candidate in normalized:
                return original
    return None


def _best_numeric_column(rows: list[dict[str, str]], *, prefer_large: bool, exclude: set[str] | None = None) -> str:
    exclude = exclude or set()
    scores: list[tuple[float, str]] = []
    for column in rows[0].keys():
        if column in exclude:
            continue
        values = [_to_float(row.get(column)) for row in rows]
        numeric = [value for value in values if value is not None]
        if len(numeric) < max(3, len(rows) // 3):
            continue
        spread = float(np.nanmax(numeric) - np.nanmin(numeric))
        magnitude = float(np.nanmax(np.abs(numeric)))
        score = magnitude + spread if prefer_large else -(magnitude + spread)
        scores.append((score, column))
    if not scores:
        raise ValueError("No numeric columns found in CSV.")
    return sorted(scores, reverse=True)[0][1]


def _looks_like_percent(column: str, values: list[float]) -> bool:
    normalized = _norm_col(column)
    if "percent" in normalized or normalized.endswith("_pct") or normalized.endswith("%"):
        return True
    if not values:
        return False
    max_abs = max(abs(value) for value in values)
    return max_abs > 2.0


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    if not math.isfinite(result):
        return None
    return result


def _to_float_loose(value: str | None) -> float:
    if value is None:
        return float("nan")
    text = str(value).strip().replace(",", "")
    if not text:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def _safe_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", value.strip())
    return cleaned.strip("_") or "dataset"


def _safe_filename(value: str) -> str:
    name = Path(value).name or "uploaded.csv"
    return re.sub(r"[^A-Za-z0-9_.\-]+", "_", name)


def _norm_col(value: str) -> str:
    return re.sub(r"[^a-z0-9%]+", "_", value.strip().lower()).strip("_")


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.6g}"
    return str(value)
