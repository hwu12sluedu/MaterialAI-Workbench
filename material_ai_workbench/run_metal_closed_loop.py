"""CLI closed loop for metal plasticity batches.

Example:
  conda run -n pylabfea python -m material_ai_workbench.run_metal_closed_loop
  conda run -n pylabfea python -m material_ai_workbench.run_metal_closed_loop --run-abaqus --postprocess-odb
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from material_ai_workbench.batch_simulation import (
    BATCH_ROOT,
    batch_sample_table_rows,
    create_parameter_sweep_plan,
    run_batch_plan,
    save_batch_plan,
)
from material_ai_workbench.closed_loop_report import generate_closed_loop_report
from material_ai_workbench.surrogate_model import train_surrogate_from_dataset


def main() -> int:
    args = _parse_args()
    strengths = _parse_strengths(args.yield_strengths)
    export_or_train = bool(args.export_dataset or args.train_surrogate)
    archive_cases = bool(args.archive_cases or export_or_train or args.postprocess_odb)
    surrogate_target = args.surrogate_target or ("latest_odb_max_mises" if args.run_abaqus else "yield_strength")

    print("=" * 72)
    print("METAL PLASTICITY CLOSED LOOP")
    print("=" * 72)
    print(f"Material: {args.material_type}")
    print(f"Yield sweep: {strengths}")
    print(f"Abaqus enabled: {args.run_abaqus}")

    plan = create_parameter_sweep_plan(
        name=args.name,
        material_type=args.material_type,
        yield_strengths=strengths,
        youngs_modulus=args.youngs_modulus,
        poisson_ratio=args.poisson_ratio,
        n_load_cases=args.n_load_cases,
        n_sequence=args.n_sequence,
        test_size=args.test_size,
        max_abaqus_load_cases=args.max_abaqus_load_cases,
        output_root=args.output_root,
    )
    print(f"\nPlan: {plan.plan_dir}")

    plan = run_batch_plan(
        plan.plan_dir,
        run_abaqus=args.run_abaqus,
        archive_cases=archive_cases,
        postprocess_odb=args.postprocess_odb,
        export_dataset_after=export_or_train,
        train_surrogate_after=False,
        max_samples=args.max_samples,
        timeout_seconds=args.timeout_seconds,
    )
    print("\nSamples:")
    for row in batch_sample_table_rows(plan):
        print(
            "  {sample}: {status}, sy={sy}, Abaqus={abaqus}, MaxMises={mises}".format(
                sample=row.get("sample_id"),
                status=row.get("status"),
                sy=row.get("sy"),
                abaqus=row.get("Abaqus"),
                mises=row.get("Max Mises"),
            )
        )

    surrogate_run = None
    dataset_dir = plan.data.get("outputs", {}).get("dataset_dir")
    if args.train_surrogate:
        if not dataset_dir:
            print("\nSurrogate: skipped, no dataset directory was exported.")
        else:
            print(f"\nTraining surrogate target: {surrogate_target}")
            surrogate = train_surrogate_from_dataset(
                dataset_dir,
                target_column=surrogate_target,
                model_kind=args.surrogate_model,
                uncertainty=args.uncertainty,
            )
            surrogate_run = surrogate.run_dir
            plan.data.setdefault("outputs", {})["surrogate_run"] = str(surrogate.run_dir)
            save_batch_plan(plan)
            print(f"Surrogate: {surrogate.run_dir}")
            print(
                "Metrics: MAE={mae}, RMSE={rmse}, R2={r2}".format(
                    mae=_fmt(surrogate.metrics.get("mae")),
                    rmse=_fmt(surrogate.metrics.get("rmse")),
                    r2=_fmt(surrogate.metrics.get("r2")),
                )
            )

    report = None
    if args.closed_loop_report:
        report = generate_closed_loop_report(batch_plan=plan.plan_dir)
        print(f"\nClosed-loop report: {report.report_path}")

    print("\nOutputs:")
    print(f"  Batch plan: {plan.plan_path}")
    print(f"  Summary CSV: {plan.summary_csv}")
    if dataset_dir:
        print(f"  Dataset: {dataset_dir}")
    if surrogate_run:
        print(f"  Surrogate: {surrogate_run}")
    if report:
        print(f"  Report: {report.report_path}")
    print("=" * 72)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="metal_j2_closed_loop")
    parser.add_argument("--material-type", choices=["j2", "hill", "barlat"], default="j2")
    parser.add_argument("--yield-strengths", default="50,60,70,80,90")
    parser.add_argument("--youngs-modulus", type=float, default=200_000.0)
    parser.add_argument("--poisson-ratio", type=float, default=0.3)
    parser.add_argument("--n-load-cases", type=int, default=32)
    parser.add_argument("--n-sequence", type=int, default=3)
    parser.add_argument("--test-size", type=int, default=60)
    parser.add_argument("--max-abaqus-load-cases", type=int, default=1)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--output-root", type=Path, default=BATCH_ROOT)
    parser.add_argument("--run-abaqus", action="store_true")
    parser.add_argument("--archive-cases", action="store_true")
    parser.add_argument("--postprocess-odb", action="store_true")
    parser.add_argument("--export-dataset", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--train-surrogate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--surrogate-target", default=None)
    parser.add_argument("--surrogate-model", choices=["random_forest", "mlp"], default="random_forest")
    parser.add_argument("--uncertainty", choices=["none", "ensemble"], default="ensemble")
    parser.add_argument("--closed-loop-report", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def _parse_strengths(value: str) -> list[float]:
    strengths = [float(item.strip()) for item in str(value).replace(";", ",").split(",") if item.strip()]
    if not strengths:
        raise ValueError("yield-strengths must contain at least one number.")
    return strengths


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.4g}"
    except (TypeError, ValueError):
        return "N/A"


if __name__ == "__main__":
    raise SystemExit(main())
