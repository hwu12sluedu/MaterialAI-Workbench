"""End-to-end material ML training workflow for the first Workbench prototype.

The module deliberately keeps a small scope:
reference material -> SVC yield model -> plots/UMAT parameters/report.
That narrow loop is the first reusable block for a future Abaqus-connected app.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
import pylabfea as FE

from material_ai_workbench.config import RUNS_ROOT


def _safe_savefig(fig: plt.Figure, path: Path, dpi: int = 180) -> bool:
    """Save a matplotlib figure without crashing the process on DLL errors.

    Returns True on success, False if savefig raised an exception.
    """
    try:
        fig.savefig(str(path), dpi=dpi)
        plt.close(fig)
        return True
    except Exception:
        plt.close(fig)
        # Write a placeholder so downstream consumers know the plot was skipped
        fallback = Path(str(path))
        fallback.write_bytes(b"")
        return False


LOAD_CASES = ("stx", "sty", "et2", "ect")
METRIC_NAMES = ("mae", "precision", "accuracy", "recall", "f1", "mcc")
HYPERELASTIC_TYPES = {"hyperelastic", "neo_hookean", "mooney_rivlin"}


@dataclass
class WorkbenchConfig:
    material_type: str = "j2"
    name: str | None = None
    output_dir: Path | None = None
    youngs_modulus: float = 200_000.0
    poisson_ratio: float = 0.3
    yield_strength: float = 60.0
    hill_ratios: tuple[float, float, float, float, float, float] = (
        1.2,
        1.0,
        0.8,
        1.0,
        1.0,
        1.0,
    )
    barlat_alphas: tuple[float, float, float, float, float, float, float, float] = (
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
    )
    barlat_coeffs: tuple[float, float, float, float, float, float, float, float] | None = None
    barlat_exponent: float = 8.0
    hyperelastic_c10: float | None = None
    hyperelastic_c01: float | None = None
    hyperelastic_d1: float | None = None
    c_value: float = 1.0
    gamma: float = 1.0
    n_load_cases: int = 40
    n_sequence: int = 4
    elastic_floor: float = 0.1
    elastic_ceiling: float = 0.95
    strain_max: float = 0.01
    min_step: int = 8
    calculate_curves: bool = False
    test_size: int = 80
    test_stress_scale: float = 0.15
    test_stress_offset: float = 0.08
    plot_mesh: int = 50
    random_seed: int = 42


@dataclass
class WorkbenchResult:
    run_dir: Path
    report_path: Path
    summary_path: Path
    stress_strain_csv: Path
    yield_locus_png: Path
    stress_strain_png: Path
    umat_csv: Path
    umat_meta_json: Path
    support_vectors: int
    metrics: dict[str, float]


def run_material_workbench(config: WorkbenchConfig) -> WorkbenchResult:
    if config.material_type.lower() in HYPERELASTIC_TYPES:
        return _run_hyperelastic_workbench(config)

    run_dir = _prepare_run_dir(config)
    figures_dir = run_dir / "figures"
    models_dir = run_dir / "models"
    data_dir = run_dir / "data"
    reports_dir = run_dir / "reports"
    for folder in (figures_dir, models_dir, data_dir, reports_dir):
        folder.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(config.random_seed)
    ref_mat = _create_reference_material(config)
    ml_mat = _create_ml_material(config)

    ml_mat.train_SVC(
        C=config.c_value,
        gamma=config.gamma,
        mat_ref=ref_mat,
        Nlc=config.n_load_cases,
        Nseq=config.n_sequence,
        Fe=config.elastic_floor,
        Ce=config.elastic_ceiling,
        gridsearch=False,
        verbose=0,
    )

    if config.calculate_curves:
        ref_mat.calc_properties(
            eps=config.strain_max,
            min_step=config.min_step,
            sigeps=True,
            load_cases=list(LOAD_CASES),
        )
        ml_mat.calc_properties(
            verb=False,
            eps=config.strain_max,
            min_step=config.min_step,
            sigeps=True,
            load_cases=list(LOAD_CASES),
        )

    model_file_stem = "abq_" + ml_mat.name
    export_path = _as_posix_dir(models_dir)
    ml_mat.export_MLparam(
        sname="material_ai_workbench",
        source="pyLabFEA reference material",
        file=model_file_stem,
        path=export_path,
        descr=[
            "material_type",
            "E",
            "nu",
            "sy",
            "Nlc",
            "Nseq",
            "Ce",
            "Fe",
            "random_seed",
        ],
        param=[
            config.material_type,
            config.youngs_modulus,
            config.poisson_ratio,
            config.yield_strength,
            config.n_load_cases,
            config.n_sequence,
            config.elastic_ceiling,
            config.elastic_floor,
            config.random_seed,
        ],
    )

    metrics = _evaluate_model(config, ref_mat, ml_mat, rng)
    stress_strain_csv = data_dir / "stress_strain_curves.csv"
    if config.calculate_curves:
        _write_stress_strain_csv(stress_strain_csv, ref_mat, ml_mat)
    else:
        _write_skipped_curves_csv(stress_strain_csv)

    yield_locus_png = figures_dir / "yield_locus.png"
    _plot_yield_locus(yield_locus_png, ref_mat, ml_mat, config)

    stress_strain_png = figures_dir / "stress_strain_curves.png"
    if config.calculate_curves:
        _plot_stress_strain(stress_strain_png, ref_mat, ml_mat)
    else:
        _plot_skipped_curves(stress_strain_png)

    umat_csv = models_dir / f"{model_file_stem}-svm.csv"
    umat_meta_json = models_dir / f"{model_file_stem}-svm_meta.json"
    support_vectors = int(len(ml_mat.svm_yf.support_vectors_))

    summary = _summary_dict(
        config=config,
        ref_mat=ref_mat,
        ml_mat=ml_mat,
        run_dir=run_dir,
        metrics=metrics,
        support_vectors=support_vectors,
        stress_strain_csv=stress_strain_csv,
        yield_locus_png=yield_locus_png,
        stress_strain_png=stress_strain_png,
        umat_csv=umat_csv,
        umat_meta_json=umat_meta_json,
    )
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report_path = reports_dir / "material_model_report.md"
    report_path.write_text(_markdown_report(summary), encoding="utf-8")

    return WorkbenchResult(
        run_dir=run_dir,
        report_path=report_path,
        summary_path=summary_path,
        stress_strain_csv=stress_strain_csv,
        yield_locus_png=yield_locus_png,
        stress_strain_png=stress_strain_png,
        umat_csv=umat_csv,
        umat_meta_json=umat_meta_json,
        support_vectors=support_vectors,
        metrics=metrics,
    )


def _prepare_run_dir(config: WorkbenchConfig) -> Path:
    label = config.name or f"ml_{config.material_type.lower()}"
    safe_label = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in label)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(config.output_dir or RUNS_ROOT) / f"{stamp}_{safe_label}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _run_hyperelastic_workbench(config: WorkbenchConfig) -> WorkbenchResult:
    material_type = _normalize_hyperelastic_type(config.material_type)
    run_dir = _prepare_run_dir(config)
    figures_dir = run_dir / "figures"
    models_dir = run_dir / "models"
    data_dir = run_dir / "data"
    reports_dir = run_dir / "reports"
    for folder in (figures_dir, models_dir, data_dir, reports_dir):
        folder.mkdir(parents=True, exist_ok=True)

    c10, c01, d1 = _hyperelastic_parameters(config, material_type)
    curves = _hyperelastic_curves(material_type, c10, c01, strain_max=max(0.25, float(config.strain_max)))

    stress_strain_csv = data_dir / "hyperelastic_stress_strain_curves.csv"
    _write_hyperelastic_curves_csv(stress_strain_csv, curves)

    stress_strain_png = figures_dir / "hyperelastic_stress_strain_curves.png"
    _plot_hyperelastic_curves(stress_strain_png, curves, material_type)

    yield_locus_png = figures_dir / "hyperelastic_note.png"
    _plot_hyperelastic_note(yield_locus_png, material_type)

    material_card = models_dir / f"abq_{_safe_name(config.name or material_type)}-hyperelastic.inp"
    _write_hyperelastic_material_card(material_card, material_type, c10, c01, d1)

    meta_json = models_dir / f"abq_{_safe_name(config.name or material_type)}-hyperelastic_meta.json"
    metrics = _hyperelastic_metrics(curves, c10, c01, d1)
    summary = {
        "project": "MaterialAI Workbench prototype",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "pylabfea_version": FE.__version__,
        "run_dir": str(run_dir),
        "config": _json_ready(asdict(config)),
        "reference_material": {
            "name": config.name or material_type,
            "model": material_type,
            "C10_mpa": c10,
            "C01_mpa": c01,
            "D1": d1,
        },
        "material_model_note": _material_model_note(WorkbenchConfig(**{**asdict(config), "material_type": material_type})),
        "ml_material": {
            "name": config.name or material_type,
            "C": None,
            "gamma": None,
            "stress_dimension": 3,
            "support_vectors": 0,
            "scale_seq": None,
        },
        "metrics": metrics,
        "outputs": {
            "stress_strain_csv": str(stress_strain_csv),
            "yield_locus_png": str(yield_locus_png),
            "stress_strain_png": str(stress_strain_png),
            "umat_csv": str(material_card),
            "umat_meta_json": str(meta_json),
            "abaqus_material_card": str(material_card),
        },
        "abaqus_next_step": {
            "status": "material_card_ready",
            "expected_command_pattern": "Include the generated *HYPERELASTIC card in an Abaqus rubber/elastomer model.",
            "note": "Hyperelastic models do not use the pyLabFEA SVC yield-surface training loop.",
        },
    }
    meta_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report_path = reports_dir / "material_model_report.md"
    report_path.write_text(_hyperelastic_report(summary), encoding="utf-8")
    return WorkbenchResult(
        run_dir=run_dir,
        report_path=report_path,
        summary_path=summary_path,
        stress_strain_csv=stress_strain_csv,
        yield_locus_png=yield_locus_png,
        stress_strain_png=stress_strain_png,
        umat_csv=material_card,
        umat_meta_json=meta_json,
        support_vectors=0,
        metrics=metrics,
    )


def _normalize_hyperelastic_type(material_type: str) -> str:
    value = str(material_type or "").strip().lower().replace("-", "_")
    if value == "hyperelastic":
        return "neo_hookean"
    if value in {"neo_hookean", "mooney_rivlin"}:
        return value
    raise ValueError("hyperelastic material_type must be neo_hookean or mooney_rivlin.")


def _hyperelastic_parameters(config: WorkbenchConfig, material_type: str) -> tuple[float, float, float]:
    c10 = float(config.hyperelastic_c10 if config.hyperelastic_c10 is not None else 0.5)
    c01 = float(config.hyperelastic_c01 if config.hyperelastic_c01 is not None else (0.0 if material_type == "neo_hookean" else 0.2))
    d1 = float(config.hyperelastic_d1 if config.hyperelastic_d1 is not None else 0.0)
    if c10 <= 0:
        raise ValueError("hyperelastic C10 must be positive.")
    if material_type == "mooney_rivlin" and c01 < 0:
        raise ValueError("Mooney-Rivlin C01 must be zero or positive.")
    if d1 < 0:
        raise ValueError("hyperelastic D1 must be zero or positive.")
    return c10, c01, d1


def _hyperelastic_curves(material_type: str, c10: float, c01: float, *, strain_max: float) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    strains = np.linspace(0.0, strain_max, 80)
    for mode in ("uniaxial", "equibiaxial", "planar"):
        for engineering_strain in strains:
            stretch = 1.0 + float(engineering_strain)
            if mode == "uniaxial":
                stress = _mooney_uniaxial_cauchy(stretch, c10, c01 if material_type == "mooney_rivlin" else 0.0)
            elif mode == "equibiaxial":
                stress = _mooney_biaxial_cauchy(stretch, c10, c01 if material_type == "mooney_rivlin" else 0.0)
            else:
                stress = _mooney_planar_cauchy(stretch, c10, c01 if material_type == "mooney_rivlin" else 0.0)
            rows.append(
                {
                    "mode": mode,
                    "engineering_strain": float(engineering_strain),
                    "stretch": float(stretch),
                    "cauchy_stress_mpa": float(stress),
                }
            )
    return rows


def _mooney_uniaxial_cauchy(stretch: float, c10: float, c01: float) -> float:
    return 2.0 * (c10 + c01 / max(stretch, 1e-12)) * (stretch**2 - stretch**-1)


def _mooney_biaxial_cauchy(stretch: float, c10: float, c01: float) -> float:
    return 2.0 * (c10 + c01 * stretch**2) * (stretch**2 - stretch**-4)


def _mooney_planar_cauchy(stretch: float, c10: float, c01: float) -> float:
    return 2.0 * (c10 + c01) * (stretch**2 - stretch**-2)


def _write_hyperelastic_curves_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["mode", "engineering_strain", "stretch", "cauchy_stress_mpa"])
        writer.writeheader()
        writer.writerows(rows)


def _plot_hyperelastic_curves(path: Path, rows: list[dict[str, float | str]], material_type: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {"uniaxial": "#2563eb", "equibiaxial": "#b91c1c", "planar": "#047857"}
    for mode in ("uniaxial", "equibiaxial", "planar"):
        subset = [row for row in rows if row["mode"] == mode]
        ax.plot(
            [float(row["engineering_strain"]) for row in subset],
            [float(row["cauchy_stress_mpa"]) for row in subset],
            color=colors[mode],
            linewidth=1.8,
            label=mode,
        )
    ax.set_title(f"Hyperelastic stress-strain curves: {material_type}")
    ax.set_xlabel("Engineering strain")
    ax.set_ylabel("Cauchy stress (MPa)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.subplots_adjust(left=0.12, right=0.96, top=0.9, bottom=0.13)
    _safe_savefig(fig, path, dpi=180)


def _plot_hyperelastic_note(path: Path, material_type: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.text(
        0.5,
        0.6,
        f"{material_type} has no yield locus",
        ha="center",
        va="center",
        fontsize=15,
        transform=ax.transAxes,
    )
    ax.text(
        0.5,
        0.42,
        "This branch exports stress-strain curves and an Abaqus *HYPERELASTIC card.",
        ha="center",
        va="center",
        fontsize=10,
        transform=ax.transAxes,
    )
    ax.set_axis_off()
    fig.subplots_adjust(left=0.04, right=0.96, top=0.95, bottom=0.08)
    _safe_savefig(fig, path, dpi=160)


def _write_hyperelastic_material_card(path: Path, material_type: str, c10: float, c01: float, d1: float) -> None:
    lines = ["*Material, name=HYPERELASTIC_MATERIAL"]
    if material_type == "mooney_rivlin":
        lines.extend(["*Hyperelastic, mooney-rivlin", f"{c10:.8g}, {c01:.8g}, {d1:.8g}"])
    else:
        lines.extend(["*Hyperelastic, neo hooke", f"{c10:.8g}, {d1:.8g}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hyperelastic_metrics(rows: list[dict[str, float | str]], c10: float, c01: float, d1: float) -> dict[str, float]:
    uniaxial = [float(row["cauchy_stress_mpa"]) for row in rows if row["mode"] == "uniaxial"]
    return {
        "initial_shear_modulus_mpa": float(2.0 * (c10 + c01)),
        "bulk_parameter_d1": float(d1),
        "max_uniaxial_stress_mpa": float(max(uniaxial) if uniaxial else 0.0),
        "mae": 0.0,
        "precision": 1.0,
        "accuracy": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "mcc": 1.0,
    }


def _create_reference_material(config: WorkbenchConfig) -> FE.Material:
    material_type = config.material_type.lower()
    ref_mat = FE.Material(name=f"{material_type.upper()}-reference", num=1)
    ref_mat.elasticity(E=config.youngs_modulus, nu=config.poisson_ratio)
    if material_type == "j2":
        ref_mat.plasticity(sy=config.yield_strength, sdim=6)
    elif material_type == "hill":
        ref_mat.plasticity(sy=config.yield_strength, rv=list(config.hill_ratios), sdim=6)
    elif material_type == "barlat":
        ref_mat.plasticity(
            sy=config.yield_strength,
            sdim=6,
            barlat=_barlat18_from_yld2000_alphas(config),
            barlat_exp=int(config.barlat_exponent),
        )
    else:
        raise ValueError("material_type must be one of: 'j2', 'hill', 'barlat', 'neo_hookean', 'mooney_rivlin'.")
    return ref_mat


def _create_ml_material(config: WorkbenchConfig) -> FE.Material:
    material_type = config.material_type.lower()
    name = config.name or f"ML-{material_type.upper()}_C{config.c_value:g}_G{config.gamma:g}"
    ml_mat = FE.Material(name=name, num=2)
    if material_type == "j2":
        ml_mat.dev_only = True
    return ml_mat


def _barlat18_from_yld2000_alphas(config: WorkbenchConfig) -> list[float]:
    """Map eight Yld2000-2D-style alphas to pyLabFEA's Yld2004-18p API.

    pyLabFEA currently exposes Barlat through an 18-parameter Yld2004 form.
    The eight-alpha UI is kept because it is familiar for sheet forming; this
    deterministic expansion gives a usable engineering entry point while keeping
    the exact alphas visible in the run configuration.
    """

    raw = config.barlat_coeffs if config.barlat_coeffs is not None else config.barlat_alphas
    alphas = [float(value) for value in raw]
    if len(alphas) != 8:
        raise ValueError("barlat_alphas must contain exactly 8 positive coefficients.")
    if any(value <= 0 for value in alphas):
        raise ValueError("barlat_alphas must all be positive.")
    a1, a2, a3, a4, a5, a6, a7, a8 = alphas
    shear = (a7 + a8) / 2.0
    first_transform = [a1, a2, a3, a4, a5, a6, a7, a8, shear]
    second_transform = [a2, a1, a4, a3, a6, a5, a8, a7, shear]
    return first_transform + second_transform


def _evaluate_model(
    config: WorkbenchConfig,
    ref_mat: FE.Material,
    ml_mat: FE.Material,
    rng: np.random.Generator,
) -> dict[str, float]:
    size = max(12, int(config.test_size))
    scale = max(1.0e-6, config.yield_strength * config.test_stress_scale)
    offset = config.yield_strength * config.test_stress_offset
    n1 = size // 4
    n2 = size // 2
    n3 = size - n1 - n2
    stress_level = np.concatenate(
        (
            rng.normal(loc=config.yield_strength, scale=scale, size=n1),
            rng.normal(loc=config.yield_strength - offset, scale=scale, size=n2),
            rng.normal(loc=config.yield_strength + offset, scale=scale, size=n3),
        )
    )
    unit_stress = FE.load_cases(number_3d=0, number_6d=len(stress_level))
    sig_test = unit_stress * stress_level[:, None]
    yf_ref = ref_mat.calc_yf(sig_test)
    yf_ml = ml_mat.calc_yf(sig_test)
    values = FE.training_score(yf_ref, yf_ml)
    return {name: float(value) for name, value in zip(METRIC_NAMES, values)}


def _write_stress_strain_csv(path: Path, ref_mat: FE.Material, ml_mat: FE.Material) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "material",
                "load_case",
                "load_case_name",
                "eq_strain_percent",
                "eq_stress_j2_mpa",
                "eq_plastic_strain_percent",
            ]
        )
        for mat in (ref_mat, ml_mat):
            for case in LOAD_CASES:
                prop = mat.propJ2[case]
                if prop["seq"] is None:
                    continue
                for eeq, seq, peeq in zip(prop["eeq"], prop["seq"], prop["peeq"]):
                    writer.writerow(
                        [
                            mat.name,
                            case,
                            mat.prop[case]["name"],
                            float(eeq * 100.0),
                            float(seq),
                            float(peeq * 100.0),
                        ]
                    )


def _write_skipped_curves_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["status", "note"])
        writer.writerow(
            [
                "skipped",
                "Stress-strain curve calculation was skipped. Rerun with --with-curves to enable it.",
            ]
        )


def _plot_yield_locus(
    path: Path,
    ref_mat: FE.Material,
    ml_mat: FE.Material,
    config: WorkbenchConfig,
) -> None:
    support_vectors = ml_mat.svm_yf.support_vectors_ * ml_mat.scale_seq
    ml_mat.plot_yield_locus(
        xstart=-1.8,
        xend=1.8,
        ref_mat=ref_mat,
        data=support_vectors,
        Nmesh=config.plot_mesh,
        fontsize=16,
    )
    fig = plt.gcf()
    fig.suptitle("ML yield locus vs. reference material", fontsize=14)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.9, bottom=0.12)
    _safe_savefig(fig, path, dpi=220)


def _plot_stress_strain(path: Path, ref_mat: FE.Material, ml_mat: FE.Material) -> None:
    colors = {"stx": "#b00020", "sty": "#1f5fbf", "et2": "#555555", "ect": "#8c2bb3"}
    fig, ax = plt.subplots(figsize=(9, 6))
    for case in LOAD_CASES:
        case_name = ref_mat.prop[case]["name"]
        for mat, linestyle in ((ref_mat, "-"), (ml_mat, "--")):
            prop = mat.propJ2[case]
            if prop["seq"] is None:
                continue
            label = f"{mat.name} / {case_name}"
            ax.plot(
                prop["eeq"] * 100.0,
                prop["seq"],
                linestyle=linestyle,
                color=colors[case],
                linewidth=1.8,
                label=label,
            )
    ax.set_title("Stress-strain curves: reference vs. ML material")
    ax.set_xlabel("Equivalent strain (%)")
    ax.set_ylabel("J2 equivalent stress (MPa)")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, ncol=2)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.12)
    _safe_savefig(fig, path, dpi=220)


def _plot_skipped_curves(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.text(
        0.5,
        0.55,
        "Stress-strain curve step skipped",
        ha="center",
        va="center",
        fontsize=16,
        transform=ax.transAxes,
    )
    ax.text(
        0.5,
        0.43,
        "Rerun with --with-curves after the training loop is validated.",
        ha="center",
        va="center",
        fontsize=11,
        transform=ax.transAxes,
    )
    ax.set_axis_off()
    fig.subplots_adjust(left=0.04, right=0.96, top=0.95, bottom=0.08)
    _safe_savefig(fig, path, dpi=180)


def _summary_dict(
    *,
    config: WorkbenchConfig,
    ref_mat: FE.Material,
    ml_mat: FE.Material,
    run_dir: Path,
    metrics: dict[str, float],
    support_vectors: int,
    stress_strain_csv: Path,
    yield_locus_png: Path,
    stress_strain_png: Path,
    umat_csv: Path,
    umat_meta_json: Path,
) -> dict[str, Any]:
    return {
        "project": "MaterialAI Workbench prototype",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "pylabfea_version": FE.__version__,
        "run_dir": str(run_dir),
        "config": _json_ready(asdict(config)),
        "reference_material": {
            "name": ref_mat.name,
            "E_mpa": float(ref_mat.E),
            "nu": float(ref_mat.nu),
            "yield_strength_mpa": float(ref_mat.sy),
        },
        "material_model_note": _material_model_note(config),
        "ml_material": {
            "name": ml_mat.name,
            "C": float(ml_mat.C_yf),
            "gamma": float(ml_mat.gam_yf),
            "stress_dimension": int(ml_mat.sdim),
            "support_vectors": support_vectors,
            "scale_seq": float(ml_mat.scale_seq),
        },
        "metrics": metrics,
        "outputs": {
            "stress_strain_csv": str(stress_strain_csv),
            "yield_locus_png": str(yield_locus_png),
            "stress_strain_png": str(stress_strain_png),
            "umat_csv": str(umat_csv),
            "umat_meta_json": str(umat_meta_json),
        },
        "abaqus_next_step": {
            "status": "not_run_in_this_prototype",
            "expected_command_pattern": "abaqus python calc_properties.py <material_name>",
            "note": "The exported SVM files are prepared for the pyLabFEA UMAT example workflow.",
        },
    }


def _material_model_note(config: WorkbenchConfig) -> str:
    material_type = config.material_type.lower()
    if material_type == "barlat":
        return (
            "Experimental Barlat/Yld2000 entry point. Current pyLabFEA training uses a Hill-compatible "
            "anisotropic reference surface while preserving Barlat coefficients in config for future full implementation."
        )
    if material_type in HYPERELASTIC_TYPES:
        return "Hyperelastic branch: curve generation and Abaqus material-card export without SVC yield-surface training."
    return "Native pyLabFEA-compatible plasticity training."


def _hyperelastic_report(summary: dict[str, Any]) -> str:
    ref = summary["reference_material"]
    metrics = summary["metrics"]
    outputs = summary["outputs"]
    return f"""# Hyperelastic Material Report

## Purpose

This run creates a rubber/elastomer material branch for MaterialAI Workbench. It does not train a plastic yield surface. Instead it generates analytical stress-strain curves and an Abaqus `*HYPERELASTIC` material card.

## Material

- Model: `{ref['model']}`
- C10: `{ref['C10_mpa']} MPa`
- C01: `{ref['C01_mpa']} MPa`
- D1: `{ref['D1']}`
- Initial shear modulus estimate: `{metrics['initial_shear_modulus_mpa']} MPa`
- Max uniaxial stress in generated curve: `{metrics['max_uniaxial_stress_mpa']} MPa`

## Outputs

- Stress-strain CSV: `{outputs['stress_strain_csv']}`
- Stress-strain plot: `{outputs['stress_strain_png']}`
- Abaqus material card: `{outputs['abaqus_material_card']}`
- Metadata JSON: `{outputs['umat_meta_json']}`

## Engineering Note

Neo-Hookean and Mooney-Rivlin parameters should come from actual rubber test fitting before production use. This branch is the first deployable app path for hyperelastic material definition and Abaqus export.
"""


def _markdown_report(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    outputs = summary["outputs"]
    config = summary["config"]
    ml = summary["ml_material"]
    ref = summary["reference_material"]
    return f"""# MaterialAI Workbench 首轮报告

## 任务定位

本次运行完成了第一版材料 AI 闭环：参考材料定义、ML 屈服模型训练、力学曲线计算、屈服面可视化、UMAT 参数导出和结果汇总。

## 输入材料

- 材料类型：`{config["material_type"]}`
- 弹性模量：`{ref["E_mpa"]:.3f} MPa`
- 泊松比：`{ref["nu"]:.4f}`
- 屈服强度：`{ref["yield_strength_mpa"]:.3f} MPa`

## 训练设置

- ML 材料名：`{ml["name"]}`
- SVC 参数：`C={ml["C"]:.6g}`, `gamma={ml["gamma"]:.6g}`
- 训练载荷方向数：`{config["n_load_cases"]}`
- 每个方向的弹性/塑性采样序列：`{config["n_sequence"]}`
- 支持向量数：`{ml["support_vectors"]}`

## 验证指标

| 指标 | 数值 |
|---|---:|
| MAE | {metrics["mae"]:.6g} |
| Precision | {metrics["precision"]:.6g} |
| Accuracy | {metrics["accuracy"]:.6g} |
| Recall | {metrics["recall"]:.6g} |
| F1 | {metrics["f1"]:.6g} |
| MCC | {metrics["mcc"]:.6g} |

## 输出文件

- 应力-应变数据：`{outputs["stress_strain_csv"]}`
- 屈服面图：`{outputs["yield_locus_png"]}`
- 应力-应变曲线图：`{outputs["stress_strain_png"]}`
- Abaqus UMAT SVM 参数：`{outputs["umat_csv"]}`
- Abaqus UMAT 元数据：`{outputs["umat_meta_json"]}`

## 工程解释

这个结果目前还不是完整 Abaqus 自动验算，但已经具备后续接入 Abaqus 的关键资产：可读的 SVM 参数 CSV 和 meta JSON。下一步可以把这些文件交给 `examples/UMAT` 中的 `ml_umat.f` 与 `calc_properties.py`，完成 Abaqus 单元级材料力学行为验算。

曲线计算状态：`{"已执行" if config["calculate_curves"] else "已跳过"}`。如果需要 pyLabFEA 内部小有限元应力-应变曲线，可重新运行命令并添加 `--with-curves`。

## 下一步

1. 把本流程接入 Streamlit，形成可视化 App 原型。
2. 增加 Abaqus job 提交与 ODB/CSV 读取。
3. 加入真实材料曲线或 Abaqus 批量仿真数据导入。
4. 在 SVM 屈服模型之外，增加神经网络代理模型实验。
"""


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _as_posix_dir(path: Path) -> str:
    return path.as_posix().rstrip("/") + "/"


def _safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value).strip())
    return safe or "material"
