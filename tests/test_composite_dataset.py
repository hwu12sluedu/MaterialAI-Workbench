import csv
import json

from material_ai_workbench.composite_dataset import (
    CompositeBatchConfig,
    composite_surrogate_comparison_rows,
    create_composite_batch_plan,
    run_composite_batch_plan,
    train_composite_surrogate,
)


def test_composite_batch_and_surrogate_pipeline(tmp_path):
    plan = create_composite_batch_plan(
        CompositeBatchConfig(
            name="unit_batch",
            output_dir=tmp_path / "batches",
            sample_count=3,
            vf_min=0.35,
            vf_max=0.45,
            hole_radius_min=1.0,
            hole_radius_max=2.0,
            width=16.0,
            length=40.0,
            micro_fiber_count=3,
            micro_nx=2,
            micro_ny=8,
            micro_nz=8,
        )
    )
    assert plan.plan_path.exists()
    assert len(plan.data["samples"]) == 3

    plan = run_composite_batch_plan(plan.plan_dir, max_samples=3)
    assert plan.dataset_csv.exists()
    with plan.dataset_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert "max_stress_near_hole_estimate_mpa" in rows[0]
    assert "micro_rve_interface_elements" in rows[0]

    surrogate = train_composite_surrogate(
        plan.dataset_csv,
        target_column="max_stress_near_hole_estimate_mpa",
        output_root=tmp_path / "surrogates",
    )
    assert surrogate.model_path.exists()
    assert surrogate.predictions_csv.exists()
    assert surrogate.metrics["sample_count"] == 3


def test_composite_surrogate_comparison_rows_filters_and_sorts(tmp_path):
    dataset_csv = tmp_path / "dataset.csv"
    dataset_csv.write_text("a,target\n1,2\n", encoding="utf-8")
    run_a = tmp_path / "surrogates" / "rf"
    run_b = tmp_path / "surrogates" / "mlp"
    for run_dir, model_kind, rmse in [(run_a, "random_forest", 5.0), (run_b, "mlp", 2.0)]:
        run_dir.mkdir(parents=True)
        (run_dir / "composite_surrogate_metrics.json").write_text(
            json.dumps(
                {
                    "dataset_csv": str(dataset_csv),
                    "target_column": "target",
                    "model_kind": model_kind,
                    "sample_count": 8,
                    "evaluation_mode": "holdout",
                    "mae": rmse / 2,
                    "rmse": rmse,
                    "r2": 0.7,
                    "uncertainty": "ensemble",
                    "prediction_interval_mean_half_width": 1.2,
                }
            ),
            encoding="utf-8",
        )

    rows = composite_surrogate_comparison_rows([run_a, run_b], dataset_csv=dataset_csv, target_column="target")

    assert [row["model_kind"] for row in rows] == ["mlp", "random_forest"]
    assert rows[0]["prediction_interval_mean_half_width"] == 1.2
