"""MaterialAI Workbench built on top of the bundled pyLabFEA fork."""

from importlib.metadata import PackageNotFoundError, version

from .composite_workflow import CompositePlateConfig, CompositePlateResult, run_composite_plate_workflow
from .composite_dataset import (
    CompositeBatchConfig,
    create_composite_batch_plan,
    run_composite_batch_plan,
    train_composite_surrogate,
)
from .composite_benchmarks import composite_benchmark_rows, load_composite_benchmarks
from .experimental_datasets import (
    ExperimentalDatasetResult,
    prepare_cfrp_experimental_dataset,
)
from .pipeline import WorkbenchConfig, WorkbenchResult, run_material_workbench
from .job_queue import JobQueue, QueuedJob
from .multi_fidelity import MultiFidelityResult, train_multi_fidelity

try:
    __version__ = version("materialai-workbench")
except PackageNotFoundError:
    __version__ = "0.4.0a1"

__all__ = [
    "CompositePlateConfig",
    "CompositePlateResult",
    "CompositeBatchConfig",
    "ExperimentalDatasetResult",
    "WorkbenchConfig",
    "WorkbenchResult",
    "JobQueue",
    "QueuedJob",
    "MultiFidelityResult",
    "create_composite_batch_plan",
    "composite_benchmark_rows",
    "load_composite_benchmarks",
    "prepare_cfrp_experimental_dataset",
    "run_composite_batch_plan",
    "train_composite_surrogate",
    "run_composite_plate_workflow",
    "run_material_workbench",
    "train_multi_fidelity",
    "__version__",
]
