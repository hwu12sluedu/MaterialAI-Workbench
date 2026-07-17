"""Stable case-package contract and quality gates for archived Abaqus work."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

CASE_PACKAGE_SCHEMA_VERSION = "2.0"
QUALITY_SCHEMA_VERSION = "1.0"
FULL_HASH_LIMIT_BYTES = 64 * 1024 * 1024
SAMPLED_HASH_BYTES = 1024 * 1024

_UNIT_FIELDS = ("system", "length", "force", "time", "stress", "temperature")
_UNIT_PRESETS: dict[str, dict[str, str]] = {
    "mm-n-s-mpa": {
        "system": "mm-N-s-MPa",
        "length": "mm",
        "force": "N",
        "time": "s",
        "stress": "MPa",
        "temperature": "degC",
    },
    "si": {
        "system": "SI-m-kg-s-Pa",
        "length": "m",
        "force": "N",
        "time": "s",
        "stress": "Pa",
        "temperature": "K",
    },
}


def normalize_case_units(
    units: dict[str, Any] | str | None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize an explicit Abaqus unit declaration without guessing units."""

    params = parameters or {}
    raw: dict[str, Any]
    if isinstance(units, str):
        raw = {"system": units}
    elif isinstance(units, dict):
        raw = dict(units)
    else:
        nested = params.get("units")
        raw = dict(nested) if isinstance(nested, dict) else {}

    if not raw and params.get("unit_system"):
        raw["system"] = params.get("unit_system")
    for field_name in _UNIT_FIELDS[1:]:
        parameter_key = f"{field_name}_unit"
        if not raw.get(field_name) and params.get(parameter_key):
            raw[field_name] = params[parameter_key]

    preset_key = _unit_preset_key(raw.get("system", ""))
    normalized = dict(_UNIT_PRESETS.get(preset_key, {}))
    for field_name in _UNIT_FIELDS:
        value = str(raw.get(field_name, "")).strip()
        if value:
            normalized[field_name] = value
        else:
            normalized.setdefault(field_name, "")

    normalized["declared"] = bool(
        normalized.get("system")
        and normalized.get("length")
        and normalized.get("force")
        and normalized.get("stress")
    )
    return normalized


def fingerprint_file(
    path: Path | str, size_bytes: int | None = None
) -> tuple[str, str]:
    """Return a full hash for normal files and a bounded sampled hash for large files."""

    file_path = Path(path)
    size = int(size_bytes if size_bytes is not None else file_path.stat().st_size)
    digest = hashlib.sha256()
    try:
        with file_path.open("rb") as handle:
            if size <= FULL_HASH_LIMIT_BYTES:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
                return digest.hexdigest(), "sha256-full"

            digest.update(b"materialai-sampled-file-v1\0")
            digest.update(str(size).encode("ascii"))
            digest.update(b"\0")
            digest.update(handle.read(SAMPLED_HASH_BYTES))
            handle.seek(max(0, size - SAMPLED_HASH_BYTES))
            digest.update(handle.read(SAMPLED_HASH_BYTES))
            return digest.hexdigest(), "sha256-size-first-last-1MiB"
    except OSError:
        return "", "unavailable"


def fingerprint_case_files(files: Iterable[Any]) -> str:
    """Build a stable source fingerprint from ordered relative paths and file hashes."""

    digest = hashlib.sha256()
    digest.update(b"materialai-case-source-v2\0")
    rows = sorted(
        files, key=lambda item: str(getattr(item, "relative_path", "")).casefold()
    )
    for item in rows:
        values = (
            str(getattr(item, "relative_path", "")).replace("\\", "/").casefold(),
            str(int(getattr(item, "size_bytes", 0) or 0)),
            str(getattr(item, "fingerprint", "")),
            str(getattr(item, "fingerprint_mode", "")),
        )
        digest.update("\0".join(values).encode("utf-8", errors="replace"))
        digest.update(b"\n")
    return digest.hexdigest()


def evaluate_case_quality(summary: Any) -> dict[str, Any]:
    """Evaluate whether an indexed case is trustworthy enough for ML training."""

    checks: list[dict[str, Any]] = []
    files = list(getattr(summary, "files", []) or [])
    file_counts = dict(getattr(summary, "file_counts", {}) or {})
    inp = _nested_summary(getattr(summary, "inp_features", {}))
    result = _nested_summary(getattr(summary, "result_features", {}))
    units = normalize_case_units(
        getattr(summary, "units", {}), getattr(summary, "parameters", {})
    )
    material_type = str(getattr(summary, "material_type", "") or "").strip().lower()
    materials = list(inp.get("materials", []) or [])
    mesh = dict(getattr(summary, "mesh_stats", {}) or {})
    odb_extractions = list(getattr(summary, "odb_extractions", []) or [])
    log_rows = list(
        (getattr(summary, "result_features", {}) or {}).get("log_files", []) or []
    )
    log_statuses = [str(item.get("status_hint", "unknown")) for item in log_rows]
    has_solver_error = (
        "error_or_aborted" in log_statuses or int(result.get("error_count", 0) or 0) > 0
    )
    has_completion = "completed" in log_statuses
    odb_count = int(result.get("odb_file_count", 0) or 0)
    labels = _numeric_labels(summary)
    execution_state = _execution_state(
        has_solver_error=has_solver_error,
        has_completion=has_completion,
        odb_count=odb_count,
        has_extraction=bool(odb_extractions),
        has_model=bool(file_counts.get("model", 0)),
    )

    _add_check(
        checks,
        "source_files",
        "pass" if files else "fail",
        10,
        (
            "Source files are indexed."
            if files
            else "No readable source files were indexed."
        ),
        {"file_count": len(files)},
    )
    has_model = int(file_counts.get("model", 0) or 0) > 0
    _add_check(
        checks,
        "model_input",
        "pass" if has_model else "fail",
        12,
        (
            "A model input is available."
            if has_model
            else "No INP, CAE, or CAD model file is available."
        ),
        {"model_file_count": int(file_counts.get("model", 0) or 0)},
    )
    inp_count = int(inp.get("inp_file_count", 0) or 0)
    inp_errors = int(inp.get("parse_error_count", 0) or 0)
    inp_status = (
        "pass" if inp_count and not inp_errors else ("warn" if has_model else "fail")
    )
    _add_check(
        checks,
        "inp_parse",
        inp_status,
        8,
        (
            "INP structure parsed."
            if inp_status == "pass"
            else "INP structure is missing or incomplete."
        ),
        {"inp_file_count": inp_count, "parse_error_count": inp_errors},
    )
    _add_check(
        checks,
        "unit_declaration",
        "pass" if units["declared"] else "warn",
        12,
        (
            "Units are explicitly declared."
            if units["declared"]
            else "Abaqus is unitless; declare the unit system before training."
        ),
        units,
    )
    material_identified = bool(
        materials or (material_type and material_type != "unknown")
    )
    _add_check(
        checks,
        "material_identity",
        "pass" if material_identified else "warn",
        10,
        (
            "Material identity is available."
            if material_identified
            else "Material identity was not recognized."
        ),
        {"material_type": material_type, "materials": materials},
    )
    node_count = int(mesh.get("node_count", 0) or 0)
    element_count = int(mesh.get("element_count", 0) or 0)
    mesh_identified = node_count > 0 and element_count > 0
    _add_check(
        checks,
        "mesh_identity",
        "pass" if mesh_identified else "warn",
        8,
        (
            "Mesh size is indexed."
            if mesh_identified
            else "Mesh node/element counts are unavailable."
        ),
        {"node_count": node_count, "element_count": element_count},
    )
    solver_status = (
        "fail" if has_solver_error else ("pass" if has_completion else "warn")
    )
    _add_check(
        checks,
        "solver_completion",
        solver_status,
        15,
        _solver_message(solver_status, execution_state),
        {"execution_state": execution_state, "log_statuses": log_statuses},
    )
    _add_check(
        checks,
        "odb_evidence",
        "pass" if odb_count else "warn",
        10,
        "ODB evidence is indexed." if odb_count else "No ODB result is indexed.",
        {"odb_file_count": odb_count, "extraction_count": len(odb_extractions)},
    )
    _add_check(
        checks,
        "numeric_targets",
        "pass" if labels else "warn",
        10,
        (
            "Numeric result targets are available."
            if labels
            else "No numeric ML target has been extracted."
        ),
        {"labels": labels},
    )
    source_fingerprint = str(getattr(summary, "source_fingerprint", "") or "")
    _add_check(
        checks,
        "lineage",
        "pass" if source_fingerprint else "warn",
        5,
        (
            "Source lineage fingerprint is available."
            if source_fingerprint
            else "Source fingerprint is missing."
        ),
        {"source_fingerprint": source_fingerprint},
    )

    blockers: list[str] = []
    if execution_state not in {"solved", "postprocessed"}:
        blockers.append("execution_evidence_not_solved")
    if has_solver_error:
        blockers.append("solver_error_or_abort_detected")
    if not units["declared"]:
        blockers.append("units_not_declared")
    if not material_identified:
        blockers.append("material_not_identified")
    if not mesh_identified:
        blockers.append("mesh_not_identified")
    if not labels:
        blockers.append("numeric_targets_missing")

    score = _quality_score(checks)
    critical_failure = any(
        item["status"] == "fail"
        and item["id"] in {"source_files", "model_input", "solver_completion"}
        for item in checks
    )
    overall_status = (
        "fail"
        if critical_failure
        else ("warn" if any(item["status"] != "pass" for item in checks) else "pass")
    )
    return {
        "schema_version": QUALITY_SCHEMA_VERSION,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "status": overall_status,
        "score": score,
        "execution_state": execution_state,
        "training_eligible": not blockers,
        "blocking_reasons": blockers,
        "recommended_actions": _recommended_actions(blockers),
        "checks": checks,
    }


def build_case_package(summary: Any) -> dict[str, Any]:
    """Build the public, versioned case-package document from an internal summary."""

    quality = evaluate_case_quality(summary)
    result_features = getattr(summary, "result_features", {}) or {}
    inp_features = getattr(summary, "inp_features", {}) or {}
    files = list(getattr(summary, "files", []) or [])
    units = normalize_case_units(
        getattr(summary, "units", {}), getattr(summary, "parameters", {})
    )
    solver = dict(getattr(summary, "solver", {}) or {})
    solver.setdefault("name", "Abaqus")
    solver["execution_state"] = quality["execution_state"]
    solver["job_names"] = _job_names(files)
    source_fingerprint = str(getattr(summary, "source_fingerprint", "") or "")
    if not source_fingerprint:
        source_fingerprint = fingerprint_case_files(files)

    return {
        "schema_version": CASE_PACKAGE_SCHEMA_VERSION,
        "package_type": "materialai_abaqus_case",
        "case_id": str(getattr(summary, "case_id", "")),
        "title": str(getattr(summary, "title", "")),
        "description": str(getattr(summary, "description", "")),
        "tags": list(getattr(summary, "tags", []) or []),
        "user_status": str(getattr(summary, "status", "")),
        "created_at": str(getattr(summary, "created_at", "")),
        "updated_at": str(getattr(summary, "updated_at", "")),
        "source": {
            "mode": str(
                (getattr(summary, "provenance", {}) or {}).get(
                    "source_mode", "reference"
                )
            ),
            "root": str(getattr(summary, "source_folder", "")),
            "fingerprint": source_fingerprint,
            "file_count": len(files),
            "total_size_bytes": int(getattr(summary, "total_size_bytes", 0) or 0),
        },
        "solver": solver,
        "units": units,
        "model": {
            "inp": inp_features,
            "material_type": str(getattr(summary, "material_type", "")),
            "geometry": dict(getattr(summary, "geometry", {}) or {}),
            "loading": dict(getattr(summary, "loading", {}) or {}),
            "mesh": dict(getattr(summary, "mesh_stats", {}) or {}),
            "parameters": dict(getattr(summary, "parameters", {}) or {}),
        },
        "results": {
            "indexed": result_features,
            "abaqus": dict(getattr(summary, "abaqus_results", {}) or {}),
            "odb_features": dict(getattr(summary, "odb_features", {}) or {}),
            "odb_extractions": list(getattr(summary, "odb_extractions", []) or []),
            "odb_frame_series": list(getattr(summary, "odb_frame_series", []) or []),
            "labels": _numeric_labels(summary),
        },
        "files": [_package_file_row(item) for item in files],
        "provenance": dict(getattr(summary, "provenance", {}) or {}),
        "quality": quality,
    }


def write_case_package(summary: Any) -> Path:
    package = build_case_package(summary)
    case_dir = Path(str(getattr(summary, "case_dir")))
    case_dir.mkdir(parents=True, exist_ok=True)
    path = case_dir / "case_package.json"
    path.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_case_package(case_dir: Path | str) -> dict[str, Any]:
    path = Path(case_dir)
    package_path = (
        path if path.name == "case_package.json" else path / "case_package.json"
    )
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CASE_PACKAGE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported case package schema_version: {payload.get('schema_version')}"
        )
    return payload


def quality_table_rows(quality: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "check": item.get("id", ""),
            "status": item.get("status", ""),
            "message": item.get("message", ""),
            "evidence": json.dumps(item.get("evidence", {}), ensure_ascii=False),
        }
        for item in quality.get("checks", [])
    ]


def _unit_preset_key(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-").replace(" ", "")
    aliases = {
        "mm-n-mpa": "mm-n-s-mpa",
        "mm-n-s-mpa": "mm-n-s-mpa",
        "mmnmpa": "mm-n-s-mpa",
        "m-kg-s-pa": "si",
        "si-m-kg-s-pa": "si",
        "si": "si",
    }
    return aliases.get(text, text)


def _nested_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("summary")
    return nested if isinstance(nested, dict) else payload


def _numeric_labels(summary: Any) -> dict[str, float]:
    labels: dict[str, float] = {}
    sources: list[dict[str, Any]] = []
    abaqus_results = getattr(summary, "abaqus_results", {}) or {}
    if isinstance(abaqus_results, dict):
        sources.append(abaqus_results)
    extractions = getattr(summary, "odb_extractions", []) or []
    if extractions and isinstance(extractions[-1], dict):
        aggregate = extractions[-1].get("aggregate", {})
        if isinstance(aggregate, dict):
            sources.insert(0, aggregate)
    result_summary = _nested_summary(getattr(summary, "result_features", {}) or {})
    sources.append(result_summary)
    for key in ("max_mises", "max_peeq", "max_displacement", "max_reaction_force"):
        for source in sources:
            value = source.get(key)
            if isinstance(value, (int, float)):
                labels[key] = float(value)
                break
    return labels


def _execution_state(
    *,
    has_solver_error: bool,
    has_completion: bool,
    odb_count: int,
    has_extraction: bool,
    has_model: bool,
) -> str:
    if has_solver_error:
        return "failed"
    if has_extraction and odb_count:
        return "postprocessed"
    if has_completion and odb_count:
        return "solved"
    if has_completion:
        return "completed_without_odb"
    if odb_count:
        return "odb_present_unverified"
    if has_model:
        return "prepared"
    return "unknown"


def _add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    status: str,
    weight: int,
    message: str,
    evidence: dict[str, Any],
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": status,
            "weight": int(weight),
            "message": message,
            "evidence": evidence,
        }
    )


def _quality_score(checks: list[dict[str, Any]]) -> int:
    factors = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    total = sum(int(item.get("weight", 0)) for item in checks)
    earned = sum(
        int(item.get("weight", 0)) * factors.get(str(item.get("status", "fail")), 0.0)
        for item in checks
    )
    return int(round(100.0 * earned / max(1, total)))


def _solver_message(status: str, execution_state: str) -> str:
    if status == "fail":
        return "Solver logs contain an error, abort, or termination signal."
    if status == "pass":
        return "Solver completion evidence is present."
    return f"Solver completion is not proven; indexed state is {execution_state}."


def _recommended_actions(blockers: list[str]) -> list[str]:
    messages = {
        "execution_evidence_not_solved": "Add a completed STA/MSG record and the matching ODB.",
        "solver_error_or_abort_detected": "Resolve the solver error before using this case as training truth.",
        "units_not_declared": "Declare the Abaqus unit system explicitly.",
        "material_not_identified": "Record the material model and material identity.",
        "mesh_not_identified": "Import a readable INP or provide mesh statistics.",
        "numeric_targets_missing": "Run ODB extraction for at least one numeric target.",
    }
    return [messages[item] for item in blockers if item in messages]


def _job_names(files: list[Any]) -> list[str]:
    result_extensions = {".odb", ".sta", ".msg", ".dat", ".log"}
    return sorted(
        {
            Path(str(getattr(item, "name", ""))).stem
            for item in files
            if str(getattr(item, "extension", "")).lower() in result_extensions
        },
        key=str.casefold,
    )


def _package_file_row(item: Any) -> dict[str, Any]:
    return {
        "relative_path": str(getattr(item, "relative_path", "")),
        "name": str(getattr(item, "name", "")),
        "extension": str(getattr(item, "extension", "")),
        "category": str(getattr(item, "category", "")),
        "size_bytes": int(getattr(item, "size_bytes", 0) or 0),
        "modified_at": str(getattr(item, "modified_at", "")),
        "fingerprint": str(getattr(item, "fingerprint", "")),
        "fingerprint_mode": str(getattr(item, "fingerprint_mode", "")),
    }
