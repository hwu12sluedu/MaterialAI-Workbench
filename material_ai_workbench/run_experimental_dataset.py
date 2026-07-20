"""Prepare the traceable public CFRP experimental benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from material_ai_workbench.config import DATASETS_ROOT
from material_ai_workbench.experimental_datasets import (
    ALSHEGHRI_CFRP_SPEC,
    prepare_cfrp_experimental_dataset,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-xlsx",
        type=Path,
        default=None,
        help="Use an already downloaded official workbook instead of the network.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DATASETS_ROOT,
        help="Dataset workspace root.",
    )
    parser.add_argument(
        "--accept-license",
        action="store_true",
        help=(
            f"Accept {ALSHEGHRI_CFRP_SPEC.license_name} before downloading from "
            "the official source."
        ),
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare the dataset and emit a machine-readable result."""

    args = build_parser().parse_args(argv)
    try:
        result = prepare_cfrp_experimental_dataset(
            source_path=args.source_xlsx,
            output_root=args.output_root,
            accept_license=args.accept_license,
            timeout_seconds=args.timeout,
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
                "status": "prepared",
                "dataset_dir": str(result.dataset_dir),
                "row_count": result.row_count,
                "quality_status": result.quality_status,
                "manifest_json": str(result.manifest_json),
                "normalized_csv": str(result.normalized_csv),
                "grouped_splits": str(result.split_manifest_json),
                "data_card": str(result.data_card_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
