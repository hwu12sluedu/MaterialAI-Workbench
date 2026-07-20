"""Audit CFRP validation protocols and exact-duplicate sensitivity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from material_ai_workbench.experimental_baselines import (
    DEFAULT_DATASET_DIR,
    DEFAULT_MODELS,
)
from material_ai_workbench.experimental_datasets import TARGET_COLUMNS
from material_ai_workbench.experimental_validation import (
    DEFAULT_OUTPUT_ROOT,
    run_cfrp_validation_audit,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="Prepared CFRP dataset version directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Validation-audit output root.",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGET_COLUMNS,
        dest="targets",
        help="Target to audit; repeat for multiple targets. Defaults to all.",
    )
    parser.add_argument(
        "--model",
        action="append",
        choices=DEFAULT_MODELS,
        dest="models",
        help="Model to audit; repeat for multiple models. Defaults to all.",
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--rf-estimators", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the audit and emit a machine-readable result."""

    args = build_parser().parse_args(argv)
    try:
        result = run_cfrp_validation_audit(
            args.dataset_dir,
            output_root=args.output_root,
            targets=args.targets,
            models=args.models or DEFAULT_MODELS,
            random_state=args.random_state,
            rf_estimators=args.rf_estimators,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "error", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            {
                "status": "completed_with_warnings",
                "run_dir": str(result.run_dir),
                "summary_json": str(result.summary_json),
                "comparison_csv": str(result.comparison_csv),
                "predictions_csv": str(result.predictions_csv),
                "duplicate_clusters_csv": str(result.duplicate_clusters_csv),
                "report_md": str(result.report_md),
                "release_gate_protocol": result.summary["release_gate_protocol"],
                "duplicate_audit": result.summary["duplicate_audit"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
