"""MaterialAI Workbench built on top of the bundled pyLabFEA fork."""

from importlib.metadata import PackageNotFoundError, version

from .composite_workflow import CompositePlateConfig, CompositePlateResult, run_composite_plate_workflow
from .composite_dataset import (
    CompositeBatchConfig,
    create_composite_batch_plan,
    run_composite_batch_plan,
    train_composite_surrogate,
)
from .pipeline import WorkbenchConfig, WorkbenchResult, run_material_workbench
from .job_queue import JobQueue, QueuedJob
from .multi_fidelity import MultiFidelityResult, train_multi_fidelity

try:
    __version__ = version("materialai-workbench")
except PackageNotFoundError:
    __version__ = "0.3.0"

__all__ = [
    "CompositePlateConfig",
    "CompositePlateResult",
    "CompositeBatchConfig",
    "WorkbenchConfig",
    "WorkbenchResult",
    "JobQueue",
    "QueuedJob",
    "MultiFidelityResult",
    "create_composite_batch_plan",
    "run_composite_batch_plan",
    "train_composite_surrogate",
    "run_composite_plate_workflow",
    "run_material_workbench",
    "train_multi_fidelity",
    "__version__",
]
