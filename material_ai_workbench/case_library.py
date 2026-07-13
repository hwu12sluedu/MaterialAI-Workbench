"""Abaqus case-library utilities for MaterialAI Workbench.

The first version indexes existing simulation folders without copying large CAE
or ODB files.  Each case becomes a small, traceable asset that can later feed
similar-case retrieval, batch post-processing, and neural-network datasets.
"""

from __future__ import annotations

import json
import csv
import warnings
from dataclasses import asdict, dataclass, field, fields as dataclass_fields
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.config import CASES_ROOT as DEFAULT_CASES_ROOT


CASES_ROOT = DEFAULT_CASES_ROOT

MODEL_EXTENSIONS = {
    ".cae",
    ".inp",
    ".sat",
    ".step",
    ".stp",
    ".iges",
    ".igs",
    ".x_t",
    ".prt",
    ".asm",
}
RESULT_EXTENSIONS = {
    ".odb",
    ".sim",
    ".dat",
    ".sta",
    ".msg",
    ".log",
    ".fil",
    ".res",
    ".rpt",
}
DATA_EXTENSIONS = {".csv", ".txt", ".xlsx", ".xls", ".json", ".yaml", ".yml"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".svg"}
REPORT_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".md", ".html", ".htm"}
SCRIPT_EXTENSIONS = {".py", ".ps1", ".bat", ".cmd", ".for", ".f", ".f90", ".f95", ".m"}
IGNORED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    ".pytest_cache",
    ".ipynb_checkpoints",
}
LOAD_KEYWORDS = {"cload", "dload", "dsload", "pressure", "temperature", "film", "radiate"}
BOUNDARY_KEYWORDS = {"boundary", "initial conditions"}
INTERACTION_KEYWORDS = {"contact", "contact pair", "surface interaction", "tie"}
OUTPUT_KEYWORDS = {"output", "field output", "history output", "node output", "element output"}
TEXT_RESULT_EXTENSIONS = {".sta", ".msg", ".dat", ".log", ".rpt"}
SIMILARITY_FEATURE_KEYS = (
    "file_count",
    "model_file_count",
    "result_file_count",
    "inp_node_count",
    "inp_element_count",
    "csv_row_count",
    "max_mises",
    "max_peeq",
    "yield_strength",
    "youngs_modulus",
    "poisson_ratio",
    "fiber_volume_fraction",
    "hole_radius",
)


@dataclass
class CaseFile:
    path: str
    relative_path: str
    name: str
    extension: str
    category: str
    size_bytes: int
    modified_at: str


@dataclass
class CaseSummary:
    case_id: str
    title: str
    description: str
    tags: list[str]
    status: str
    source_folder: str
    created_at: str
    updated_at: str
    case_dir: str
    files: list[CaseFile] = field(default_factory=list)
    file_counts: dict[str, int] = field(default_factory=dict)
    total_size_bytes: int = 0
    key_files: dict[str, list[str]] = field(default_factory=dict)
    inp_features: dict[str, Any] = field(default_factory=dict)
    result_features: dict[str, Any] = field(default_factory=dict)
    odb_extractions: list[dict[str, Any]] = field(default_factory=list)
    odb_frame_series: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    lessons_learned: str = ""
    next_actions: str = ""
    # Structured metadata for ML training datasets
    material_type: str = ""
    geometry: dict[str, float] = field(default_factory=dict)
    loading: dict[str, Any] = field(default_factory=dict)
    mesh_stats: dict[str, int] = field(default_factory=dict)
    abaqus_results: dict[str, float] = field(default_factory=dict)
    odb_features: dict[str, float] = field(default_factory=dict)
    run_artifacts: dict[str, list[str]] = field(default_factory=dict)


def scan_case_folder(
    source_folder: Path | str,
    *,
    title: str,
    tags: list[str] | str | None = None,
    description: str = "",
    status: str = "success",
    parameters: dict[str, Any] | None = None,
    lessons_learned: str = "",
    next_actions: str = "",
    cases_root: Path = CASES_ROOT,
) -> CaseSummary:
    source = Path(source_folder).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Case source does not exist: {source}")

    normalized_tags = _normalize_tags(tags)
    case_id = _case_id(title)
    case_dir = _unique_case_dir(cases_root, case_id)
    case_dir.mkdir(parents=True, exist_ok=False)

    files = _scan_files(source)
    file_counts = _file_counts(files)
    total_size = sum(item.size_bytes for item in files)
    key_files = _key_files(files)
    inp_features = _extract_inp_features(files)
    result_features = _extract_result_features(files)
    geometry = _extract_geometry_from_inp(inp_features, parameters or {})
    loading = _extract_loading_from_inp(inp_features, parameters or {})
    mesh_stats = _extract_mesh_stats(inp_features)
    abaqus_results = _extract_abaqus_results(result_features)
    odb_features = _extract_odb_features_from_results(result_features)
    material_type = _infer_material_type(parameters or {}, inp_features, result_features)
    run_artifacts = _collect_run_artifacts(files)
    now = datetime.now().isoformat(timespec="seconds")
    summary = CaseSummary(
        case_id=case_dir.name,
        title=title.strip() or source.name,
        description=description.strip(),
        tags=normalized_tags,
        status=status.strip() or "success",
        source_folder=str(source),
        created_at=now,
        updated_at=now,
        case_dir=str(case_dir),
        files=files,
        file_counts=file_counts,
        total_size_bytes=total_size,
        key_files=key_files,
        inp_features=inp_features,
        result_features=result_features,
        lessons_learned=lessons_learned.strip(),
        next_actions=next_actions.strip(),
        parameters=parameters or {},
        material_type=material_type,
        geometry=geometry,
        loading=loading,
        mesh_stats=mesh_stats,
        abaqus_results=abaqus_results,
        odb_features=odb_features,
        run_artifacts=run_artifacts,
    )
    save_case_summary(summary)
    write_case_report(summary)
    return summary


def batch_import_cases(
    parent_folder: Path | str,
    *,
    tags: list[str] | None = None,
    status: str = "success",
    cases_root: Path = CASES_ROOT,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Scan a parent folder and import all sub-folders as individual cases.

    Returns a dict with imported, skipped, failed counts and case IDs.
    """
    parent = Path(parent_folder).expanduser().resolve()
    if not parent.is_dir():
        raise FileNotFoundError(f"Not a directory: {parent}")

    existing_sources: set[str] = set()
    if skip_existing:
        for case in list_cases(cases_root):
            existing_sources.add(str(Path(case.source_folder).resolve()))

    imported: list[str] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []

    subdirs = [d for d in parent.iterdir() if d.is_dir() and d.name not in IGNORED_DIR_NAMES]
    total = len(subdirs)

    for i, subdir in enumerate(sorted(subdirs), 1):
        source_str = str(subdir.resolve())
        if source_str in existing_sources:
            skipped.append(subdir.name)
            continue
        try:
            summary = scan_case_folder(
                subdir,
                title=subdir.name,
                tags=tags or [],
                status=status,
                cases_root=cases_root,
            )
            imported.append(summary.case_id)
        except Exception as exc:
            failed.append({"folder": subdir.name, "error": str(exc)})

    return {
        "parent_folder": str(parent),
        "total_found": total,
        "imported": len(imported),
        "skipped": len(skipped),
        "failed": len(failed),
        "imported_case_ids": imported,
        "skipped_folders": skipped,
        "failed_details": failed,
    }


def find_duplicate_cases(
    source_folder: Path | str,
    *,
    cases_root: Path = CASES_ROOT,
) -> list[dict[str, Any]]:
    """Check if a source folder has already been imported.

    Returns a list of matching cases with similarity info.
    """
    source = Path(source_folder).expanduser().resolve()
    source_str = str(source)

    duplicates: list[dict[str, Any]] = []
    for case in list_cases(cases_root):
        case_source = str(Path(case.source_folder).resolve())
        if case_source == source_str:
            duplicates.append({
                "case_id": case.case_id,
                "title": case.title,
                "source_folder": case_source,
                "status": case.status,
                "created_at": case.created_at,
                "match_type": "exact_path",
            })
            continue
        # Fuzzy: same folder name + similar file count
        if Path(case_source).name == source.name:
            if case.file_counts:
                dup_file_count = sum(1 for f in source.rglob("*") if f.is_file())
                if abs(case.file_counts.get("total", 0) - dup_file_count) <= 3:
                    duplicates.append({
                        "case_id": case.case_id,
                        "title": case.title,
                        "source_folder": case_source,
                        "status": case.status,
                        "created_at": case.created_at,
                        "match_type": "fuzzy_name_size",
                    })

    return duplicates


def save_case_summary(summary: CaseSummary) -> Path:
    case_dir = Path(summary.case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    summary.updated_at = datetime.now().isoformat(timespec="seconds")
    path = case_dir / "case_summary.json"
    path.write_text(json.dumps(_summary_to_dict(summary), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_case_report(summary: CaseSummary) -> Path:
    case_dir = Path(summary.case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    path = case_dir / "case_report.md"
    path.write_text(_markdown_report(summary), encoding="utf-8")
    return path


def list_cases(cases_root: Path = CASES_ROOT) -> list[CaseSummary]:
    if not cases_root.exists():
        return []
    cases: list[CaseSummary] = []
    for summary_path in cases_root.glob("*/case_summary.json"):
        try:
            cases.append(load_case_summary(summary_path.parent))
        except Exception:
            continue
    return sorted(cases, key=lambda item: item.updated_at, reverse=True)


def filter_cases(
    cases: list[CaseSummary],
    *,
    tags: list[str] | str | None = None,
    statuses: list[str] | tuple[str, ...] | None = None,
    material_types: list[str] | tuple[str, ...] | None = None,
    case_types: list[str] | tuple[str, ...] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[CaseSummary]:
    tag_terms = _normalize_filter_terms(tags)
    status_set = {str(item).strip().lower() for item in (statuses or []) if str(item).strip()}
    material_set = {str(item).strip().lower() for item in (material_types or []) if str(item).strip()}
    case_type_set = {str(item).strip().lower() for item in (case_types or []) if str(item).strip()}
    start = _date_key(date_from)
    end = _date_key(date_to)

    result: list[CaseSummary] = []
    for case in cases:
        if status_set and case.status.lower() not in status_set:
            continue
        material_type = _case_material_type(case)
        if material_set and material_type not in material_set:
            continue
        inferred_case_type = infer_case_type(case)
        if case_type_set and inferred_case_type not in case_type_set:
            continue
        updated = _date_key(case.updated_at)
        if start and updated and updated < start:
            continue
        if end and updated and updated > end:
            continue
        haystack = " ".join([case.title, case.description, case.source_folder, " ".join(case.tags)]).lower()
        if tag_terms and not all(term in haystack for term in tag_terms):
            continue
        result.append(case)
    return result


def infer_case_type(case: CaseSummary) -> str:
    text = " ".join(
        [
            case.title,
            case.description,
            case.source_folder,
            " ".join(case.tags),
            case.material_type,
            str((case.parameters or {}).get("material_type", "")),
        ]
    ).lower()
    if any(term in text for term in ("composite", "rve", "fiber", "laminate", "复合")):
        return "composite"
    if any(term in text for term in ("j2", "hill", "barlat", "steel", "metal", "plastic", "金属")):
        return "metal"
    return "unknown"


def find_similar_cases(
    query: CaseSummary | Path | str,
    *,
    cases: list[CaseSummary] | None = None,
    cases_root: Path = CASES_ROOT,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rank archived cases by simple normalized numeric feature distance."""

    query_case = query if isinstance(query, CaseSummary) else load_case_summary(query)
    candidates = [case for case in (cases or list_cases(cases_root)) if case.case_id != query_case.case_id]
    if not candidates:
        return []
    query_vector = _case_similarity_vector(query_case)
    candidate_vectors = [_case_similarity_vector(case) for case in candidates]
    scales = _feature_scales([query_vector, *candidate_vectors])
    rows = []
    for case, vector in zip(candidates, candidate_vectors):
        distance = _normalized_distance(query_vector, vector, scales)
        rows.append(
            {
                "case_id": case.case_id,
                "title": case.title,
                "status": case.status,
                "tags": ", ".join(case.tags),
                "distance": distance,
                "similarity": 1.0 / (1.0 + distance),
                "case_dir": case.case_dir,
            }
        )
    return sorted(rows, key=lambda item: item["distance"])[: max(1, int(top_k))]


def load_case_summary(case_dir: Path | str) -> CaseSummary:
    path = Path(case_dir)
    summary_path = path if path.name == "case_summary.json" else path / "case_summary.json"
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    files = [_case_file_from_dict(item) for item in data.get("files", []) if isinstance(item, dict)]
    data["files"] = files
    known = {item.name for item in dataclass_fields(CaseSummary)}
    unknown = sorted(set(data) - known)
    if unknown:
        warnings.warn(
            f"Ignoring unknown fields in {summary_path.name}: {', '.join(unknown)}",
            RuntimeWarning,
            stacklevel=2,
        )
    return CaseSummary(**{key: value for key, value in data.items() if key in known})


def case_table_rows(cases: list[CaseSummary]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        rows.append(
            {
                "case": case.case_id,
                "标题": case.title,
                "状态": case.status,
                "标签": ", ".join(case.tags),
                "文件数": len(case.files),
                "ODB": case.file_counts.get("result", 0),
                "数据": case.file_counts.get("data", 0),
                "报告": case.file_counts.get("report", 0),
                "大小(MB)": round(case.total_size_bytes / (1024 * 1024), 3),
                "更新时间": case.updated_at,
            }
        )
    return rows


def file_table_rows(summary: CaseSummary, category: str | None = None) -> list[dict[str, Any]]:
    files = summary.files
    if category and category != "all":
        files = [item for item in files if item.category == category]
    rows = []
    for item in files:
        rows.append(
            {
                "类别": item.category,
                "文件名": item.name,
                "扩展名": item.extension,
                "相对路径": item.relative_path,
                "大小(MB)": round(item.size_bytes / (1024 * 1024), 3),
                "修改时间": item.modified_at,
            }
        )
    return rows


def inp_feature_table_rows(summary: CaseSummary) -> list[dict[str, Any]]:
    rows = []
    for feature in (summary.inp_features or {}).get("files", []):
        rows.append(
            {
                "INP文件": feature.get("relative_path", ""),
                "节点(估算)": feature.get("estimated_node_count", 0),
                "单元(估算)": feature.get("estimated_element_count", 0),
                "材料数": len(feature.get("materials", [])),
                "Step数": len(feature.get("steps", [])),
                "单元类型": ", ".join(feature.get("element_types", [])),
                "载荷": ", ".join(feature.get("load_keywords", [])),
                "边界": ", ".join(feature.get("boundary_keywords", [])),
                "输出": ", ".join(feature.get("output_keywords", [])),
            }
        )
    return rows


def result_feature_table_rows(summary: CaseSummary) -> list[dict[str, Any]]:
    features = summary.result_features or {}
    rows = []
    for item in features.get("csv_files", []):
        signals = []
        for label, key in (("Max Mises", "max_mises"), ("Max PEEQ", "max_peeq"), ("Max U", "max_displacement"), ("Max RF", "max_reaction_force")):
            value = item.get("signals", {}).get(key)
            if value is not None:
                signals.append(f"{label}={value:.6g}")
        rows.append(
            {
                "类型": "csv",
                "文件": item.get("relative_path", ""),
                "行数": item.get("row_count", 0),
                "指标": "; ".join(signals) or "未识别关键指标",
                "警告": "",
                "说明": f"数值列 {len(item.get('numeric_columns', []))} 个",
            }
        )
    for item in features.get("odb_files", []):
        rows.append(
            {
                "类型": "odb",
                "文件": item.get("relative_path", ""),
                "行数": "",
                "指标": f"{item.get('size_mb', 0):.3f} MB",
                "警告": "",
                "说明": "已索引路径；完整场变量需 Abaqus MCP/ODB 读取",
            }
        )
    for item in features.get("log_files", []):
        rows.append(
            {
                "类型": "log",
                "文件": item.get("relative_path", ""),
                "行数": item.get("line_count", 0),
                "指标": item.get("status_hint", "unknown"),
                "警告": f"W{item.get('warning_count', 0)} / E{item.get('error_count', 0)}",
                "说明": "日志/状态文件文本扫描",
            }
        )
    return rows


def odb_extraction_table_rows(summary: CaseSummary) -> list[dict[str, Any]]:
    rows = []
    for item in summary.odb_extractions or []:
        aggregate = item.get("aggregate", {})
        rows.append(
            {
                "时间": item.get("created_at", ""),
                "ODB": item.get("odb_name", ""),
                "字段数": aggregate.get("field_count", 0),
                "Max Mises": aggregate.get("max_mises"),
                "Max PEEQ": aggregate.get("max_peeq"),
                "Max U": aggregate.get("max_displacement"),
                "Max RF": aggregate.get("max_reaction_force"),
                "报告": item.get("report_path", ""),
            }
        )
    return rows


def odb_frame_series_table_rows(summary: CaseSummary) -> list[dict[str, Any]]:
    rows = []
    for item in summary.odb_frame_series or []:
        rows.append(
            {
                "时间": item.get("created_at", ""),
                "ODB": item.get("odb_name", ""),
                "行数": item.get("row_count", 0),
                "Step数": item.get("step_count", 0),
                "字段": ", ".join(item.get("fields_requested", [])),
                "后端": item.get("backend_used", ""),
                "CSV": item.get("csv_path", ""),
                "报告": item.get("report_path", ""),
            }
        )
    return rows


def append_odb_extraction(summary: CaseSummary, extraction: dict[str, Any]) -> CaseSummary:
    summary.odb_extractions.append(extraction)
    save_case_summary(summary)
    write_case_report(summary)
    return summary


def append_odb_frame_series(summary: CaseSummary, series: dict[str, Any]) -> CaseSummary:
    summary.odb_frame_series.append(series)
    save_case_summary(summary)
    write_case_report(summary)
    return summary


def extract_inp_features(inp_path: Path | str) -> dict[str, Any]:
    path = Path(inp_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"INP file does not exist: {path}")
    if path.suffix.lower() != ".inp":
        raise ValueError(f"Expected .inp file: {path}")
    return _parse_inp_file(path, path.name)


def extract_csv_result_features(csv_path: Path | str) -> dict[str, Any]:
    path = Path(csv_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"CSV result file does not exist: {path}")
    return _parse_csv_result_file(path, path.name)


def _scan_files(source: Path) -> list[CaseFile]:
    if source.is_file():
        return [_case_file_from_path(source, source.parent)]

    files: list[CaseFile] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.relative_to(source).parts[:-1]):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(_case_file_from_path(path, source))
    return files


def _case_file_from_path(path: Path, root: Path) -> CaseFile:
    stat = path.stat()
    suffix = path.suffix.lower()
    return CaseFile(
        path=str(path.resolve()),
        relative_path=str(path.relative_to(root)),
        name=path.name,
        extension=suffix,
        category=_categorize_extension(suffix),
        size_bytes=int(stat.st_size),
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    )


def _extract_inp_features(files: list[CaseFile]) -> dict[str, Any]:
    inp_files = [item for item in files if item.extension == ".inp"]
    if not inp_files:
        return {}

    parsed = []
    for item in inp_files:
        try:
            parsed.append(_parse_inp_file(Path(item.path), item.relative_path))
        except Exception as exc:
            parsed.append(
                {
                    "path": item.path,
                    "relative_path": item.relative_path,
                    "parse_error": str(exc),
                    "estimated_node_count": 0,
                    "estimated_element_count": 0,
                    "materials": [],
                    "steps": [],
                    "element_types": [],
                    "load_keywords": [],
                    "boundary_keywords": [],
                    "interaction_keywords": [],
                    "output_keywords": [],
                    "include_files": [],
                    "keyword_counts": {},
                }
            )

    summary = {
        "inp_file_count": len(parsed),
        "estimated_node_count": sum(int(item.get("estimated_node_count", 0)) for item in parsed),
        "estimated_element_count": sum(int(item.get("estimated_element_count", 0)) for item in parsed),
        "materials": _unique_sorted(value for item in parsed for value in item.get("materials", [])),
        "steps": _unique_sorted(value for item in parsed for value in item.get("steps", [])),
        "element_types": _unique_sorted(value for item in parsed for value in item.get("element_types", [])),
        "load_keywords": _unique_sorted(value for item in parsed for value in item.get("load_keywords", [])),
        "boundary_keywords": _unique_sorted(value for item in parsed for value in item.get("boundary_keywords", [])),
        "interaction_keywords": _unique_sorted(value for item in parsed for value in item.get("interaction_keywords", [])),
        "output_keywords": _unique_sorted(value for item in parsed for value in item.get("output_keywords", [])),
        "include_files": _unique_sorted(value for item in parsed for value in item.get("include_files", [])),
        "parse_error_count": sum(1 for item in parsed if item.get("parse_error")),
    }
    return {"summary": summary, "files": parsed}


def _extract_result_features(files: list[CaseFile]) -> dict[str, Any]:
    csv_files = []
    for item in files:
        if item.extension != ".csv":
            continue
        try:
            csv_files.append(_parse_csv_result_file(Path(item.path), item.relative_path))
        except Exception as exc:
            csv_files.append(
                {
                    "path": item.path,
                    "relative_path": item.relative_path,
                    "parse_error": str(exc),
                    "row_count": 0,
                    "numeric_columns": [],
                    "signals": {},
                }
            )

    odb_files = [
        {
            "path": item.path,
            "relative_path": item.relative_path,
            "size_mb": round(item.size_bytes / (1024 * 1024), 6),
            "modified_at": item.modified_at,
            "status": "indexed_metadata_only",
        }
        for item in files
        if item.extension == ".odb"
    ]

    log_files = []
    for item in files:
        if item.extension not in TEXT_RESULT_EXTENSIONS:
            continue
        try:
            log_files.append(_parse_text_result_file(Path(item.path), item.relative_path))
        except Exception as exc:
            log_files.append(
                {
                    "path": item.path,
                    "relative_path": item.relative_path,
                    "parse_error": str(exc),
                    "line_count": 0,
                    "warning_count": 0,
                    "error_count": 0,
                    "status_hint": "read_error",
                }
            )

    if not csv_files and not odb_files and not log_files:
        return {}

    signals = [_signals_from_csv(item) for item in csv_files]
    summary = {
        "csv_file_count": len(csv_files),
        "odb_file_count": len(odb_files),
        "log_file_count": len(log_files),
        "csv_row_count": sum(int(item.get("row_count", 0)) for item in csv_files),
        "warning_count": sum(int(item.get("warning_count", 0)) for item in log_files),
        "error_count": sum(int(item.get("error_count", 0)) for item in log_files),
        "max_mises": _max_optional(signal.get("max_mises") for signal in signals),
        "max_peeq": _max_optional(signal.get("max_peeq") for signal in signals),
        "max_displacement": _max_optional(signal.get("max_displacement") for signal in signals),
        "max_reaction_force": _max_optional(signal.get("max_reaction_force") for signal in signals),
        "odb_files": [item["path"] for item in odb_files],
        "parse_error_count": sum(
            1
            for item in [*csv_files, *log_files]
            if item.get("parse_error")
        ),
    }
    return {"summary": summary, "csv_files": csv_files, "odb_files": odb_files, "log_files": log_files}


def _parse_csv_result_file(path: Path, relative_path: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = _guess_delimiter(sample)
        reader = csv.DictReader(handle, delimiter=delimiter)
        columns = [column.strip() for column in (reader.fieldnames or []) if column]
        stats: dict[str, dict[str, float]] = {}
        row_count = 0
        for row in reader:
            row_count += 1
            for column, raw_value in row.items():
                if column is None:
                    continue
                value = _try_float(raw_value)
                if value is None:
                    continue
                key = column.strip()
                if not key:
                    continue
                item = stats.setdefault(key, {"count": 0.0, "min": value, "max": value, "sum": 0.0})
                item["count"] += 1.0
                item["min"] = min(item["min"], value)
                item["max"] = max(item["max"], value)
                item["sum"] += value

    numeric_columns = []
    for column, item in sorted(stats.items()):
        count = item["count"]
        numeric_columns.append(
            {
                "name": column,
                "count": int(count),
                "min": item["min"],
                "max": item["max"],
                "mean": item["sum"] / count if count else None,
            }
        )

    signals = _signals_from_numeric_columns(numeric_columns)
    return {
        "path": str(path),
        "relative_path": relative_path,
        "delimiter": delimiter,
        "row_count": row_count,
        "columns": columns,
        "numeric_columns": numeric_columns,
        "signals": signals,
    }


def _parse_text_result_file(path: Path, relative_path: str, max_lines: int = 100_000) -> dict[str, Any]:
    warning_count = 0
    error_count = 0
    completed = False
    aborted = False
    truncated = False
    line_count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_count, line in enumerate(handle, start=1):
            if line_count > max_lines:
                truncated = True
                break
            lower = line.lower()
            if "warning" in lower:
                warning_count += 1
            if "error" in lower or "exception" in lower:
                error_count += 1
            if "aborted" in lower or "terminated" in lower:
                aborted = True
            if "completed" in lower or "successfully" in lower:
                completed = True

    if aborted or error_count:
        status_hint = "error_or_aborted"
    elif completed:
        status_hint = "completed"
    elif warning_count:
        status_hint = "warning"
    else:
        status_hint = "unknown"

    return {
        "path": str(path),
        "relative_path": relative_path,
        "line_count": min(line_count, max_lines),
        "warning_count": warning_count,
        "error_count": error_count,
        "status_hint": status_hint,
        "truncated": truncated,
    }


def _guess_delimiter(sample: str) -> str:
    if sample.count(";") > sample.count(","):
        return ";"
    if sample.count("\t") > sample.count(","):
        return "\t"
    return ","


def _try_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("D", "E").replace("d", "e").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        before, after = text.rsplit(",", 1)
        if after.isdigit() and len(after) == 3 and before.replace("-", "").isdigit():
            text = before + after
        else:
            text = before + "." + after
    try:
        return float(text)
    except ValueError:
        return None


def _case_file_from_dict(data: dict[str, Any]) -> CaseFile:
    known = {item.name for item in dataclass_fields(CaseFile)}
    return CaseFile(**{key: value for key, value in data.items() if key in known})


def _signals_from_csv(item: dict[str, Any]) -> dict[str, float | None]:
    return item.get("signals") or _signals_from_numeric_columns(item.get("numeric_columns", []))


def _signals_from_numeric_columns(numeric_columns: list[dict[str, Any]]) -> dict[str, float | None]:
    return {
        "max_mises": _metric_from_columns(numeric_columns, ("mises", "von_mises", "s_mises")),
        "max_peeq": _metric_from_columns(numeric_columns, ("peeq", "eqps", "plastic_strain")),
        "max_displacement": _metric_from_columns(numeric_columns, ("umag", "displacement", "disp", "u_"), use_abs=True),
        "max_reaction_force": _metric_from_columns(numeric_columns, ("rf", "reaction"), use_abs=True),
    }


def _metric_from_columns(
    numeric_columns: list[dict[str, Any]],
    keywords: tuple[str, ...],
    *,
    use_abs: bool = False,
) -> float | None:
    values: list[float] = []
    for column in numeric_columns:
        name = str(column.get("name", "")).lower().replace(" ", "_")
        if not any(keyword in name for keyword in keywords):
            continue
        min_value = column.get("min")
        max_value = column.get("max")
        if isinstance(min_value, (int, float)) and isinstance(max_value, (int, float)):
            if use_abs:
                values.append(max(abs(float(min_value)), abs(float(max_value))))
            else:
                values.append(float(max_value))
    return max(values) if values else None


def _case_similarity_vector(case: CaseSummary) -> dict[str, float]:
    inp_summary = (case.inp_features or {}).get("summary", {})
    result_summary = (case.result_features or {}).get("summary", {})
    params = case.parameters or {}
    geometry = case.geometry or {}
    loading = case.loading or {}
    return {
        "file_count": float(len(case.files)),
        "model_file_count": float(case.file_counts.get("model", 0)),
        "result_file_count": float(case.file_counts.get("result", 0)),
        "inp_node_count": float(inp_summary.get("estimated_node_count", 0) or 0),
        "inp_element_count": float(inp_summary.get("estimated_element_count", 0) or 0),
        "csv_row_count": float(result_summary.get("csv_row_count", 0) or 0),
        "max_mises": float(result_summary.get("max_mises", 0) or 0),
        "max_peeq": float(result_summary.get("max_peeq", 0) or 0),
        "yield_strength": _float_or_zero(params.get("yield_strength", loading.get("yield_strength"))),
        "youngs_modulus": _float_or_zero(params.get("youngs_modulus")),
        "poisson_ratio": _float_or_zero(params.get("poisson_ratio")),
        "fiber_volume_fraction": _float_or_zero(params.get("fiber_volume_fraction", geometry.get("fiber_volume_fraction"))),
        "hole_radius": _float_or_zero(params.get("hole_radius", geometry.get("hole_radius"))),
    }


def _feature_scales(vectors: list[dict[str, float]]) -> dict[str, float]:
    scales: dict[str, float] = {}
    for key in SIMILARITY_FEATURE_KEYS:
        values = [abs(float(vector.get(key, 0.0))) for vector in vectors]
        scales[key] = max(max(values), 1.0)
    return scales


def _case_material_type(case: CaseSummary) -> str:
    return str(case.material_type or (case.parameters or {}).get("material_type", "")).strip().lower()


def _normalized_distance(left: dict[str, float], right: dict[str, float], scales: dict[str, float]) -> float:
    total = 0.0
    used = 0
    for key in SIMILARITY_FEATURE_KEYS:
        scale = scales.get(key, 1.0) or 1.0
        total += ((left.get(key, 0.0) - right.get(key, 0.0)) / scale) ** 2
        used += 1
    return float((total / max(1, used)) ** 0.5)


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _max_optional(values: Any) -> float | None:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    return max(clean) if clean else None


def _parse_inp_file(path: Path, relative_path: str) -> dict[str, Any]:
    keyword_counts: dict[str, int] = {}
    materials: list[str] = []
    steps: list[str] = []
    element_types: list[str] = []
    include_files: list[str] = []
    load_keywords: list[str] = []
    boundary_keywords: list[str] = []
    interaction_keywords: list[str] = []
    output_keywords: list[str] = []
    node_count = 0
    element_count = 0
    current_block: str | None = None
    line_count = 0

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line_count += 1
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("**"):
                continue

            if stripped.startswith("*"):
                keyword = _inp_keyword(stripped)
                if not keyword:
                    current_block = None
                    continue

                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
                parameters = _inp_parameters(stripped)
                if keyword == "node":
                    current_block = "node"
                elif keyword == "element":
                    current_block = "element"
                    if parameters.get("type"):
                        element_types.append(parameters["type"].upper())
                else:
                    current_block = None

                if keyword == "material" and parameters.get("name"):
                    materials.append(parameters["name"])
                elif keyword == "step" and parameters.get("name"):
                    steps.append(parameters["name"])
                elif keyword == "include" and parameters.get("input"):
                    include_files.append(parameters["input"])

                if keyword in LOAD_KEYWORDS:
                    load_keywords.append(keyword)
                if keyword in BOUNDARY_KEYWORDS:
                    boundary_keywords.append(keyword)
                if keyword in INTERACTION_KEYWORDS:
                    interaction_keywords.append(keyword)
                if keyword in OUTPUT_KEYWORDS:
                    output_keywords.append(keyword)
                continue

            if current_block == "node":
                node_count += 1
            elif current_block == "element":
                element_count += 1

    return {
        "path": str(path),
        "relative_path": relative_path,
        "line_count": line_count,
        "estimated_node_count": node_count,
        "estimated_element_count": element_count,
        "materials": _unique_sorted(materials),
        "steps": _unique_sorted(steps),
        "element_types": _unique_sorted(element_types),
        "include_files": _unique_sorted(include_files),
        "load_keywords": _unique_sorted(load_keywords),
        "boundary_keywords": _unique_sorted(boundary_keywords),
        "interaction_keywords": _unique_sorted(interaction_keywords),
        "output_keywords": _unique_sorted(output_keywords),
        "keyword_counts": dict(sorted(keyword_counts.items())),
    }


def _inp_keyword(line: str) -> str:
    content = line.strip()[1:].strip()
    if not content:
        return ""
    return content.split(",", 1)[0].strip().lower()


def _inp_parameters(line: str) -> dict[str, str]:
    content = line.strip()[1:].strip()
    parts = content.split(",")[1:]
    params: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip().strip('"').strip("'")
        if key:
            params[key] = value
    return params


def _unique_sorted(values: Any) -> list[str]:
    result = []
    seen = set()
    for value in values:
        item = str(value).strip()
        if item and item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    return sorted(result, key=lambda item: item.lower())


def _categorize_extension(extension: str) -> str:
    if extension in MODEL_EXTENSIONS:
        return "model"
    if extension in RESULT_EXTENSIONS:
        return "result"
    if extension in DATA_EXTENSIONS:
        return "data"
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in REPORT_EXTENSIONS:
        return "report"
    if extension in SCRIPT_EXTENSIONS:
        return "script"
    return "other"


def _file_counts(files: list[CaseFile]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in files:
        counts[item.category] = counts.get(item.category, 0) + 1
    return dict(sorted(counts.items()))


def _key_files(files: list[CaseFile]) -> dict[str, list[str]]:
    keys: dict[str, list[str]] = {key: [] for key in ("model", "result", "data", "image", "report", "script")}
    for item in files:
        if item.category in keys:
            keys[item.category].append(item.relative_path)
    return {key: values[:20] for key, values in keys.items() if values}


def _normalize_tags(tags: list[str] | str | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = tags.replace("，", ",").replace(";", ",").split(",")
    else:
        raw = tags
    result = []
    seen = set()
    for item in raw:
        tag = str(item).strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            result.append(tag)
    return result


def _normalize_filter_terms(values: list[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw = values.replace(";", ",").replace("，", ",").split(",")
    else:
        raw = values
    return [str(item).strip().lower() for item in raw if str(item).strip()]


def _date_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:10]


def _case_id(title: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in title.strip())
    safe = "_".join(part for part in safe.split("_") if part)
    safe = safe or "abaqus_case"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{safe[:60]}"


def _unique_case_dir(cases_root: Path, case_id: str) -> Path:
    base = cases_root / case_id
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = cases_root / f"{case_id}_{idx}"
        if not candidate.exists():
            return candidate
        idx += 1


def _extract_geometry_from_inp(
    inp_features: dict[str, Any], parameters: dict[str, Any]
) -> dict[str, float]:
    """Extract geometry metadata from INP features and parameters."""
    geom: dict[str, float] = {}
    for key in ("length", "width", "thickness", "hole_radius", "fiber_volume_fraction"):
        if key in parameters:
            try:
                geom[key] = float(parameters[key])
            except (TypeError, ValueError):
                pass
    inp_summary = _inp_summary(inp_features)
    node_count = inp_summary.get("estimated_node_count", 0) or 0
    elem_count = inp_summary.get("estimated_element_count", 0) or 0
    if node_count:
        geom["estimated_node_count"] = float(node_count)
    if elem_count:
        geom["estimated_element_count"] = float(elem_count)
    return geom


def _extract_loading_from_inp(
    inp_features: dict[str, Any], parameters: dict[str, Any]
) -> dict[str, Any]:
    """Extract loading metadata."""
    load: dict[str, Any] = {}
    for key in ("applied_strain", "applied_stress", "load_type", "yield_strength"):
        if key in parameters:
            try:
                load[key] = float(parameters[key])
            except (TypeError, ValueError):
                load[key] = parameters[key]
    return load


def _extract_mesh_stats(inp_features: dict[str, Any]) -> dict[str, int]:
    """Extract mesh statistics."""
    inp_summary = _inp_summary(inp_features)
    return {
        "node_count": int(inp_summary.get("estimated_node_count", 0) or 0),
        "element_count": int(inp_summary.get("estimated_element_count", 0) or 0),
    }


def _extract_abaqus_results(result_features: dict[str, Any]) -> dict[str, float]:
    """Extract key Abaqus result values."""
    summary = result_features.get("summary", {}) if isinstance(result_features, dict) else {}
    results: dict[str, float] = {}
    for key in ("max_mises", "max_peeq", "max_displacement", "max_reaction_force"):
        val = summary.get(key)
        if val is not None:
            try:
                results[key] = float(val)
            except (TypeError, ValueError):
                pass
    return results


def _extract_odb_features_from_results(result_features: dict[str, Any]) -> dict[str, float]:
    """Extract ODB feature summary."""
    summary = result_features.get("summary", {}) if isinstance(result_features, dict) else {}
    feats: dict[str, float] = {}
    for key in ("odb_file_count", "csv_file_count", "log_file_count", "csv_row_count",
                "warning_count", "error_count"):
        val = summary.get(key)
        if val is not None:
            try:
                feats[key] = float(val)
            except (TypeError, ValueError):
                pass
    return feats


def _infer_material_type(
    parameters: dict[str, Any],
    inp_features: dict[str, Any],
    result_features: dict[str, Any],
) -> str:
    """Infer material type from available metadata."""
    if "material_type" in parameters:
        return str(parameters["material_type"]).strip().lower()
    materials = _inp_summary(inp_features).get("materials", [])
    if materials:
        mat_names = " ".join(str(m).lower() for m in materials)
        if "composite" in mat_names or "ud_cfrp" in mat_names or "rve" in mat_names:
            return "composite"
        if "barlat" in mat_names:
            return "barlat"
        if "hill" in mat_names:
            return "hill"
        if "j2" in mat_names:
            return "j2"
        if any(term in mat_names for term in ("steel", "aluminum", "aluminium", "metal")):
            return "metal"
    return "unknown"


def _inp_summary(inp_features: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(inp_features, dict):
        return {}
    summary = inp_features.get("summary")
    return summary if isinstance(summary, dict) else inp_features


def _collect_run_artifacts(files: list[CaseFile]) -> dict[str, list[str]]:
    """Collect key run artifact file paths by category."""
    artifacts: dict[str, list[str]] = {}
    for f in files:
        cat = f.category
        if cat not in artifacts:
            artifacts[cat] = []
        artifacts[cat].append(f.path)
    return artifacts


def _summary_to_dict(summary: CaseSummary) -> dict[str, Any]:
    return asdict(summary)


def _markdown_report(summary: CaseSummary) -> str:
    counts = "\n".join(f"- {key}: {value}" for key, value in summary.file_counts.items()) or "- 暂无文件"
    tags = ", ".join(summary.tags) if summary.tags else "未标注"
    inp_section = _inp_features_markdown(summary)
    result_section = _result_features_markdown(summary)
    extraction_section = _odb_extractions_markdown(summary)
    key_sections = []
    for category, values in summary.key_files.items():
        body = "\n".join(f"- `{value}`" for value in values) or "- 无"
        key_sections.append(f"### {category}\n\n{body}")
    key_files = "\n\n".join(key_sections) if key_sections else "暂无关键文件"
    return f"""# Abaqus 案例报告：{summary.title}

## 基本信息

- Case ID: `{summary.case_id}`
- 状态: `{summary.status}`
- 标签: {tags}
- 来源目录: `{summary.source_folder}`
- 创建时间: `{summary.created_at}`
- 更新时间: `{summary.updated_at}`

## 案例说明

{summary.description or "暂无说明"}

## 文件统计

- 文件总数: `{len(summary.files)}`
- 总大小: `{summary.total_size_bytes / (1024 * 1024):.3f} MB`

{counts}

## INP 特征摘要

{inp_section}

## 结果特征摘要

{result_section}

## ODB 深度后处理

{extraction_section}

## 关键文件

{key_files}

## 经验记录

{summary.lessons_learned or "暂无记录"}

## 后续动作

{summary.next_actions or "暂无"}

## 说明

当前案例库 v0 只索引源文件路径，不复制大型 `.cae` / `.odb` 文件。后续可以在此基础上增加相似案例检索、批量仿真和神经网络训练数据生成。
"""


def _inp_features_markdown(summary: CaseSummary) -> str:
    features = summary.inp_features or {}
    if not features:
        return "未发现 `.inp` 文件。"

    aggregate = features.get("summary", {})
    lines = [
        f"- INP 文件数: `{aggregate.get('inp_file_count', 0)}`",
        f"- 节点数估算: `{aggregate.get('estimated_node_count', 0)}`",
        f"- 单元数估算: `{aggregate.get('estimated_element_count', 0)}`",
        f"- 材料: `{', '.join(aggregate.get('materials', [])) or '未识别'}`",
        f"- Step: `{', '.join(aggregate.get('steps', [])) or '未识别'}`",
        f"- 单元类型: `{', '.join(aggregate.get('element_types', [])) or '未识别'}`",
        f"- 载荷关键字: `{', '.join(aggregate.get('load_keywords', [])) or '未识别'}`",
        f"- 边界关键字: `{', '.join(aggregate.get('boundary_keywords', [])) or '未识别'}`",
    ]
    if aggregate.get("parse_error_count"):
        lines.append(f"- 解析异常文件数: `{aggregate.get('parse_error_count')}`")
    return "\n".join(lines)


def _result_features_markdown(summary: CaseSummary) -> str:
    features = summary.result_features or {}
    if not features:
        return "未发现 ODB/CSV/日志结果文件。"

    aggregate = features.get("summary", {})
    lines = [
        f"- CSV 文件数: `{aggregate.get('csv_file_count', 0)}`",
        f"- ODB 文件数: `{aggregate.get('odb_file_count', 0)}`",
        f"- 日志文件数: `{aggregate.get('log_file_count', 0)}`",
        f"- CSV 行数: `{aggregate.get('csv_row_count', 0)}`",
        f"- Max Mises: `{aggregate.get('max_mises')}`",
        f"- Max PEEQ: `{aggregate.get('max_peeq')}`",
        f"- Warning/Error: `{aggregate.get('warning_count', 0)} / {aggregate.get('error_count', 0)}`",
    ]
    return "\n".join(lines)


def _odb_extractions_markdown(summary: CaseSummary) -> str:
    if not summary.odb_extractions and not summary.odb_frame_series:
        return "暂无 ODB 深度后处理记录。"

    lines = []
    for item in summary.odb_extractions:
        aggregate = item.get("aggregate", {})
        lines.append(
            "- `{time}` `{odb}`: Max Mises=`{mises}`, Max PEEQ=`{peeq}`, report=`{report}`".format(
                time=item.get("created_at", ""),
                odb=item.get("odb_name", ""),
                mises=aggregate.get("max_mises"),
                peeq=aggregate.get("max_peeq"),
                report=item.get("report_path", ""),
            )
        )
    for item in summary.odb_frame_series:
        lines.append(
            "- `{time}` `{odb}`: frame series rows=`{rows}`, csv=`{csv}`".format(
                time=item.get("created_at", ""),
                odb=item.get("odb_name", ""),
                rows=item.get("row_count", 0),
                csv=item.get("csv_path", ""),
            )
        )
    return "\n".join(lines)
