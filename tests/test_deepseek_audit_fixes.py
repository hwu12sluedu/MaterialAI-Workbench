import json
from pathlib import Path

import numpy as np

from material_ai_workbench.case_library import CaseSummary, _try_float, find_similar_cases, load_case_summary
from material_ai_workbench.job_queue import JobQueue
from material_ai_workbench.multi_fidelity import train_multi_fidelity
from material_ai_workbench.time_series_surrogate import resample_curve


def _case(case_id: str, tmp_path: Path, nodes: int, mises: float) -> CaseSummary:
    case_dir = tmp_path / case_id
    case_dir.mkdir()
    return CaseSummary(
        case_id=case_id,
        title=case_id,
        description="",
        tags=["test"],
        status="success",
        source_folder=str(case_dir),
        created_at="2026-07-03T00:00:00",
        updated_at="2026-07-03T00:00:00",
        case_dir=str(case_dir),
        files=[],
        file_counts={"model": 1, "result": 1},
        inp_features={"summary": {"estimated_node_count": nodes, "estimated_element_count": nodes // 2}},
        result_features={"summary": {"csv_row_count": 10, "max_mises": mises, "max_peeq": 0.01}},
        parameters={"yield_strength": mises / 2, "youngs_modulus": 200000, "poisson_ratio": 0.3},
    )


def test_load_case_summary_ignores_unknown_fields(tmp_path):
    case = _case("case_a", tmp_path, 100, 60.0)
    payload = case.__dict__.copy()
    payload["files"] = []
    payload["future_field"] = "kept out"
    path = Path(case.case_dir) / "case_summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_case_summary(path)
    assert loaded.case_id == "case_a"
    assert not hasattr(loaded, "future_field")


def test_try_float_handles_us_and_european_decimal_formats():
    assert _try_float("1.234,56") == 1234.56
    assert _try_float("1,234.56") == 1234.56
    assert _try_float("1,234") == 1234.0


def test_find_similar_cases_returns_ranked_rows(tmp_path):
    query = _case("query", tmp_path, 100, 60.0)
    close = _case("close", tmp_path, 105, 62.0)
    far = _case("far", tmp_path, 500, 180.0)

    rows = find_similar_cases(query, cases=[query, far, close], top_k=2)
    assert [row["case_id"] for row in rows] == ["close", "far"]
    assert rows[0]["similarity"] > rows[1]["similarity"]


def test_job_queue_persists_submitted_jobs(tmp_path):
    queue_path = tmp_path / "queue.json"
    queue = JobQueue(queue_file=queue_path, abaqus_bat=tmp_path / "abaqus.bat")
    job = queue.submit("Plate Hole", tmp_path / "plate.inp", tmp_path, cpus=2)

    reloaded = JobQueue(queue_file=queue_path, abaqus_bat=tmp_path / "abaqus.bat")
    assert reloaded.status()["queued"] == 1
    assert reloaded.list_jobs()[0].job_id == job.job_id


def test_job_queue_history_log_and_retry(tmp_path):
    queue_path = tmp_path / "queue.json"
    history_path = tmp_path / "history.json"
    inp = tmp_path / "plate.inp"
    inp.write_text("*Heading\n", encoding="utf-8")
    abaqus_bat = tmp_path / "abaqus.bat"
    abaqus_bat.write_text("@echo off\necho simulated failure\nexit /b 2\n", encoding="utf-8")

    queue = JobQueue(queue_file=queue_path, history_file=history_path, abaqus_bat=abaqus_bat)
    job = queue.submit("bad job", inp, tmp_path, cpus=1)
    assert queue.process_next(timeout_seconds=10) is True

    failed = queue.list_jobs()[0]
    assert failed.status == "failed"
    assert "simulated failure" in queue.log_text(job.job_id)
    assert queue.history()[0]["status"] == "failed"
    assert queue.statistics()["history_failed"] == 1

    retried = queue.retry(job.job_id)
    assert retried.retry_of == job.job_id
    assert retried.status == "queued"


def test_multi_fidelity_training_writes_artifacts(tmp_path):
    X_low = np.linspace(0, 1, 8).reshape(-1, 1)
    y_low = 2.0 * X_low.ravel()
    X_high = np.array([[0.1], [0.4], [0.8]])
    y_high = 2.0 * X_high.ravel() + 0.5

    result = train_multi_fidelity(X_low, y_low, X_high, y_high, output_root=tmp_path)
    assert result.predictions_csv.exists()
    assert result.metrics["n_high_fidelity"] == 3


def test_resample_curve_returns_fixed_length():
    curve = resample_curve(np.array([0.0, 0.5, 1.0]), np.array([0.0, 2.0, 4.0]), n_points=5)
    assert curve.tolist() == [0.0, 1.0, 2.0, 3.0, 4.0]
