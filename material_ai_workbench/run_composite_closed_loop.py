r"""Run one composite micro-to-Abaqus closed-loop acceptance case.

PowerShell:
  $env:PYTHONPATH = "src;."
  conda run -n pylabfea python -m material_ai_workbench.run_composite_closed_loop
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from material_ai_workbench.case_library import append_odb_extraction, scan_case_folder
from material_ai_workbench.composite_dataset import COMPOSITE_BATCH_ROOT, train_composite_surrogate
from material_ai_workbench.composite_workflow import CompositePlateConfig, run_composite_plate_workflow
from material_ai_workbench.odb_postprocess import run_case_odb_extraction


def main() -> int:
    print("=" * 72)
    print("COMPOSITE ABAQUS PIPELINE: RVE + plate solve + postprocess")
    print("=" * 72)

    config = CompositePlateConfig(
        name="comp_full_demo",
        fiber_volume_fraction=0.55,
        fiber_e=230_000.0,
        fiber_nu=0.20,
        matrix_e=3_500.0,
        matrix_nu=0.35,
        interface_efficiency=0.92,
        micro_fiber_count=9,
        micro_nx=4,
        micro_ny=8,
        micro_nz=8,
        length=120.0,
        width=40.0,
        thickness=2.0,
        hole_radius=5.0,
        mesh_size=2.0,
        run_abaqus=True,
        submit_job=True,
        random_seed=42,
    )

    print("\n--- Stage 1: RVE + Abaqus plate solve ---")
    started = time.time()
    result = run_composite_plate_workflow(config)
    elapsed = time.time() - started
    print(f"  Duration: {elapsed:.0f}s")
    print(f"  Abaqus status: {result.abaqus_status}")
    print(f"  Run dir: {result.run_dir}")
    print(
        "  Effective properties: "
        f"E1={result.effective_properties['E1']:.0f} MPa, "
        f"E2={result.effective_properties['E2']:.0f} MPa, "
        f"G12={result.effective_properties['G12']:.0f} MPa"
    )
    if result.abaqus_status != "abaqus_completed":
        print("  Stage 1: FAILED. Check abaqus_stdout.log and abaqus_stderr.log in the run directory.")
        return 1
    print("  Stage 1: PASS")

    print("\n--- Stage 2: ODB post-processing ---")
    odb_path = _find_first_odb(result.run_dir)
    if odb_path is None:
        print("  Stage 2: FAILED. No ODB file was produced.")
        return 1
    print(f"  ODB: {odb_path}")

    post = subprocess.run(
        [str(config.smapython), str(result.postprocess_script_path)],
        cwd=result.run_dir / "abaqus",
        capture_output=True,
        text=True,
        timeout=180,
    )
    if post.returncode != 0:
        print(f"  Stage 2: FAILED. {post.stderr[-1000:]}")
        return 1

    plate_json = result.run_dir / "abaqus" / "plate_results.json"
    plate: dict[str, Any] = {}
    if plate_json.exists():
        plate = json.loads(plate_json.read_text(encoding="utf-8"))
        print(f"  Max Mises: {plate.get('max_mises_mpa', 'N/A')} MPa")
        print(f"  Max U: {plate.get('max_displacement', 'N/A')} mm")
        print(f"  Sum RF1: {plate.get('sum_rf1', 'N/A')} N")
        print("  Stage 2: PASS")
    else:
        print("  Stage 2: FAILED. Postprocess ran but plate_results.json was not created.")
        return 1

    print("\n--- Stage 3: Case library archive ---")
    case = scan_case_folder(
        result.run_dir / "abaqus",
        title="comp_full_demo_plate_hole",
        tags=["composite", "plate_hole", "micro_rve", "abaqus"],
        description="Composite micro RVE generated properties mapped into a 3D Abaqus plate-with-hole tension model.",
        status="success",
        parameters={
            "fiber_volume_fraction": config.fiber_volume_fraction,
            "fiber_e": config.fiber_e,
            "matrix_e": config.matrix_e,
            "hole_radius": config.hole_radius,
            "E1": result.effective_properties["E1"],
            "E2": result.effective_properties["E2"],
            "max_mises_mpa": plate.get("max_mises_mpa"),
        },
    )
    print(f"  Case ID: {case.case_id}")
    print(f"  Files indexed: {len(case.files)}")
    print("  Stage 3: PASS")

    print("\n--- Stage 4: ODB deep feature extraction ---")
    extraction = run_case_odb_extraction(
        case,
        odb_path,
        fields=["S", "U", "RF"],
        backend="abaqus_python",
        capture_contour=False,
    )
    append_odb_extraction(case, extraction)
    agg = extraction.get("aggregate", {})
    print(f"  Max Mises: {agg.get('max_mises', 'N/A')} MPa")
    print(f"  Max U: {agg.get('max_displacement', 'N/A')} mm")
    print("  Stage 4: PASS")

    print("\n--- Stage 5: Dataset row check ---")
    row_csv = result.dataset_csv
    if not row_csv.exists():
        print("  Stage 5: FAILED. Dataset row CSV was not created.")
        return 1
    with row_csv.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    print(
        "  Single row: "
        f"E1={row.get('E1', 'N/A')}, "
        f"estimate={row.get('max_stress_near_hole_estimate_mpa', 'N/A')}, "
        f"actual_mises={plate.get('max_mises_mpa', 'N/A')}"
    )
    print("  Stage 5: PASS")

    print("\n--- Stage 6: Composite surrogate on latest batch dataset ---")
    batch_ds = _latest_batch_dataset()
    if batch_ds is None:
        print("  Stage 6: SKIPPED. No composite batch dataset is available yet.")
    else:
        surrogate = train_composite_surrogate(
            batch_ds,
            target_column="max_stress_near_hole_estimate_mpa",
            model_kind="random_forest",
            uncertainty="ensemble",
        )
        metrics = surrogate.metrics
        print(f"  Dataset: {batch_ds}")
        print(
            "  Metrics: "
            f"MAE={_fmt(metrics.get('mae'))}, "
            f"RMSE={_fmt(metrics.get('rmse'))}, "
            f"R2={_fmt(metrics.get('r2'))}"
        )
        print("  Stage 6: PASS")

    print("\n" + "=" * 72)
    print("COMPOSITE ABAQUS PIPELINE COMPLETE")
    print(f"Run dir: {result.run_dir}")
    print("=" * 72)
    return 0


def _find_first_odb(run_dir: Path) -> Path | None:
    candidates = sorted(run_dir.glob("**/*.odb"), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _latest_batch_dataset() -> Path | None:
    if not COMPOSITE_BATCH_ROOT.exists():
        return None
    candidates = sorted(
        [path for path in COMPOSITE_BATCH_ROOT.glob("*/composite_dataset.csv") if path.exists()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.4g}"
    except (TypeError, ValueError):
        return "N/A"


if __name__ == "__main__":
    raise SystemExit(main())
