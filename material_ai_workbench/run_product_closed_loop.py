"""Product-level smoke closed loop for MaterialAI Workbench.

The default path is intentionally light: it generates a micro RVE, six PBC
load-case input files, a 3D plate-with-hole Abaqus build script, a dataset row,
and a product summary without submitting Abaqus. Add --run-abaqus and
--submit-job when Abaqus is available and the user explicitly wants a solve.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.composite_workflow import (
    CompositePlateConfig,
    load_composite_manifest,
    run_composite_plate_workflow,
)
from material_ai_workbench.config import COMPOSITE_ROOT


def run_product_closed_loop(config: CompositePlateConfig) -> dict[str, Any]:
    result = run_composite_plate_workflow(config)
    manifest = load_composite_manifest(result.run_dir)
    metrics = manifest.get("microstructure_metrics", {})
    paths = manifest.get("paths", {})
    pbc_summary = manifest.get("pbc_homogenization", {})
    target_vf = float(config.fiber_volume_fraction)
    actual_vf = _safe_float(metrics.get("actual_vf"), target_vf)
    vf_error = actual_vf - target_vf

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workflow": "product_closed_loop_smoke",
        "config": _json_ready(asdict(config)),
        "run_dir": str(result.run_dir),
        "capability_status": {
            "micro_rve": "completed" if result.micro_rve_inp_path.exists() else "missing",
            "pbc_job_files": "completed" if len(list(result.micro_pbc_job_dir.glob("micro_rve_pbc_*.inp"))) == 6 else "incomplete",
            "pbc_homogenization": pbc_summary.get("status", "not_requested"),
            "plate_model": "completed" if result.abaqus_script_path.exists() else "missing",
            "abaqus_plate_solve": result.abaqus_status,
            "dataset_row": "completed" if result.dataset_csv.exists() else "missing",
            "engineering_report": "completed" if result.report_path.exists() else "missing",
        },
        "acceptance": {
            "target_vf": target_vf,
            "actual_vf": actual_vf,
            "target_vf_error": vf_error,
            "vf_within_3_percent": abs(vf_error) <= 0.03,
            "pbc_job_count": len(paths.get("micro_pbc_jobs", [])) if isinstance(paths.get("micro_pbc_jobs"), list) else 0,
        },
        "effective_properties": result.effective_properties,
        "engineering_estimates": result.engineering_estimates,
        "paths": {
            "manifest": str(result.manifest_path),
            "report": str(result.report_path),
            "micro_rve_inp": str(result.micro_rve_inp_path),
            "micro_phase_map": str(result.micro_phase_map_path),
            "micro_pbc_job_dir": str(result.micro_pbc_job_dir),
            "abaqus_script": str(result.abaqus_script_path),
            "run_script": str(result.run_script_path),
            "dataset_csv": str(result.dataset_csv),
        },
    }

    summary_path = result.run_dir / "product_closed_loop_summary.json"
    report_path = result.run_dir / "product_closed_loop_report.md"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report_path.write_text(_product_report(summary), encoding="utf-8")
    summary["paths"]["product_summary"] = str(summary_path)
    summary["paths"]["product_report"] = str(report_path)
    return summary


def main() -> int:
    args = _parse_args()
    config = _config_from_args(args)
    summary = run_product_closed_loop(config)

    print("=" * 72)
    print("MATERIALAI PRODUCT CLOSED LOOP")
    print("=" * 72)
    print(f"Run dir: {summary['run_dir']}")
    print(f"Actual Vf: {summary['acceptance']['actual_vf']}")
    print(f"Vf within +/-3%: {summary['acceptance']['vf_within_3_percent']}")
    print(f"PBC job files: {summary['acceptance']['pbc_job_count']}")
    print(f"Abaqus plate solve: {summary['capability_status']['abaqus_plate_solve']}")
    print(f"Report: {summary['paths']['product_report']}")
    print("=" * 72)
    return 0 if summary["acceptance"]["vf_within_3_percent"] else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="product_smoke_composite_plate_hole")
    parser.add_argument("--output-dir", type=Path, default=COMPOSITE_ROOT)
    parser.add_argument("--vf", type=float, default=0.55)
    parser.add_argument("--fiber-e", type=float, default=230_000.0)
    parser.add_argument("--fiber-nu", type=float, default=0.20)
    parser.add_argument("--matrix-e", type=float, default=3_500.0)
    parser.add_argument("--matrix-nu", type=float, default=0.35)
    parser.add_argument("--interface-efficiency", type=float, default=0.92)
    parser.add_argument("--length", type=float, default=120.0)
    parser.add_argument("--width", type=float, default=40.0)
    parser.add_argument("--thickness", type=float, default=2.0)
    parser.add_argument("--hole-radius", type=float, default=5.0)
    parser.add_argument("--applied-strain", type=float, default=0.003)
    parser.add_argument("--micro-fiber-count", type=int, default=16)
    parser.add_argument("--micro-nx", type=int, default=8)
    parser.add_argument("--micro-ny", type=int, default=18)
    parser.add_argument("--micro-nz", type=int, default=18)
    parser.add_argument("--fiber-theta", type=float, default=0.0)
    parser.add_argument("--fiber-phi", type=float, default=0.0)
    parser.add_argument("--fiber-spread", type=float, default=8.0)
    parser.add_argument("--fiber-length", type=float, default=1.2)
    parser.add_argument("--fiber-length-std", type=float, default=0.08)
    parser.add_argument("--fiber-diameter", type=float, default=None)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--run-pbc-homogenization", action="store_true")
    parser.add_argument("--use-abaqus-homogenization", action="store_true")
    parser.add_argument("--run-abaqus", action="store_true")
    parser.add_argument("--submit-job", action="store_true")
    return parser.parse_args()


def _config_from_args(args: argparse.Namespace) -> CompositePlateConfig:
    return CompositePlateConfig(
        name=args.name,
        output_dir=args.output_dir,
        fiber_volume_fraction=args.vf,
        fiber_e=args.fiber_e,
        fiber_nu=args.fiber_nu,
        matrix_e=args.matrix_e,
        matrix_nu=args.matrix_nu,
        interface_efficiency=args.interface_efficiency,
        length=args.length,
        width=args.width,
        thickness=args.thickness,
        hole_radius=args.hole_radius,
        applied_strain=args.applied_strain,
        micro_fiber_count=args.micro_fiber_count,
        micro_nx=args.micro_nx,
        micro_ny=args.micro_ny,
        micro_nz=args.micro_nz,
        fiber_orientation_theta_deg=args.fiber_theta,
        fiber_orientation_phi_deg=args.fiber_phi,
        fiber_orientation_spread_deg=args.fiber_spread,
        fiber_length_normalized=args.fiber_length,
        fiber_length_std=args.fiber_length_std,
        fiber_diameter_normalized=args.fiber_diameter,
        random_seed=args.seed,
        run_pbc_homogenization=args.run_pbc_homogenization,
        use_abaqus_homogenization=args.use_abaqus_homogenization,
        run_abaqus=args.run_abaqus,
        submit_job=args.submit_job,
    )


def _product_report(summary: dict[str, Any]) -> str:
    status = summary["capability_status"]
    acceptance = summary["acceptance"]
    props = summary["effective_properties"]
    estimates = summary["engineering_estimates"]
    paths = summary["paths"]
    return f"""# MaterialAI Product Closed Loop Smoke Report

## Acceptance

- Target Vf: `{acceptance.get('target_vf')}`
- Actual voxel Vf: `{acceptance.get('actual_vf')}`
- Vf error: `{acceptance.get('target_vf_error')}`
- Vf within +/-3%: `{acceptance.get('vf_within_3_percent')}`
- PBC job files: `{acceptance.get('pbc_job_count')}`

## Capability Status

| Stage | Status |
|---|---|
| Micro RVE generation | `{status.get('micro_rve')}` |
| Six PBC job files | `{status.get('pbc_job_files')}` |
| PBC homogenization solve | `{status.get('pbc_homogenization')}` |
| 3D plate model script | `{status.get('plate_model')}` |
| Abaqus plate solve | `{status.get('abaqus_plate_solve')}` |
| Dataset row | `{status.get('dataset_row')}` |
| Engineering report | `{status.get('engineering_report')}` |

## Effective Properties

- E1: `{props.get('E1')}` MPa
- E2: `{props.get('E2')}` MPa
- G12: `{props.get('G12')}` MPa

## Plate Estimate

- Nominal axial stress: `{estimates.get('nominal_axial_stress_mpa')}` MPa
- Estimated max stress near hole: `{estimates.get('max_stress_near_hole_estimate_mpa')}` MPa
- Right edge displacement: `{estimates.get('right_edge_displacement')}` mm

## Key Files

- Manifest: `{paths.get('manifest')}`
- Composite report: `{paths.get('report')}`
- Micro RVE INP: `{paths.get('micro_rve_inp')}`
- PBC job folder: `{paths.get('micro_pbc_job_dir')}`
- Abaqus script: `{paths.get('abaqus_script')}`
- Dataset row: `{paths.get('dataset_csv')}`

This smoke path is the publishable no-Abaqus demo. It proves the product can
prepare traceable micro-to-macro assets. Add `--run-abaqus --submit-job` only
when Abaqus is available and the solve is intentionally requested.
"""


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


if __name__ == "__main__":
    raise SystemExit(main())
