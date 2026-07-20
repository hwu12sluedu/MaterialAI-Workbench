"""Validation-protocol and duplicate-sensitivity audit for CFRP regressors."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from material_ai_workbench.experimental_baselines import (
    DEFAULT_DATASET_DIR,
    DEFAULT_MODELS,
    MODEL_LABELS,
    TARGET_UNITS,
    _artifact_inventory,
    _features,
    _make_estimator,
    _model_order,
    _normalize_selection,
    _regression_metrics,
    _run_id,
    _runtime_versions,
    _targets,
    _utc_now,
    _write_csv,
    _write_json,
    _write_text,
    load_cfrp_baseline_dataset,
    validate_target_split_contract,
)
from material_ai_workbench.experimental_datasets import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
)
from material_ai_workbench.config import EXPERIMENTS_ROOT

DEFAULT_OUTPUT_ROOT = EXPERIMENTS_ROOT / "cfrp_validation_audits"

PROTOCOLS = (
    {
        "id": "grouped_raw",
        "dataset_variant": "raw",
        "split_strategy": "leave_one_material_type_out",
        "label": "Material-group holdout / raw",
    },
    {
        "id": "grouped_deduplicated",
        "dataset_variant": "deduplicated",
        "split_strategy": "leave_one_material_type_out",
        "label": "Material-group holdout / deduplicated",
    },
    {
        "id": "row_loocv_raw",
        "dataset_variant": "raw",
        "split_strategy": "leave_one_row_out",
        "label": "Row LOOCV / raw",
    },
    {
        "id": "row_loocv_deduplicated",
        "dataset_variant": "deduplicated",
        "split_strategy": "leave_one_row_out",
        "label": "Row LOOCV / deduplicated",
    },
)

_DUPLICATE_COLUMNS = (
    "material_type_id",
    *FEATURE_COLUMNS,
    *TARGET_COLUMNS,
)


@dataclass(frozen=True)
class ExperimentalValidationAudit:
    """Artifacts produced by one validation-protocol audit."""

    run_dir: Path
    manifest_json: Path
    summary_json: Path
    comparison_csv: Path
    predictions_csv: Path
    duplicate_clusters_csv: Path
    report_md: Path
    figure_paths: tuple[Path, ...]
    summary: dict[str, Any]


def run_cfrp_validation_audit(
    dataset_dir: Path | str = DEFAULT_DATASET_DIR,
    *,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    targets: Sequence[str] | None = None,
    models: Sequence[str] = DEFAULT_MODELS,
    random_state: int = 42,
    rf_estimators: int = 100,
) -> ExperimentalValidationAudit:
    """Compare strict group holdout and row LOOCV before and after deduplication.

    The row-level protocol is an explanatory comparison, not the release gate.
    Only complete material-type holdout estimates generalization to an unseen
    material type. Exact source duplicates are retained in the governed dataset
    and removed only in the explicit ``deduplicated`` audit variants.
    """

    selected_targets = _normalize_selection(
        targets or TARGET_COLUMNS, allowed=TARGET_COLUMNS, label="target"
    )
    selected_models = _normalize_selection(
        models, allowed=DEFAULT_MODELS, label="model"
    )
    if int(rf_estimators) < 10:
        raise ValueError("rf_estimators must be at least 10.")

    bundle = load_cfrp_baseline_dataset(dataset_dir)
    all_rows = sorted(
        bundle.rows_by_id.values(),
        key=lambda row: (int(row["source_row"]), str(row["sample_id"])),
    )
    duplicate_clusters, sample_clusters, canonical_ids = _audit_duplicates(all_rows)
    variants = {
        "raw": all_rows,
        "deduplicated": [
            row for row in all_rows if str(row["sample_id"]) in canonical_ids
        ],
    }

    output = Path(output_root).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    run_id = _run_id()
    final_dir = output / run_id
    working_dir = output / f".{run_id}.{uuid4().hex}.partial"
    working_dir.mkdir(parents=False, exist_ok=False)

    try:
        predictions: list[dict[str, Any]] = []
        comparison: list[dict[str, Any]] = []

        for target in selected_targets:
            registered_folds = validate_target_split_contract(bundle, target)
            for protocol in PROTOCOLS:
                eligible_rows = [
                    row
                    for row in variants[str(protocol["dataset_variant"])]
                    if row[target] is not None
                ]
                folds = _build_protocol_folds(
                    eligible_rows=eligible_rows,
                    strategy=str(protocol["split_strategy"]),
                    registered_group_folds=registered_folds,
                )
                protocol_comparison: list[dict[str, Any]] = []
                for model_kind in selected_models:
                    model_predictions = _evaluate_protocol(
                        eligible_rows=eligible_rows,
                        folds=folds,
                        target=target,
                        model_kind=model_kind,
                        protocol=protocol,
                        sample_clusters=sample_clusters,
                        random_state=random_state,
                        rf_estimators=int(rf_estimators),
                    )
                    predictions.extend(model_predictions)
                    metrics = _regression_metrics(model_predictions)
                    metrics.update(
                        {
                            "target": target,
                            "target_unit": TARGET_UNITS.get(target),
                            "protocol": protocol["id"],
                            "protocol_label": protocol["label"],
                            "dataset_variant": protocol["dataset_variant"],
                            "split_strategy": protocol["split_strategy"],
                            "model": model_kind,
                            "model_label": MODEL_LABELS[model_kind],
                            "sample_count": len(eligible_rows),
                            "unique_record_count": len(
                                {_record_fingerprint(row) for row in eligible_rows}
                            ),
                            "fold_count": len(folds),
                            "duplicate_extra_rows": len(eligible_rows)
                            - len({_record_fingerprint(row) for row in eligible_rows}),
                            "duplicate_test_record_count": sum(
                                bool(row["duplicate_cluster_id"])
                                for row in model_predictions
                            ),
                            "duplicate_leakage_sample_count": sum(
                                bool(row["exact_duplicate_in_training"])
                                for row in model_predictions
                            ),
                        }
                    )
                    protocol_comparison.append(metrics)

                _rank_models(protocol_comparison)
                comparison.extend(protocol_comparison)

        _add_protocol_deltas(comparison)
        predictions.sort(
            key=lambda row: (
                str(row["target"]),
                _protocol_order(str(row["protocol"])),
                _model_order(str(row["model"])),
                str(row["sample_id"]),
            )
        )
        comparison.sort(
            key=lambda row: (
                str(row["target"]),
                _protocol_order(str(row["protocol"])),
                int(row["rank_by_mae"]),
            )
        )

        predictions_csv = working_dir / "predictions.csv"
        comparison_csv = working_dir / "protocol_comparison.csv"
        duplicate_clusters_csv = working_dir / "duplicate_clusters.csv"
        _write_csv(predictions_csv, predictions, _prediction_columns())
        _write_csv(comparison_csv, comparison, _comparison_columns())
        _write_csv(
            duplicate_clusters_csv,
            duplicate_clusters,
            _duplicate_cluster_columns(),
        )

        figure_paths = _write_figures(
            working_dir / "figures",
            comparison,
            selected_targets,
            selected_models,
        )
        summary = _build_summary(
            run_id=run_id,
            bundle=bundle,
            comparison=comparison,
            duplicate_clusters=duplicate_clusters,
            targets=selected_targets,
            models=selected_models,
            raw_count=len(variants["raw"]),
            deduplicated_count=len(variants["deduplicated"]),
            random_state=random_state,
            rf_estimators=int(rf_estimators),
        )
        summary_json = working_dir / "summary.json"
        report_md = working_dir / "REPORT_CN.md"
        _write_json(summary_json, summary)
        _write_text(report_md, _render_report(summary, comparison))

        manifest_json = working_dir / "run_manifest.json"
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": _utc_now(),
            "experiment": "cfrp_validation_protocol_audit",
            "source_dataset": {
                "dataset_id": bundle.dataset_manifest["dataset_id"],
                "dataset_version": bundle.dataset_manifest["dataset_version"],
                "dataset_doi": bundle.dataset_manifest["source"]["dataset_doi"],
                "normalized_csv_sha256": bundle.normalized_sha256,
                "grouped_splits_sha256": bundle.split_sha256,
            },
            "configuration": {
                "features": list(FEATURE_COLUMNS),
                "targets": list(selected_targets),
                "models": list(selected_models),
                "protocols": [dict(protocol) for protocol in PROTOCOLS],
                "duplicate_definition_columns": list(_DUPLICATE_COLUMNS),
                "random_state": int(random_state),
                "rf_estimators": int(rf_estimators),
            },
            "evaluation": {
                "release_gate": "leave_one_material_type_out",
                "row_loocv_role": "paper_protocol_context_only",
                "hyperparameter_search": False,
                "paper_metric_comparability": "not_directly_comparable",
            },
            "runtime": _runtime_versions(),
            "artifacts": _artifact_inventory(working_dir, exclude={manifest_json}),
            "limitations": list(summary["limitations"]),
        }
        _write_json(manifest_json, manifest)
        os.replace(working_dir, final_dir)
    except Exception:
        if working_dir.exists() and working_dir.parent == output:
            shutil.rmtree(working_dir, ignore_errors=True)
        raise

    return ExperimentalValidationAudit(
        run_dir=final_dir,
        manifest_json=final_dir / "run_manifest.json",
        summary_json=final_dir / "summary.json",
        comparison_csv=final_dir / "protocol_comparison.csv",
        predictions_csv=final_dir / "predictions.csv",
        duplicate_clusters_csv=final_dir / "duplicate_clusters.csv",
        report_md=final_dir / "REPORT_CN.md",
        figure_paths=tuple(
            final_dir / path.relative_to(working_dir) for path in figure_paths
        ),
        summary=summary,
    )


def _audit_duplicates(
    rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str], set[str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_record_fingerprint(row)].append(row)

    clusters: list[dict[str, Any]] = []
    sample_clusters: dict[str, str] = {}
    canonical_ids: set[str] = set()
    for fingerprint, members in sorted(
        grouped.items(), key=lambda item: min(int(row["source_row"]) for row in item[1])
    ):
        ordered = sorted(
            members,
            key=lambda row: (int(row["source_row"]), str(row["sample_id"])),
        )
        retained = ordered[0]
        canonical_ids.add(str(retained["sample_id"]))
        if len(ordered) == 1:
            continue
        cluster_id = f"duplicate_{fingerprint[:12]}"
        for row in ordered:
            sample_clusters[str(row["sample_id"])] = cluster_id
        clusters.append(
            {
                "cluster_id": cluster_id,
                "record_count": len(ordered),
                "duplicate_extra_count": len(ordered) - 1,
                "material_type_id": int(retained["material_type_id"]),
                "material_type_name": str(retained["material_type_name"]),
                "retained_sample_id": str(retained["sample_id"]),
                "removed_sample_ids": "|".join(
                    str(row["sample_id"]) for row in ordered[1:]
                ),
                "all_sample_ids": "|".join(str(row["sample_id"]) for row in ordered),
                "source_rows": "|".join(str(row["source_row"]) for row in ordered),
                "fingerprint_sha256": fingerprint,
            }
        )
    return clusters, sample_clusters, canonical_ids


def _record_fingerprint(row: dict[str, Any]) -> str:
    payload = [row.get(column) for column in _DUPLICATE_COLUMNS]
    serialized = json.dumps(
        payload, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_protocol_folds(
    *,
    eligible_rows: Sequence[dict[str, Any]],
    strategy: str,
    registered_group_folds: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered_ids = [str(row["sample_id"]) for row in eligible_rows]
    allowed = set(ordered_ids)
    if len(allowed) != len(ordered_ids):
        raise ValueError("A protocol dataset variant contains duplicate sample ids.")
    if len(ordered_ids) < 2:
        raise ValueError("At least two labelled samples are required for validation.")

    if strategy == "leave_one_material_type_out":
        folds = []
        for registered in registered_group_folds:
            train_ids = [
                sample_id
                for sample_id in registered["train_sample_ids"]
                if sample_id in allowed
            ]
            test_ids = [
                sample_id
                for sample_id in registered["test_sample_ids"]
                if sample_id in allowed
            ]
            if not train_ids or not test_ids:
                raise ValueError(
                    "Deduplication removed every train or test sample from a group fold."
                )
            folds.append(
                {
                    "fold_id": str(registered["fold_id"]),
                    "test_group": int(registered["test_group"]),
                    "train_sample_ids": train_ids,
                    "test_sample_ids": test_ids,
                }
            )
    elif strategy == "leave_one_row_out":
        folds = [
            {
                "fold_id": f"holdout_{sample_id}",
                "test_group": None,
                "train_sample_ids": [item for item in ordered_ids if item != sample_id],
                "test_sample_ids": [sample_id],
            }
            for sample_id in ordered_ids
        ]
    else:
        raise ValueError(f"Unsupported validation strategy: {strategy}")

    _validate_protocol_folds(folds, allowed, strategy)
    return folds


def _validate_protocol_folds(
    folds: Sequence[dict[str, Any]], allowed: set[str], strategy: str
) -> None:
    test_occurrences: Counter[str] = Counter()
    for fold in folds:
        train = list(fold["train_sample_ids"])
        test = list(fold["test_sample_ids"])
        if len(train) != len(set(train)) or len(test) != len(set(test)):
            raise ValueError(f"Fold {fold['fold_id']} repeats a sample id.")
        train_set = set(train)
        test_set = set(test)
        if train_set & test_set:
            raise ValueError(f"Fold {fold['fold_id']} overlaps train and test samples.")
        if train_set | test_set != allowed:
            raise ValueError(f"Fold {fold['fold_id']} does not partition its variant.")
        if strategy == "leave_one_row_out" and len(test) != 1:
            raise ValueError("Row LOOCV must hold out exactly one sample per fold.")
        test_occurrences.update(test)
    if set(test_occurrences) != allowed or any(
        count != 1 for count in test_occurrences.values()
    ):
        raise ValueError(
            "Validation folds must test every eligible sample exactly once."
        )


def _evaluate_protocol(
    *,
    eligible_rows: Sequence[dict[str, Any]],
    folds: Sequence[dict[str, Any]],
    target: str,
    model_kind: str,
    protocol: dict[str, str],
    sample_clusters: dict[str, str],
    random_state: int,
    rf_estimators: int,
) -> list[dict[str, Any]]:
    eligible_by_id = {str(row["sample_id"]): row for row in eligible_rows}
    cluster_members: dict[str, set[str]] = defaultdict(set)
    for sample_id in eligible_by_id:
        cluster_id = sample_clusters.get(sample_id)
        if cluster_id:
            cluster_members[cluster_id].add(sample_id)

    predictions: list[dict[str, Any]] = []
    for fold in folds:
        train_ids = list(fold["train_sample_ids"])
        test_ids = list(fold["test_sample_ids"])
        train_rows = [eligible_by_id[sample_id] for sample_id in train_ids]
        test_rows = [eligible_by_id[sample_id] for sample_id in test_ids]
        estimator = _make_estimator(
            model_kind,
            random_state=random_state,
            rf_estimators=rf_estimators,
        )
        estimator.fit(_features(train_rows), _targets(train_rows, target))
        predicted = np.asarray(estimator.predict(_features(test_rows)), dtype=float)
        train_set = set(train_ids)
        for row, prediction in zip(test_rows, predicted):
            sample_id = str(row["sample_id"])
            truth = float(row[target])
            residual = float(prediction - truth)
            cluster_id = sample_clusters.get(sample_id, "")
            duplicate_in_training = bool(
                cluster_id and cluster_members[cluster_id].intersection(train_set)
            )
            predictions.append(
                {
                    "target": target,
                    "target_unit": TARGET_UNITS.get(target),
                    "protocol": protocol["id"],
                    "protocol_label": protocol["label"],
                    "dataset_variant": protocol["dataset_variant"],
                    "split_strategy": protocol["split_strategy"],
                    "model": model_kind,
                    "model_label": MODEL_LABELS[model_kind],
                    "fold_id": fold["fold_id"],
                    "test_group": int(row["material_type_id"]),
                    "sample_id": sample_id,
                    "source_row": int(row["source_row"]),
                    "truth": truth,
                    "prediction": float(prediction),
                    "residual": residual,
                    "absolute_error": abs(residual),
                    "relative_error": (
                        abs(residual) / abs(truth) if abs(truth) > 1e-12 else None
                    ),
                    "train_count": len(train_rows),
                    "test_count": len(test_rows),
                    "duplicate_cluster_id": cluster_id,
                    "exact_duplicate_in_training": duplicate_in_training,
                }
            )
    return predictions


def _rank_models(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(
        rows, key=lambda row: (float(row["mae"]), _model_order(str(row["model"])))
    )
    mean_row = next((row for row in rows if row["model"] == "mean"), None)
    mean_mae = float(mean_row["mae"]) if mean_row is not None else None
    for rank, row in enumerate(ordered, start=1):
        row["rank_by_mae"] = rank
        row["mae_improvement_vs_mean_pct"] = (
            100.0 * (mean_mae - float(row["mae"])) / mean_mae
            if mean_mae is not None and mean_mae > 1e-15
            else None
        )
        row["beats_mean_baseline"] = (
            bool(float(row["mae"]) < mean_mae - 1e-12) if mean_mae is not None else None
        )


def _add_protocol_deltas(rows: list[dict[str, Any]]) -> None:
    indexed = {
        (str(row["target"]), str(row["model"]), str(row["protocol"])): row
        for row in rows
    }
    for row in rows:
        target = str(row["target"])
        model = str(row["model"])
        strict = indexed[(target, model, "grouped_raw")]
        strict_mae = float(strict["mae"])
        row["mae_reduction_vs_grouped_raw_pct"] = (
            100.0 * (strict_mae - float(row["mae"])) / strict_mae
            if strict_mae > 1e-15
            else None
        )
        strict_r2 = strict.get("r2")
        row_r2 = row.get("r2")
        row["r2_gain_vs_grouped_raw"] = (
            float(row_r2) - float(strict_r2)
            if row_r2 is not None and strict_r2 is not None
            else None
        )
        if row["dataset_variant"] == "deduplicated":
            raw_protocol = (
                "grouped_raw"
                if row["split_strategy"] == "leave_one_material_type_out"
                else "row_loocv_raw"
            )
            raw = indexed[(target, model, raw_protocol)]
            raw_mae = float(raw["mae"])
            row["dedup_mae_change_pct"] = (
                100.0 * (float(row["mae"]) - raw_mae) / raw_mae
                if raw_mae > 1e-15
                else None
            )
        else:
            row["dedup_mae_change_pct"] = None


def _build_summary(
    *,
    run_id: str,
    bundle: Any,
    comparison: Sequence[dict[str, Any]],
    duplicate_clusters: Sequence[dict[str, Any]],
    targets: Sequence[str],
    models: Sequence[str],
    raw_count: int,
    deduplicated_count: int,
    random_state: int,
    rf_estimators: int,
) -> dict[str, Any]:
    target_summaries: dict[str, Any] = {}
    for target in targets:
        target_rows = [row for row in comparison if row["target"] == target]
        best_by_protocol = {}
        for protocol in PROTOCOLS:
            candidates = [
                row for row in target_rows if row["protocol"] == protocol["id"]
            ]
            best = min(candidates, key=lambda row: int(row["rank_by_mae"]))
            best_by_protocol[str(protocol["id"])] = {
                "model": best["model"],
                "mae": best["mae"],
                "rmse": best["rmse"],
                "r2": best["r2"],
            }

        model_gaps = {}
        for model in models:
            indexed = {
                str(row["protocol"]): row
                for row in target_rows
                if row["model"] == model
            }
            model_gaps[model] = {
                "grouped_raw_mae": indexed["grouped_raw"]["mae"],
                "grouped_raw_r2": indexed["grouped_raw"]["r2"],
                "row_loocv_raw_mae": indexed["row_loocv_raw"]["mae"],
                "row_loocv_raw_r2": indexed["row_loocv_raw"]["r2"],
                "row_loocv_deduplicated_mae": indexed["row_loocv_deduplicated"]["mae"],
                "row_loocv_deduplicated_r2": indexed["row_loocv_deduplicated"]["r2"],
                "row_loocv_raw_r2_gain_vs_grouped": indexed["row_loocv_raw"][
                    "r2_gain_vs_grouped_raw"
                ],
                "row_loocv_dedup_mae_change_pct": indexed["row_loocv_deduplicated"][
                    "dedup_mae_change_pct"
                ],
                "row_loocv_duplicate_leakage_samples": indexed["row_loocv_raw"][
                    "duplicate_leakage_sample_count"
                ],
            }
        target_summaries[target] = {
            "target_unit": TARGET_UNITS.get(target),
            "best_by_protocol": best_by_protocol,
            "model_protocol_gaps": model_gaps,
        }

    duplicate_extra_count = sum(
        int(cluster["duplicate_extra_count"]) for cluster in duplicate_clusters
    )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": _utc_now(),
        "experiment": "cfrp_validation_protocol_audit",
        "source_dataset": {
            "dataset_id": bundle.dataset_manifest["dataset_id"],
            "dataset_version": bundle.dataset_manifest["dataset_version"],
            "dataset_doi": bundle.dataset_manifest["source"]["dataset_doi"],
            "normalized_csv_sha256": bundle.normalized_sha256,
            "grouped_splits_sha256": bundle.split_sha256,
        },
        "configuration": {
            "features": list(FEATURE_COLUMNS),
            "targets": list(targets),
            "models": list(models),
            "random_state": int(random_state),
            "rf_estimators": int(rf_estimators),
        },
        "protocols": [dict(protocol) for protocol in PROTOCOLS],
        "release_gate_protocol": "grouped_raw",
        "duplicate_audit": {
            "definition": "exact equality across group, all features, and all targets",
            "definition_columns": list(_DUPLICATE_COLUMNS),
            "raw_row_count": raw_count,
            "deduplicated_row_count": deduplicated_count,
            "cluster_count": len(duplicate_clusters),
            "duplicate_extra_rows": duplicate_extra_count,
            "duplicate_record_count": sum(
                int(cluster["record_count"]) for cluster in duplicate_clusters
            ),
        },
        "targets": target_summaries,
        "interpretation": {
            "grouped_holdout": (
                "Estimates transfer to a material type absent from training and is "
                "the release gate for this dataset."
            ),
            "row_loocv": (
                "Estimates interpolation among rows whose material types remain in "
                "training; it is context for the paper protocol, not deployment proof."
            ),
            "deduplication": (
                "Shows how exact repeated source records change scores without "
                "altering the governed raw dataset."
            ),
        },
        "paper_comparison": {
            "status": "not_directly_comparable",
            "reason": (
                "The audit adds a paper-like row LOOCV view, but preprocessing, "
                "model definitions, and tuning are not asserted to match the paper."
            ),
        },
        "limitations": [
            "The dataset contains only 62 source rows and nine material types.",
            "Row LOOCV is not evidence of generalization to a new material type.",
            "Exact deduplication does not detect near-duplicates or shared provenance.",
            "No hyperparameter optimization is performed in this audit.",
            "The targets are scalar properties, not stress-strain histories or a constitutive law.",
            "Source-labelled units are retained without silent correction.",
        ],
    }


def _write_figures(
    figure_dir: Path,
    comparison: Sequence[dict[str, Any]],
    targets: Sequence[str],
    models: Sequence[str],
) -> list[Path]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for target in targets:
        path = figure_dir / f"{target}_protocol_sensitivity.png"
        _plot_protocol_sensitivity(path, target, comparison, models)
        paths.append(path)
    return paths


def _plot_protocol_sensitivity(
    path: Path,
    target: str,
    comparison: Sequence[dict[str, Any]],
    models: Sequence[str],
) -> None:
    protocol_ids = [str(protocol["id"]) for protocol in PROTOCOLS]
    protocol_labels = [
        "Group\nraw",
        "Group\ndedup",
        "Row LOOCV\nraw",
        "Row LOOCV\ndedup",
    ]
    colors = ("#4c78a8", "#f58518", "#54a24b", "#e45756")
    x = np.arange(len(protocol_ids), dtype=float)
    width = 0.18
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    target_rows = [row for row in comparison if row["target"] == target]
    indexed = {(str(row["protocol"]), str(row["model"])): row for row in target_rows}
    for model_index, model in enumerate(models):
        offset = (model_index - (len(models) - 1) / 2.0) * width
        rows = [indexed[(protocol, model)] for protocol in protocol_ids]
        axes[0].bar(
            x + offset,
            [float(row["mae"]) for row in rows],
            width,
            label=MODEL_LABELS[model],
            color=colors[model_index % len(colors)],
        )
        axes[1].bar(
            x + offset,
            [float(row["r2"]) if row["r2"] is not None else np.nan for row in rows],
            width,
            color=colors[model_index % len(colors)],
        )
    axes[0].set_title("Mean absolute error")
    axes[0].set_ylabel(f"MAE ({TARGET_UNITS.get(target) or 'source unit'})")
    axes[1].set_title("Coefficient of determination")
    axes[1].set_ylabel("R2")
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    for axis in axes:
        axis.set_xticks(x, protocol_labels)
        axis.grid(axis="y", alpha=0.2)
    axes[0].legend(loc="best", fontsize=8)
    fig.suptitle(f"Validation sensitivity: {target}")
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _render_report(
    summary: dict[str, Any], comparison: Sequence[dict[str, Any]]
) -> str:
    duplicate = summary["duplicate_audit"]
    sections = []
    for target, details in summary["targets"].items():
        rows = [row for row in comparison if row["target"] == target]
        table = [
            "| 模型 | 整类留出原始 R2 | 逐行留一原始 R2 | 逐行留一去重 R2 | 整类留出原始 MAE | 逐行留一原始 MAE | 逐行留一去重 MAE |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for model in summary["configuration"]["models"]:
            indexed = {row["protocol"]: row for row in rows if row["model"] == model}
            table.append(
                "| `{model}` | {group_r2} | {row_r2} | {dedup_r2} | {group_mae} | {row_mae} | {dedup_mae} |".format(
                    model=model,
                    group_r2=_format_number(indexed["grouped_raw"]["r2"]),
                    row_r2=_format_number(indexed["row_loocv_raw"]["r2"]),
                    dedup_r2=_format_number(indexed["row_loocv_deduplicated"]["r2"]),
                    group_mae=_format_number(indexed["grouped_raw"]["mae"]),
                    row_mae=_format_number(indexed["row_loocv_raw"]["mae"]),
                    dedup_mae=_format_number(indexed["row_loocv_deduplicated"]["mae"]),
                )
            )
        best_lines = []
        for protocol in PROTOCOLS:
            best = details["best_by_protocol"][protocol["id"]]
            best_lines.append(
                f"- `{protocol['id']}`：`{best['model']}`，MAE "
                f"{_format_number(best['mae'])}，R2 {_format_number(best['r2'])}"
            )
        sections.append(f"""## `{target}`

- 源标签单位：`{details['target_unit']}`
{chr(10).join(best_lines)}

{chr(10).join(table)}
""")

    limitations = "\n".join(f"- {item}" for item in summary["limitations"])
    return f"""# CFRP 验证协议与重复样本敏感性报告

## 这次审计回答什么

同一套特征和模型分别使用四种协议：整类材料留出/逐行留一，以及原始/完全去重数据。目标是解释为什么论文式逐行留一成绩可能明显高于新材料泛化成绩，并定量检查完全重复记录是否进入逐行留一训练集。

## 重复样本

- 原始行数：`{duplicate['raw_row_count']}`
- 去重后行数：`{duplicate['deduplicated_row_count']}`
- 完全重复簇：`{duplicate['cluster_count']}`
- 首条记录之外的重复行：`{duplicate['duplicate_extra_rows']}`
- 判定字段：材料类型、全部四个输入特征和全部四个目标。

原始数据没有被修改；去重只存在于本次敏感性实验的派生视图中。

{chr(10).join(sections)}
## 工程结论怎么读

- `grouped_raw` 是当前发布门槛：测试材料类型在训练中完全不可见。
- `row_loocv_raw` 只说明模型能否在已知材料类型的相邻样本之间插值。
- 若逐行留一成绩显著高于整类留出，不能直接解释为模型能够预测全新复材。
- 若逐行留一去重后明显变差，说明完全重复记录抬高了原始协议成绩。
- 本结果仍不是论文数值复现，因为没有声称完全复制论文预处理、超参数和实现细节。

## 产物

- `protocol_comparison.csv`：四种协议下的模型指标、排名和相对严格协议的差值。
- `predictions.csv`：每个样本的 OOF 预测，以及训练集中是否存在完全相同记录。
- `duplicate_clusters.csv`：重复簇、保留样本和去重样本的来源行。
- `figures/`：每个目标的 MAE 与 R2 协议敏感性图。

## 限制

{limitations}
"""


def _prediction_columns() -> list[str]:
    return [
        "target",
        "target_unit",
        "protocol",
        "protocol_label",
        "dataset_variant",
        "split_strategy",
        "model",
        "model_label",
        "fold_id",
        "test_group",
        "sample_id",
        "source_row",
        "truth",
        "prediction",
        "residual",
        "absolute_error",
        "relative_error",
        "train_count",
        "test_count",
        "duplicate_cluster_id",
        "exact_duplicate_in_training",
    ]


def _comparison_columns() -> list[str]:
    return [
        "target",
        "target_unit",
        "protocol",
        "protocol_label",
        "dataset_variant",
        "split_strategy",
        "rank_by_mae",
        "model",
        "model_label",
        "sample_count",
        "unique_record_count",
        "fold_count",
        "duplicate_extra_rows",
        "duplicate_test_record_count",
        "duplicate_leakage_sample_count",
        "mae",
        "rmse",
        "r2",
        "median_absolute_error",
        "mean_relative_error",
        "bias",
        "max_absolute_error",
        "nrmse_by_range",
        "mae_improvement_vs_mean_pct",
        "beats_mean_baseline",
        "mae_reduction_vs_grouped_raw_pct",
        "r2_gain_vs_grouped_raw",
        "dedup_mae_change_pct",
    ]


def _duplicate_cluster_columns() -> list[str]:
    return [
        "cluster_id",
        "record_count",
        "duplicate_extra_count",
        "material_type_id",
        "material_type_name",
        "retained_sample_id",
        "removed_sample_ids",
        "all_sample_ids",
        "source_rows",
        "fingerprint_sha256",
    ]


def _protocol_order(protocol: str) -> int:
    ids = [str(item["id"]) for item in PROTOCOLS]
    try:
        return ids.index(protocol)
    except ValueError:
        return len(ids)


def _format_number(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.4g}"


__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "ExperimentalValidationAudit",
    "PROTOCOLS",
    "run_cfrp_validation_audit",
]
