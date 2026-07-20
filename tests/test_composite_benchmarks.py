import copy

import pytest

from material_ai_workbench.composite_benchmarks import (
    composite_benchmark_rows,
    load_composite_benchmark_registry,
    load_composite_benchmarks,
    validate_composite_benchmark_registry,
)


def test_packaged_composite_benchmark_registry_is_traceable():
    registry = load_composite_benchmark_registry()
    entries = registry["benchmarks"]

    assert registry["schema_version"] == 1
    assert len(entries) >= 8
    assert all(entry["source"]["doi"] for entry in entries)
    assert all(entry["reproduction"]["status"] != "reproduced" for entry in entries)


def test_naive_bayes_is_registered_as_classification_not_regression():
    entries = load_composite_benchmarks()
    naive_bayes_entries = [
        entry for entry in entries if "naive_bayes" in entry["models"]
    ]

    assert naive_bayes_entries
    assert all(entry["task_kind"] == "classification" for entry in naive_bayes_entries)
    assert any(
        "损伤" in target or "断裂" in target
        for entry in naive_bayes_entries
        for target in entry["targets"]
    )


def test_composite_benchmark_rows_can_filter_open_data_regression():
    rows = composite_benchmark_rows(
        task_kind="regression", reproduction_status="data_available"
    )

    assert rows
    assert all(row["task_kind"] == "regression" for row in rows)
    assert all(row["reproduction_status"] == "data_available" for row in rows)
    assert all(row["dataset_url"] for row in rows)


def test_registry_rejects_unearned_reproduced_status():
    payload = copy.deepcopy(load_composite_benchmark_registry())
    payload["benchmarks"][0]["reproduction"] = {
        "status": "reproduced",
        "our_metrics": None,
        "notes": "invalid",
    }

    with pytest.raises(ValueError, match="cannot use reproduced without our_metrics"):
        validate_composite_benchmark_registry(payload)


def test_cfrp_independent_baseline_is_registered_without_paper_overclaim():
    entry = next(
        item
        for item in load_composite_benchmarks()
        if item["id"] == "alsheghri_2025_cfrp_experiment"
    )

    assert entry["reproduction"]["status"] == "baseline_completed"
    metrics = entry["reproduction"]["our_metrics"]
    assert metrics["protocol"] == "leave_one_material_type_out"
    assert metrics["paper_comparability"] == "not_directly_comparable"
    assert len(metrics["normalized_csv_sha256"]) == 64
    assert len(metrics["results"]) == 4
    assert any(result["best_model"] == "mean" for result in metrics["results"])


def test_registry_rejects_duplicate_ids():
    payload = copy.deepcopy(load_composite_benchmark_registry())
    payload["benchmarks"].append(copy.deepcopy(payload["benchmarks"][0]))

    with pytest.raises(ValueError, match="Duplicate composite benchmark id"):
        validate_composite_benchmark_registry(payload)
