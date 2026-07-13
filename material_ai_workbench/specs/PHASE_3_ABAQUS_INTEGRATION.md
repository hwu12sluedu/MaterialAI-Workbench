# Phase 3: Abaqus Integration Hardening

## Objective
Move from single-unit-element verification to batch job management, async ODB processing, and case similarity search.

## Prerequisites
- Phase 0 required (config.py essential)
- Phase 1 recommended (logging for debugging job states)

---

## Task 3.1: Abaqus Job Queue Manager

### Context
Currently, Abaqus jobs are started synchronously in the Streamlit UI, blocking the interface. The MCP client (`abaqus_mcp_client.py`) can submit jobs one at a time. The batch simulation (`batch_simulation.py`) runs jobs serially. No queue or concurrent management exists.

### Design
Create a lightweight job queue that:
- Accepts job submissions (job name, input file path, working directory)
- Runs jobs sequentially (Abaqus license limits concurrency anyway)
- Reports status (queued, running, completed, failed)
- Persists queue state to disk (survives Streamlit restart)
- Does NOT require a separate process — runs within the Streamlit thread with polling

### New file: `job_queue.py`

```python
"""Lightweight Abaqus job queue for the MaterialAI Workbench.

Jobs are serialised to JSON on disk so the queue survives app restarts.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from material_ai_workbench.config import ABAQUS_BAT
from material_ai_workbench.logging_config import get_logger

logger = get_logger(__name__)

QUEUE_FILE = Path(__file__).resolve().parent / "job_queue.json"


@dataclass
class QueuedJob:
    job_id: str
    name: str
    input_file: str          # path to .inp
    work_dir: str
    status: str = "queued"   # queued | running | completed | failed
    cpus: int = 4
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    return_code: int | None = None
    log_path: str | None = None
    error_message: str | None = None


class JobQueue:
    """Manages a serial queue of Abaqus jobs."""

    def __init__(self):
        self.jobs: list[QueuedJob] = []
        self._running = False
        self._load()

    def _load(self):
        if QUEUE_FILE.exists():
            raw = json.loads(QUEUE_FILE.read_text())
            self.jobs = [QueuedJob(**j) for j in raw.get("jobs", [])]

    def _save(self):
        QUEUE_FILE.write_text(json.dumps(
            {"updated_at": datetime.now().isoformat(), "jobs": [asdict(j) for j in self.jobs]},
            indent=2,
        ))

    def submit(self, name: str, input_file: str | Path, work_dir: str | Path,
               cpus: int = 4) -> QueuedJob:
        """Add a job to the queue."""
        import uuid
        job = QueuedJob(
            job_id=uuid.uuid4().hex[:8],
            name=name,
            input_file=str(input_file),
            work_dir=str(work_dir),
            cpus=cpus,
        )
        self.jobs.append(job)
        self._save()
        logger.info("Job queued: %s (%s)", job.job_id, job.name)
        return job

    def process_next(self) -> bool:
        """Run the next queued job. Returns True if a job was started."""
        if self._running:
            return False

        pending = [j for j in self.jobs if j.status == "queued"]
        if not pending:
            return False

        job = pending[0]
        job.status = "running"
        job.started_at = datetime.now().isoformat()
        job.log_path = str(Path(job.work_dir) / f"{job.name}.log")
        self._save()
        self._running = True

        try:
            logger.info("Starting job: %s", job.name)
            cmd = [
                str(ABAQUS_BAT),
                f"job={job.name}",
                f"input={job.input_file}",
                f"cpus={job.cpus}",
                "interactive",
            ]
            proc = subprocess.run(
                cmd,
                cwd=job.work_dir,
                capture_output=True,
                text=True,
                timeout=7200,  # 2-hour default
            )
            job.return_code = proc.returncode
            if proc.returncode == 0:
                job.status = "completed"
                logger.info("Job completed: %s", job.name)
            else:
                job.status = "failed"
                job.error_message = proc.stderr[:2000]
                logger.error("Job failed: %s (rc=%d)", job.name, proc.returncode)

        except subprocess.TimeoutExpired:
            job.status = "failed"
            job.error_message = "Job timed out (2 hours)"
            logger.error("Job timed out: %s", job.name)
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            logger.exception("Job error: %s", job.name)
        finally:
            job.finished_at = datetime.now().isoformat()
            self._running = False
            self._save()

        return True

    def get_status(self) -> dict:
        """Return queue summary."""
        statuses = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
        for j in self.jobs:
            statuses[j.status] = statuses.get(j.status, 0) + 1
        return {
            "total": len(self.jobs),
            **statuses,
            "running": any(j.status == "running" for j in self.jobs),
        }

    def clear_completed(self):
        """Remove completed and failed jobs from the queue."""
        self.jobs = [j for j in self.jobs if j.status in ("queued", "running")]
        self._save()

    def list_jobs(self) -> list[QueuedJob]:
        return list(self.jobs)
```

#### b) Integrate into `streamlit_app.py`

Add a new tab or a section within "Abaqus Verification" tab:

```python
# In _abaqus_panel() or a new _job_queue_panel():
from material_ai_workbench.job_queue import JobQueue

queue = JobQueue()
st.subheader("Job Queue")

# Show queue status
status = queue.get_status()
cols = st.columns(4)
cols[0].metric("Queued", status["queued"])
cols[1].metric("Running", status["running"])
cols[2].metric("Completed", status["completed"])
cols[3].metric("Failed", status["failed"])

# Submit form
with st.form("submit_job"):
    job_name = st.text_input("Job Name")
    input_file = st.text_input("Input File (.inp)")
    work_dir = st.text_input("Working Directory")
    cpus = st.number_input("CPUs", min_value=1, max_value=32, value=4)
    if st.form_submit_button("Submit to Queue"):
        queue.submit(job_name, input_file, work_dir, cpus)
        st.success(f"Job {job_name} queued")

# Process next button
if st.button("Process Next Job in Queue"):
    started = queue.process_next()
    if started:
        st.success("Job started")
    else:
        st.info("No pending jobs or a job is already running")

# Job list table
jobs = queue.list_jobs()
if jobs:
    rows = []
    for j in jobs:
        rows.append({
            "ID": j.job_id,
            "Name": j.name,
            "Status": j.status,
            "Submitted": j.submitted_at[:19],
            "Duration": _format_duration(j),
        })
    st.dataframe(rows)
```

### Acceptance Criteria
- Submit 3 jobs via the UI → queue shows all 3 as "queued"
- Click "Process Next" → first job starts, status changes to "running"
- Click "Process Next" while job is running → "No pending jobs or job already running"
- Job completes → status changes to "completed"
- Close and reopen Streamlit → queue state persists from `job_queue.json`
- Failed job (bad input file) → status "failed" with error message captured

---

## Task 3.2: Batch ODB Extraction Queue

### Context
In the case library UI (`case_library.py`), the "Extract All ODBs" button runs ODB extraction synchronously. For 10+ cases with large ODBs, this blocks the UI for minutes. Need to make it non-blocking using the JobQueue from 3.1 plus a lightweight task abstraction.

### Design
ODB extraction is not an Abaqus job — it's a local Python script run via `SMAPython.exe`. Create a generic `BackgroundTask` abstraction that can be processed by the same queue infrastructure.

### New file: `task_queue.py`

```python
"""Lightweight background task queue.

Runs arbitrary Python functions or subprocess commands as queued tasks.
Integrates with the JobQueue for a unified queue UI.
"""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from material_ai_workbench.logging_config import get_logger

logger = get_logger(__name__)

TASK_QUEUE_FILE = Path(__file__).resolve().parent / "task_queue.json"


@dataclass
class BackgroundTask:
    task_id: str
    name: str
    task_type: str           # "odp_extract" | "frame_series" | "abaqus_job" | "custom"
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class TaskQueue:
    """Thread-safe task queue with disk persistence."""

    def __init__(self):
        self.tasks: list[BackgroundTask] = []
        self._lock = threading.Lock()
        self._running = False
        self._load()

    def _load(self): ...
    def _save(self): ...

    def enqueue(self, name: str, task_type: str, params: dict) -> BackgroundTask:
        import uuid
        task = BackgroundTask(
            task_id=uuid.uuid4().hex[:8],
            name=name,
            task_type=task_type,
            params=params,
        )
        with self._lock:
            self.tasks.append(task)
            self._save()
        return task

    def enqueue_odb_extraction(self, case_id: str, odb_path: str) -> BackgroundTask:
        return self.enqueue(
            name=f"ODB extract: {case_id}",
            task_type="odb_extract",
            params={"case_id": case_id, "odb_path": odb_path},
        )

    def enqueue_odb_frame_series(self, case_id: str, odb_path: str,
                                 named_set: str | None = None) -> BackgroundTask:
        return self.enqueue(
            name=f"Frame series: {case_id}",
            task_type="frame_series",
            params={"case_id": case_id, "odb_path": odb_path, "named_set": named_set},
        )

    def process_next(self) -> bool:
        """Execute the next queued task. Returns True if a task was processed."""
        with self._lock:
            if self._running:
                return False
            pending = [t for t in self.tasks if t.status == "queued"]
            if not pending:
                return False
            task = pending[0]
            task.status = "running"
            task.started_at = datetime.now().isoformat()
            self._running = True
            self._save()

        try:
            if task.task_type == "odb_extract":
                self._run_odb_extract(task)
            elif task.task_type == "frame_series":
                self._run_frame_series(task)
            else:
                task.status = "failed"
                task.error = f"Unknown task type: {task.task_type}"
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            logger.exception("Task failed: %s", task.task_id)
        finally:
            task.finished_at = datetime.now().isoformat()
            with self._lock:
                self._running = False
                self._save()

        return True

    def _run_odb_extract(self, task: BackgroundTask):
        from material_ai_workbench.odb_postprocess import run_case_odb_extraction
        from material_ai_workbench.case_library import load_case_summary, save_case_summary

        case = load_case_summary(task.params["case_id"])
        if case is None:
            task.status = "failed"
            task.error = f"Case not found: {task.params['case_id']}"
            return

        result = run_case_odb_extraction(case, backend="abaqus_python")
        save_case_summary(case)
        task.status = "completed"
        task.result = {"extraction_dir": str(result) if result else None}

    def _run_frame_series(self, task: BackgroundTask):
        from material_ai_workbench.odb_postprocess import run_case_odb_frame_series_extraction
        from material_ai_workbench.case_library import load_case_summary, save_case_summary

        case = load_case_summary(task.params["case_id"])
        if case is None:
            task.status = "failed"
            task.error = f"Case not found: {task.params['case_id']}"
            return

        named_set = task.params.get("named_set")
        result = run_case_odb_frame_series_extraction(
            case, backend="abaqus_python",
            named_set=named_set,
        )
        save_case_summary(case)
        task.status = "completed"
        task.result = {"frame_series_dir": str(result) if result else None}
```

#### b) Update `streamlit_app.py` `_case_library_panel()`

Replace the synchronous "Extract All ODBs" button with a queue-based UI:
1. "Enqueue ODB Extraction for This Case" button (single case)
2. "Enqueue All Pending ODB Extractions" button (all cases)
3. A section showing the task queue status, with a "Process Next Task" button
4. Task results table

### Acceptance Criteria
- Enqueue ODB extraction for a case → task shows as "queued"
- Process task → extraction runs in background → task shows as "completed"
- Case summary updated with ODB extraction record
- Can queue multiple extractions and process them one at a time
- Streamlit UI remains responsive while extraction runs

---

## Task 3.3: Similar Case Retrieval

### Context
The case library indexes simulation folders but provides no way to find "cases like this one." As the library grows to 50+ cases, users need similarity search to find relevant historical simulations.

### Design
Compute a feature vector for each case (INP structure + material parameters + result signals) and use cosine similarity for retrieval. No external dependencies needed — pure numpy.

### File to modify
`D:\githubproject\pyLabFEA\material_ai_workbench\case_library.py`

### Add to case_library.py

```python
import numpy as np

# Feature vector keys in priority order
SIMILARITY_FEATURES = [
    "inp_node_count",
    "inp_element_count",
    "file_count",
    "csv_row_count",
    "result_max_mises",
    "result_max_peeq",
    "log_warning_count",
    "log_error_count",
    "yield_strength",
    "youngs_modulus",
]


def _case_to_feature_vector(case: CaseSummary) -> np.ndarray:
    """Convert a case summary to a normalized feature vector for similarity."""
    vec = np.zeros(len(SIMILARITY_FEATURES))
    for i, key in enumerate(SIMILARITY_FEATURES):
        # Try case parameters first, then INP features, then result features
        val = case.parameters.get(key)
        if val is not None:
            vec[i] = float(val)
            continue
        val = getattr(case.inp_features, key, None) if case.inp_features else None
        if val is not None:
            vec[i] = float(val)
            continue
        # result_features is a dict of signal name -> {min, max, mean}
        if case.result_features:
            for sig_name, sig_stats in case.result_features.items():
                if key.replace("result_", "") in sig_name.lower():
                    vec[i] = float(sig_stats.get("max", 0))
                    break
    return vec


def find_similar_cases(
    query_case_id: str,
    top_k: int = 5,
) -> list[tuple[str, str, float]]:
    """Return top-k similar cases by cosine similarity.

    Returns list of (case_id, title, similarity_score).
    """
    cases = list_cases()
    if not cases:
        return []

    # Build feature matrix
    case_ids = [c.case_id for c in cases]
    vectors = np.array([_case_to_feature_vector(c) for c in cases])

    # Handle zero vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors_norm = vectors / norms

    # Find query index
    try:
        query_idx = case_ids.index(query_case_id)
    except ValueError:
        return []

    query_vec = vectors_norm[query_idx:query_idx + 1]

    # Cosine similarity
    similarities = (vectors_norm @ query_vec.T).flatten()

    # Get top-k (excluding self)
    top_indices = np.argsort(similarities)[::-1]
    results = []
    for idx in top_indices:
        if idx == query_idx:
            continue
        if len(results) >= top_k:
            break
        results.append((case_ids[idx], cases[idx].title or case_ids[idx],
                        float(similarities[idx])))
    return results
```

#### Update `streamlit_app.py` `_case_library_panel()`

In the case detail view, add a "Similar Cases" section that shows the top-5 similar cases with similarity scores as a progress bar.

### Acceptance Criteria
- Two J2 cases with similar element counts → similarity > 0.9
- A J2 case and a composite case → similarity < 0.5
- Query a case that doesn't exist → returns empty list
- Similar cases appear in the Streamlit UI case detail view

---

## Dependencies Between Tasks

```
3.1 (job queue) ── no dependencies, implement first
3.2 (ODB extraction queue) ── depends on 3.1 (uses same patterns, can share BaseQueue)
3.3 (similar cases) ── independent of 3.1/3.2
```
