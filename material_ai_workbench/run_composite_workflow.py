"""Command-line entry point for the composite 3D plate-with-hole workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from material_ai_workbench.config import COMPOSITE_ROOT
from material_ai_workbench.composite_workflow import CompositePlateConfig, run_composite_plate_workflow


def main() -> None:
    args = _parse_args()
    result = run_composite_plate_workflow(
        CompositePlateConfig(
            name=args.name,
            output_dir=Path(args.output_dir) if args.output_dir else COMPOSITE_ROOT,
            fiber_volume_fraction=args.vf,
            fiber_e=args.fiber_e,
            fiber_nu=args.fiber_nu,
            matrix_e=args.matrix_e,
            matrix_nu=args.matrix_nu,
            interface_efficiency=args.interface_efficiency,
            interface_thickness_ratio=args.interface_thickness_ratio,
            length=args.length,
            width=args.width,
            thickness=args.thickness,
            hole_radius=args.hole_radius,
            applied_strain=args.applied_strain,
            mesh_size=args.mesh_size,
            n_preview_fibers=args.n_preview_fibers,
            micro_fiber_count=args.micro_fiber_count,
            micro_nx=args.micro_nx,
            micro_ny=args.micro_ny,
            micro_nz=args.micro_nz,
            micro_load_strain=args.micro_load_strain,
            random_seed=args.random_seed,
            cpus=args.cpus,
            run_abaqus=args.run_abaqus,
            submit_job=args.submit_job,
        )
    )
    print(f"Composite workflow generated: {result.run_dir}")
    print(f"Report: {result.report_path}")
    print(f"Abaqus script: {result.abaqus_script_path}")
    print(f"Abaqus status: {result.abaqus_status}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="ud_composite_plate_hole")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--vf", type=float, default=0.55)
    parser.add_argument("--fiber-e", type=float, default=230_000.0)
    parser.add_argument("--fiber-nu", type=float, default=0.20)
    parser.add_argument("--matrix-e", type=float, default=3_500.0)
    parser.add_argument("--matrix-nu", type=float, default=0.35)
    parser.add_argument("--interface-efficiency", type=float, default=0.92)
    parser.add_argument("--interface-thickness-ratio", type=float, default=0.18)
    parser.add_argument("--length", type=float, default=120.0)
    parser.add_argument("--width", type=float, default=40.0)
    parser.add_argument("--thickness", type=float, default=2.0)
    parser.add_argument("--hole-radius", type=float, default=5.0)
    parser.add_argument("--applied-strain", type=float, default=0.003)
    parser.add_argument("--mesh-size", type=float, default=2.0)
    parser.add_argument("--n-preview-fibers", type=int, default=80)
    parser.add_argument("--micro-fiber-count", type=int, default=16)
    parser.add_argument("--micro-nx", type=int, default=8)
    parser.add_argument("--micro-ny", type=int, default=18)
    parser.add_argument("--micro-nz", type=int, default=18)
    parser.add_argument("--micro-load-strain", type=float, default=0.001)
    parser.add_argument("--random-seed", type=int, default=7)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--run-abaqus", action="store_true")
    parser.add_argument("--submit-job", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
