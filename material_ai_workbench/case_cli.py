"""Command-line interface for Abaqus case ingestion and dataset governance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from material_ai_workbench.case_library import (
    CASES_ROOT,
    find_similar_cases,
    list_cases,
    load_case_summary,
    scan_case_folder,
)
from material_ai_workbench.case_package import build_case_package
from material_ai_workbench.config import DATASETS_ROOT
from material_ai_workbench.dataset_export import export_case_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="materialai-case",
        description="Import, inspect and govern Abaqus simulation cases.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser(
        "import", help="Index one Abaqus folder or a standalone INP file."
    )
    import_parser.add_argument("source", type=Path)
    import_parser.add_argument("--title", default="")
    import_parser.add_argument("--tags", default="")
    import_parser.add_argument("--description", default="")
    import_parser.add_argument("--status", default="candidate")
    import_parser.add_argument("--units", default="mm-N-s-MPa")
    import_parser.add_argument("--no-units", action="store_true")
    import_parser.add_argument("--solver-version", default="")
    import_parser.add_argument(
        "--source-mode",
        choices=("reference", "copy", "generated", "uploaded"),
        default="reference",
    )
    _add_cases_root(import_parser)

    list_parser = subparsers.add_parser("list", help="List indexed cases.")
    list_parser.add_argument("--limit", type=int, default=50)
    _add_cases_root(list_parser)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Show a case package and its quality-gate result."
    )
    inspect_parser.add_argument("case")
    _add_cases_root(inspect_parser)

    search_parser = subparsers.add_parser(
        "search", help="Find cases similar to an indexed reference case."
    )
    search_parser.add_argument("case")
    search_parser.add_argument("--top-k", type=int, default=5)
    _add_cases_root(search_parser)

    export_parser = subparsers.add_parser(
        "export", help="Export governed case features for ML experiments."
    )
    export_parser.add_argument("--name", default="case_dataset")
    export_parser.add_argument("--output-root", type=Path, default=DATASETS_ROOT)
    export_parser.add_argument(
        "--all-cases",
        action="store_true",
        help="Include cases that fail the training quality gate.",
    )
    _add_cases_root(export_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = _run_command(args)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 2
    _print_json({"ok": True, **payload})
    return 0


def _run_command(args: argparse.Namespace) -> dict[str, Any]:
    cases_root = Path(args.cases_root).expanduser().resolve()
    if args.command == "import":
        source = Path(args.source).expanduser().resolve()
        units = None if args.no_units else args.units
        summary = scan_case_folder(
            source,
            title=args.title.strip() or source.stem,
            tags=_split_tags(args.tags),
            description=args.description,
            status=args.status,
            units=units,
            solver_version=args.solver_version,
            source_mode=args.source_mode,
            cases_root=cases_root,
        )
        return {
            "command": "import",
            "case_dir": summary.case_dir,
            "case_package": build_case_package(summary),
        }

    if args.command == "list":
        cases = list_cases(cases_root)[: max(0, int(args.limit))]
        return {
            "command": "list",
            "case_count": len(cases),
            "cases": [
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "execution_state": (case.quality or {}).get(
                        "execution_state", "unknown"
                    ),
                    "training_eligible": bool(
                        (case.quality or {}).get("training_eligible", False)
                    ),
                    "case_dir": case.case_dir,
                }
                for case in cases
            ],
        }

    if args.command == "inspect":
        summary = load_case_summary(_case_dir(args.case, cases_root))
        return {"command": "inspect", "case_package": build_case_package(summary)}

    if args.command == "search":
        summary = load_case_summary(_case_dir(args.case, cases_root))
        return {
            "command": "search",
            "query_case_id": summary.case_id,
            "matches": find_similar_cases(
                summary,
                cases_root=cases_root,
                top_k=max(1, int(args.top_k)),
            ),
        }

    if args.command == "export":
        export = export_case_dataset(
            cases_root=cases_root,
            output_root=Path(args.output_root).expanduser().resolve(),
            name=args.name,
            training_only=not args.all_cases,
        )
        return {
            "command": "export",
            "export_dir": str(export.export_dir),
            "dataset_csv": str(export.dataset_csv),
            "source_case_count": export.source_case_count,
            "case_count": export.case_count,
            "skipped_case_count": export.skipped_case_count,
        }

    raise ValueError(f"Unsupported command: {args.command}")


def _add_cases_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cases-root", type=Path, default=CASES_ROOT)


def _case_dir(value: str, cases_root: Path) -> Path:
    direct = Path(value).expanduser()
    if direct.exists():
        return direct.resolve()
    candidate = cases_root / value
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"Case does not exist: {value}")


def _split_tags(value: str) -> list[str]:
    return [
        item.strip() for item in value.replace("，", ",").split(",") if item.strip()
    ]


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
