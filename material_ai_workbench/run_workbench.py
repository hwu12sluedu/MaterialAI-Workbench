"""Command line entry point for the MaterialAI Workbench prototype."""

from __future__ import annotations

import argparse
from pathlib import Path

from material_ai_workbench import WorkbenchConfig, run_material_workbench


def main() -> None:
    args = _parse_args()
    config = WorkbenchConfig(
        material_type=args.material,
        name=args.name,
        output_dir=args.output_dir,
        youngs_modulus=args.E,
        poisson_ratio=args.nu,
        yield_strength=args.sy,
        hill_ratios=tuple(args.hill_ratios),
        barlat_alphas=tuple(args.barlat_alphas),
        barlat_exponent=args.barlat_exponent,
        hyperelastic_c10=args.hyperelastic_C10,
        hyperelastic_c01=args.hyperelastic_C01,
        hyperelastic_d1=args.hyperelastic_D1,
        c_value=args.C,
        gamma=args.gamma,
        n_load_cases=args.n_load_cases,
        n_sequence=args.n_sequence,
        elastic_floor=args.elastic_floor,
        elastic_ceiling=args.elastic_ceiling,
        strain_max=args.strain_max,
        min_step=args.min_step,
        calculate_curves=args.with_curves,
        test_size=args.test_size,
        test_stress_scale=args.test_stress_scale,
        test_stress_offset=args.test_stress_offset,
        plot_mesh=args.plot_mesh,
        random_seed=args.seed,
    )
    result = run_material_workbench(config)

    print("\nMaterialAI Workbench run finished.")
    print(f"Run folder: {result.run_dir}")
    print(f"Report: {result.report_path}")
    print(f"Summary: {result.summary_path}")
    print(f"Support vectors: {result.support_vectors}")
    print(
        "Metrics: "
        + ", ".join(f"{name}={value:.5g}" for name, value in result.metrics.items())
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a small pyLabFEA-based ML material model and export report assets."
    )
    parser.add_argument("--material", choices=("j2", "hill", "barlat", "neo_hookean", "mooney_rivlin"), default="j2")
    parser.add_argument("--name", default=None, help="ML material name used in output files.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Root folder for generated runs. Defaults to MATERIALAI_RUNS_ROOT or the package runs folder.",
    )
    parser.add_argument("--E", type=float, default=200_000.0, help="Young's modulus in MPa.")
    parser.add_argument("--nu", type=float, default=0.3, help="Poisson ratio.")
    parser.add_argument("--sy", type=float, default=60.0, help="Yield strength in MPa.")
    parser.add_argument(
        "--hill-ratios",
        type=float,
        nargs=6,
        default=(1.2, 1.0, 0.8, 1.0, 1.0, 1.0),
        metavar=("R1", "R2", "R3", "R4", "R5", "R6"),
        help="Six yield stress ratios for Hill material.",
    )
    parser.add_argument(
        "--barlat-exponent",
        type=float,
        default=8.0,
        help="Barlat exponent, typically 8 for FCC aluminum and 6 for BCC steel.",
    )
    parser.add_argument(
        "--barlat-alphas",
        type=float,
        nargs=8,
        default=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        metavar=("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"),
        help="Eight Yld2000-2D-style anisotropy alpha coefficients.",
    )
    parser.add_argument("--hyperelastic-C10", type=float, default=None, help="Neo-Hookean/Mooney-Rivlin C10 in MPa.")
    parser.add_argument("--hyperelastic-C01", type=float, default=None, help="Mooney-Rivlin C01 in MPa.")
    parser.add_argument("--hyperelastic-D1", type=float, default=None, help="Abaqus hyperelastic D1 compressibility parameter.")
    parser.add_argument("--C", type=float, default=1.0, help="SVC C parameter.")
    parser.add_argument("--gamma", type=float, default=1.0, help="SVC gamma parameter.")
    parser.add_argument("--n-load-cases", type=int, default=40)
    parser.add_argument("--n-sequence", type=int, default=4)
    parser.add_argument("--elastic-floor", type=float, default=0.1)
    parser.add_argument("--elastic-ceiling", type=float, default=0.95)
    parser.add_argument("--strain-max", type=float, default=0.01)
    parser.add_argument("--min-step", type=int, default=8)
    parser.add_argument(
        "--with-curves",
        action="store_true",
        help="Also run pyLabFEA small FE stress-strain curve calculations.",
    )
    parser.add_argument("--test-size", type=int, default=80)
    parser.add_argument("--test-stress-scale", type=float, default=0.15)
    parser.add_argument("--test-stress-offset", type=float, default=0.08)
    parser.add_argument("--plot-mesh", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    main()
