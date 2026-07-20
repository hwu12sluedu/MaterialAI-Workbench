"""Train fixed-split CFRP experimental regression baselines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from material_ai_workbench.experimental_baselines import (
    DEFAULT_DATASET_DIR,
    DEFAULT_MODELS,
    DEFAULT_OUTPUT_ROOT,
    train_cfrp_grouped_baselines,
)
from material_ai_workbench.experimental_datasets import TARGET_COLUMNS


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
        help="Experiment output root.",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGET_COLUMNS,
        dest="targets",
        help="Target to evaluate; repeat for multiple targets. Defaults to all.",
    )
    parser.add_argument(
        "--model",
        action="append",
        choices=DEFAULT_MODELS,
        dest="models",
        help="Model to evaluate; repeat for multiple models. Defaults to all.",
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--interval-coverage", type=float, default=0.90)
    parser.add_argument("--rf-estimators", type=int, default=250)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the experiment and emit a machine-readable result."""

    args = build_parser().parse_args(argv)
    try:
        result = train_cfrp_grouped_baselines(
            args.dataset_dir,
            output_root=args.output_root,
            targets=args.targets,
            models=args.models or DEFAULT_MODELS,
            random_state=args.random_state,
            interval_coverage=args.interval_coverage,
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

    best_models = {
        target: details["best_model_by_grouped_mae"]
        for target, details in result.summary["targets"].items()
    }
    print(
        json.dumps(
            {
                "status": "completed_with_warnings",
                "run_dir": str(result.run_dir),
                "summary_json": str(result.summary_json),
                "comparison_csv": str(result.comparison_csv),
                "predictions_csv": str(result.predictions_csv),
                "report_md": str(result.report_md),
                "best_models_by_grouped_mae": best_models,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
