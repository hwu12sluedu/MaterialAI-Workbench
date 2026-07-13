from __future__ import annotations

import csv
import json
from types import SimpleNamespace

from material_ai_workbench.batch_simulation import (
    batch_sample_table_rows,
    create_parameter_sweep_plan,
    list_batch_plans,
    load_batch_plan,
    run_batch_plan,
)


def test_create_parameter_sweep_plan_writes_plan_report_and_summary(tmp_path) -> None:
    plan = create_parameter_sweep_plan(
        name="unit_batch",
        material_type="j2",
        yield_strengths=[50.0, 60.0],
        output_root=tmp_path / "batches",
    )

    assert plan.plan_path.exists()
    assert plan.report_path.exists()
    assert plan.summary_csv.exists()
    assert len(plan.samples) == 2
    assert len(plan.data["samples"]) == 2
    assert plan.data["samples"][0]["status"] == "pending"

    loaded = load_batch_plan(plan.plan_dir)
    assert loaded.data["name"] == "unit_batch"
    assert list_batch_plans(tmp_path / "batches") == [plan.plan_dir]

    with plan.summary_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["sample_id"].startswith("001_j2_sy50")


def test_run_batch_plan_material_only_updates_samples(tmp_path, monkeypatch) -> None:
    plan = create_parameter_sweep_plan(
        name="unit_run",
        material_type="j2",
        yield_strengths=[55.0, 65.0],
        output_root=tmp_path / "batches",
    )

    def fake_run_material_workbench(config):
        run_dir = config.output_dir / f"run_{config.name}"
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "config": {"material_type": config.material_type},
                    "ml_material": {"name": config.name, "support_vectors": 3},
                    "metrics": {"accuracy": 0.9},
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(run_dir=run_dir, metrics={"accuracy": 0.9}, support_vectors=3)

    monkeypatch.setattr("material_ai_workbench.batch_simulation.run_material_workbench", fake_run_material_workbench)

    completed = run_batch_plan(plan.plan_dir, run_abaqus=False)

    assert [sample["status"] for sample in completed.samples] == ["material_completed", "material_completed"]
    assert [sample["status"] for sample in completed.data["samples"]] == ["material_completed", "material_completed"]
    assert all(sample["run_dir"] for sample in completed.data["samples"])
    rows = batch_sample_table_rows(completed)
    assert rows[0]["status"] == "material_completed"
    assert rows[0]["Max Mises"] is None
    with completed.summary_csv.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[1]["status"] == "material_completed"
