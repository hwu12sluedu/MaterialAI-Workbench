"""Command-line tools for composite RVE batch data and surrogate training."""

from __future__ import annotations

import argparse
from pathlib import Path

from material_ai_workbench.composite_dataset import (
    COMPOSITE_BATCH_ROOT,
    CompositeBatchConfig,
    create_composite_batch_plan,
    run_composite_batch_plan,
    train_composite_surrogate,
)


def main() -> None:
    args = _parse_args()
    if args.action == "create":
        plan = create_composite_batch_plan(
            CompositeBatchConfig(
                name=args.name,
                output_dir=Path(args.output_dir) if args.output_dir else COMPOSITE_BATCH_ROOT,
                sample_count=args.sample_count,
                random_seed=args.random_seed,
                vf_min=args.vf_min,
                vf_max=args.vf_max,
                interface_efficiency_min=args.interface_efficiency_min,
                interface_efficiency_max=args.interface_efficiency_max,
                hole_radius_min=args.hole_radius_min,
                hole_radius_max=args.hole_radius_max,
                micro_fiber_count=args.micro_fiber_count,
                micro_nx=args.micro_nx,
                micro_ny=args.micro_ny,
                micro_nz=args.micro_nz,
                run_abaqus=args.run_abaqus,
                run_pbc_homogenization=args.run_pbc_homogenization,
                use_abaqus_homogenization=args.use_abaqus_homogenization,
            )
        )
        print(f"Composite batch plan: {plan.plan_dir}")
        return
    if args.action == "run":
        plan = run_composite_batch_plan(args.plan_dir, max_samples=args.max_samples)
        print(f"Composite batch updated: {plan.plan_dir}")
        print(f"Dataset: {plan.dataset_csv}")
        return
    if args.action == "train":
        run = train_composite_surrogate(
            args.dataset_csv,
            target_column=args.target,
            model_kind=args.model_kind,
            uncertainty=args.uncertainty,
        )
        print(f"Composite surrogate: {run.run_dir}")
        print(f"Metrics: {run.metrics_path}")
        return
    raise ValueError(f"Unknown action: {args.action}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="create a composite batch plan")
    create.add_argument("--name", default="composite_rve_sweep")
    create.add_argument("--output-dir", default=None)
    create.add_argument("--sample-count", type=int, default=8)
    create.add_argument("--random-seed", type=int, default=23)
    create.add_argument("--vf-min", type=float, default=0.35)
    create.add_argument("--vf-max", type=float, default=0.65)
    create.add_argument("--interface-efficiency-min", type=float, default=0.75)
    create.add_argument("--interface-efficiency-max", type=float, default=1.0)
    create.add_argument("--hole-radius-min", type=float, default=3.0)
    create.add_argument("--hole-radius-max", type=float, default=7.0)
    create.add_argument("--micro-fiber-count", type=int, default=12)
    create.add_argument("--micro-nx", type=int, default=4)
    create.add_argument("--micro-ny", type=int, default=12)
    create.add_argument("--micro-nz", type=int, default=12)
    create.add_argument("--run-abaqus", action="store_true", help="submit each macro plate Abaqus job while running samples")
    create.add_argument("--run-pbc-homogenization", action="store_true", help="run six micro RVE Abaqus homogenization jobs per sample")
    create.add_argument("--use-abaqus-homogenization", action="store_true", help="replace estimated UD properties with Abaqus-homogenized RVE properties")

    run = subparsers.add_parser("run", help="run pending samples from a composite batch plan")
    run.add_argument("plan_dir")
    run.add_argument("--max-samples", type=int, default=None)

    train = subparsers.add_parser("train", help="train a surrogate from composite_dataset.csv")
    train.add_argument("dataset_csv")
    train.add_argument("--target", default="max_stress_near_hole_estimate_mpa")
    train.add_argument("--model-kind", choices=["random_forest", "mlp"], default="random_forest")
    train.add_argument("--uncertainty", choices=["none", "ensemble"], default="ensemble")
    return parser.parse_args()


if __name__ == "__main__":
    main()
