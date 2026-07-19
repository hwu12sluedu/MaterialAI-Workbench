"""Traceable literature and experimental benchmarks for composite ML work."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

_REGISTRY_RESOURCE = "composite_benchmarks.json"
_TASK_KINDS = {"regression", "classification", "calibration_validation"}
_DATA_KINDS = {"finite_element", "numerical_homogenisation", "experimental"}
_REPRODUCTION_STATUSES = {"reference_only", "data_available", "reproduced"}
_REQUIRED_ENTRY_FIELDS = {
    "id",
    "title",
    "year",
    "material_system",
    "task_kind",
    "data_kind",
    "input_features",
    "targets",
    "models",
    "sample_count",
    "reported_metrics",
    "source",
    "reproduction",
}


def load_composite_benchmark_registry(path: Path | str | None = None) -> dict[str, Any]:
    """Load and validate the packaged registry or a user-supplied registry file."""

    if path is None:
        text = (
            files("material_ai_workbench.resources")
            .joinpath(_REGISTRY_RESOURCE)
            .read_text(encoding="utf-8")
        )
        source_name = f"material_ai_workbench.resources/{_REGISTRY_RESOURCE}"
    else:
        registry_path = Path(path)
        text = registry_path.read_text(encoding="utf-8")
        source_name = str(registry_path)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid composite benchmark JSON in {source_name}: {exc}"
        ) from exc
    return validate_composite_benchmark_registry(payload, source_name=source_name)


def load_composite_benchmarks(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Return validated benchmark entries."""

    return list(load_composite_benchmark_registry(path)["benchmarks"])


def composite_benchmark_rows(
    path: Path | str | None = None,
    *,
    task_kind: str | None = None,
    reproduction_status: str | None = None,
) -> list[dict[str, Any]]:
    """Return flattened rows suitable for the desktop or Streamlit tables."""

    if task_kind is not None and task_kind not in _TASK_KINDS:
        raise ValueError(f"Unsupported task_kind: {task_kind}")
    if (
        reproduction_status is not None
        and reproduction_status not in _REPRODUCTION_STATUSES
    ):
        raise ValueError(f"Unsupported reproduction_status: {reproduction_status}")

    rows: list[dict[str, Any]] = []
    for entry in load_composite_benchmarks(path):
        status = entry["reproduction"]["status"]
        if task_kind is not None and entry["task_kind"] != task_kind:
            continue
        if reproduction_status is not None and status != reproduction_status:
            continue
        rows.append(
            {
                "id": entry["id"],
                "year": entry["year"],
                "title": entry["title"],
                "material_system": entry["material_system"],
                "task_kind": entry["task_kind"],
                "data_kind": entry["data_kind"],
                "targets": "; ".join(entry["targets"]),
                "models": "; ".join(entry["models"]),
                "sample_count": entry["sample_count"],
                "reproduction_status": status,
                "doi": entry["source"]["doi"],
                "article_url": entry["source"]["article_url"],
                "dataset_url": entry["source"].get("dataset_url"),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["year"]), str(row["id"])))


def validate_composite_benchmark_registry(
    payload: Any,
    *,
    source_name: str = "composite benchmark registry",
) -> dict[str, Any]:
    """Validate provenance fields and prevent unearned reproduction claims."""

    if not isinstance(payload, dict):
        raise ValueError(f"{source_name} must contain a JSON object.")
    if payload.get("schema_version") != 1:
        raise ValueError(f"{source_name} must use schema_version 1.")
    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, list) or not benchmarks:
        raise ValueError(f"{source_name} must contain a non-empty benchmarks list.")

    seen_ids: set[str] = set()
    for index, entry in enumerate(benchmarks):
        label = f"{source_name} benchmark #{index + 1}"
        if not isinstance(entry, dict):
            raise ValueError(f"{label} must be an object.")
        missing = _REQUIRED_ENTRY_FIELDS - set(entry)
        if missing:
            raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}")

        benchmark_id = str(entry["id"]).strip()
        if not benchmark_id:
            raise ValueError(f"{label} has an empty id.")
        if benchmark_id in seen_ids:
            raise ValueError(f"Duplicate composite benchmark id: {benchmark_id}")
        seen_ids.add(benchmark_id)

        if entry["task_kind"] not in _TASK_KINDS:
            raise ValueError(f"{label} has unsupported task_kind: {entry['task_kind']}")
        if entry["data_kind"] not in _DATA_KINDS:
            raise ValueError(f"{label} has unsupported data_kind: {entry['data_kind']}")
        if not isinstance(entry["targets"], list) or not entry["targets"]:
            raise ValueError(f"{label} must define at least one target.")
        if not isinstance(entry["input_features"], list) or not entry["input_features"]:
            raise ValueError(f"{label} must define at least one input feature.")

        source = entry["source"]
        if (
            not isinstance(source, dict)
            or not source.get("doi")
            or not source.get("article_url")
        ):
            raise ValueError(f"{label} must define source.doi and source.article_url.")
        if not str(source["article_url"]).startswith("https://"):
            raise ValueError(f"{label} source.article_url must use HTTPS.")

        reproduction = entry["reproduction"]
        if not isinstance(reproduction, dict):
            raise ValueError(f"{label} reproduction must be an object.")
        status = reproduction.get("status")
        if status not in _REPRODUCTION_STATUSES:
            raise ValueError(f"{label} has unsupported reproduction status: {status}")
        our_metrics = reproduction.get("our_metrics")
        if status == "reproduced" and not isinstance(our_metrics, dict):
            raise ValueError(f"{label} cannot be reproduced without our_metrics.")
        if status != "reproduced" and our_metrics is not None:
            raise ValueError(
                f"{label} cannot publish our_metrics before reproduction is complete."
            )

    return payload


__all__ = [
    "composite_benchmark_rows",
    "load_composite_benchmark_registry",
    "load_composite_benchmarks",
    "validate_composite_benchmark_registry",
]
