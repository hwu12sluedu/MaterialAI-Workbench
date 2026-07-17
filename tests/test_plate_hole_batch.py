from __future__ import annotations

from types import SimpleNamespace

import pytest

import material_ai_workbench.plate_hole_batch as batch
from material_ai_workbench.plate_hole_batch import (
    PlateHoleBatchConfig,
    create_plate_hole_batch_plan,
    load_plate_hole_batch_plan,
    run_plate_hole_batch_plan,
)


def _config(tmp_path) -> PlateHoleBatchConfig:
    return PlateHoleBatchConfig(
        name="unit_batch",
        output_root=tmp_path / "batches",
        cases_root=tmp_path / "cases",
        hole_radii=(4.0, 5.0),
        yield_strengths=(250.0, 300.0),
        displacements=(0.2, 0.3),
    )


def test_create_plate_hole_batch_builds_cartesian_persistent_plan(tmp_path) -> None:
    plan = create_plate_hole_batch_plan(_config(tmp_path))
    loaded = load_plate_hole_batch_plan(plan.plan_dir)

    assert len(loaded.samples) == 8
    assert len({sample["sample_id"] for sample in loaded.samples}) == 8
    assert all(sample["status"] == "pending" for sample in loaded.samples)
    assert loaded.plan_path.exists()
    assert loaded.summary_csv.exists()
    assert loaded.report_path.exists()


def test_batch_prepare_is_resumable_and_does_not_submit(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(config, *, execute=False, run_dir=None):
        calls.append((config, execute))
        target = tmp_path / "acceptance" / config.name
        target.mkdir(parents=True)
        return SimpleNamespace(
            run_dir=target,
            status="prepared",
            manifest={"status": "prepared", "results": {}, "stages": {}},
        )

    monkeypatch.setattr(batch, "run_plate_hole_acceptance", fake_run)
    plan = create_plate_hole_batch_plan(_config(tmp_path))

    prepared = run_plate_hole_batch_plan(plan.plan_dir, max_samples=2)

    assert [sample["status"] for sample in prepared.samples[:2]] == [
        "prepared",
        "prepared",
    ]
    assert all(sample["status"] == "pending" for sample in prepared.samples[2:])
    assert len(calls) == 2
    assert all(execute is False for _, execute in calls)
    assert all(config.submit_job is False for config, _ in calls)


def test_batch_rejects_submission_without_execute(tmp_path) -> None:
    plan = create_plate_hole_batch_plan(_config(tmp_path))

    with pytest.raises(ValueError, match="requires execute"):
        run_plate_hole_batch_plan(plan.plan_dir, submit_jobs=True)
